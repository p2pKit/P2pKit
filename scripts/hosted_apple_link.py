#!/usr/bin/env python3
"""Bounded Xcode 16.2 dependency-link admission, NOT a writer/runtime gate.

There is intentionally no CLI or subprocess/network implementation here. The
genuine hosted controller must first admit its ordinary native host and natural
mDNS control, then supply Runtime.command. That callback owns every process,
environment, deadline, private stream, receipt, and retirement. All products stay
in one new private directory for the controller's failure-safe encrypted export.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import xml.etree.ElementTree as ET
import zipfile

KIB, MIB = 1024, 1024 ** 2
FETCH_LIMIT, TOTAL_FETCH_LIMIT = 128 * KIB, 384 * KIB
ARCHIVE_LIMIT, ZIP_LIMIT, LOG_LIMIT, PRODUCT_LIMIT = 512 * KIB, 2 * MIB, 16 * MIB, 16 * MIB
XCODE = Path("/Applications/Xcode_16.2.app/Contents/Developer")
XCODE_VERSION = "Xcode 16.2\nBuild version 16C5032a\n"
SDK_VERSION = "18.2"
HEADER = "library/p2p-transport-lan/src/nativeInterop/cinterop/p2pkit_nw.h"
METADATA = "gradle/verification-metadata.xml"
NAMESPACE = "https://schema.gradle.org/dependency-verification"
SCOPE = "DEPENDENCY_LINK_ADMISSION_NOT_WRITER_OR_RUNTIME_ACCEPTANCE"
BRIDGE_FUNCTIONS = (
    "p2pkit_nw_create_plain_tcp_parameters", "p2pkit_lan_enumerate_interface_addresses",
    "p2pkit_lan_interface_fingerprint", "p2pkit_test_bind_tcp_port", "p2pkit_test_nw_connection_send_fin",
    "p2pkit_nw_connection_send_default", "p2pkit_nw_connection_receive_default",
)


@dataclass(frozen=True)
class Target:
    name: str
    native: str
    sdk: str
    arch: str
    cpu: int
    subtype: int
    platform: int
    size: int
    sha256: str
    archive_size: int
    archive_sha256: str

    @property
    def component(self):
        return "cryptography-provider-cryptokit-" + self.name.lower()

    @property
    def filename(self):
        return "cryptography-provider-cryptokit-" + self.name + "Cinterop-swiftInteropDwcCryptoKitInteropMain-0.6.0.klib"

    @property
    def url(self):
        # Gradle's verification/cache "name" above is NOT the Maven filename.
        # These URLs are the exact file URLs in the pinned 0.6.0 module metadata.
        filename = self.component + "-0.6.0-cinterop-swiftInteropDwcCryptoKitInterop.klib"
        return "https://repo.maven.apache.org/maven2/dev/whyoleg/cryptography/" + self.component + "/0.6.0/" + filename

    @property
    def entry(self):
        return "default/targets/" + self.native + "/included/libDwcCryptoKitInterop.a"

    @property
    def triple(self):
        return self.arch + "-apple-ios14.0" + ("-simulator" if self.platform == 7 else "")


TARGETS = (
    Target("iosArm64", "ios_arm64", "iphoneos", "arm64", 0x0100000C, 0, 2, 102567,
           "fca5d07f0a82fcc586698f79cf20555c283364547aed695dc4c15b10adb6c4c3", 352448,
           "eea69e60cf1f57837067106c9113f743245bb97ac8e6bef6f49cc47f50e18ec0"),
    Target("iosSimulatorArm64", "ios_simulator_arm64", "iphonesimulator", "arm64", 0x0100000C, 0, 7, 101131,
           "edf55df5f8e4661c5a5813cbd514737e07f7ffa87018710e619b8857e7461a4a", 347624,
           "2c3955b3f1bb85e7279af5fc527acc0079c5eee123b019a039ded48d7345079f"),
    Target("iosX64", "ios_x64", "iphonesimulator", "x86_64", 0x01000007, 3, 7, 88500,
           "6d5431aa6ce1714047355adf9b78131c5a657f717a3382d2aae237701e42bae0", 313640,
           "068b9bc08a201c706b1f01c7ad1ba1c25945e75937cb1cb0dd979877dc4850fa"),
)


class AdmissionError(ValueError):
    """A HOLD; report is attached by admit(), never converted into admission."""


def require(value, message):
    if not value:
        raise AdmissionError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def physical(path, *, directory=False):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "absolute physical path required")
    for part in (path, *path.parents):
        require(not part.is_symlink(), "symlink is not an owned path")
    if directory:
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(), "directory not owned")
    return path


def read(path, limit):
    path = physical(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1 and
            0 <= before.st_size <= limit, "input is not a bounded owned single-link regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        require(os.path.samestat(before, opened), "input replaced before reading")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(os.path.samestat(before, after) and os.path.samestat(before, path.lstat()) and
            len(raw) == before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns,
            "input changed while reading")
    return raw


def write(path, raw):
    path = physical(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def check_pins(raw):
    require(len(raw) <= 16 * MIB and b"<!DOCTYPE" not in raw.upper() and b"<!ENTITY" not in raw.upper(),
            "unadmitted verification XML")
    document = ET.fromstring(raw)
    require(document.tag == "{" + NAMESPACE + "}verification-metadata", "verification namespace differs")
    for target in TARGETS:
        components = document.findall("./v:components/v:component[@group='dev.whyoleg.cryptography']"
                                      "[@name='" + target.component + "'][@version='0.6.0']", {"v": NAMESPACE})
        require(len(components) == 1, "exact CryptoKit component required: " + target.name)
        artifacts = components[0].findall("v:artifact[@name='" + target.filename + "']", {"v": NAMESPACE})
        require(len(artifacts) == 1, "exact CryptoKit artifact required: " + target.name)
        pins = artifacts[0].findall("v:sha256", {"v": NAMESPACE})
        require([row.get("value") for row in pins] == [target.sha256], "CryptoKit verification pin changed: " + target.name)


def macho(raw, target, filetype, sdk):
    require(32 <= len(raw) <= PRODUCT_LIMIT and raw[:4] == b"\xcf\xfa\xed\xfe", "64-bit little-endian Mach-O required")
    _, cpu, subtype, kind, count, size, _, _ = struct.unpack_from("<8I", raw)
    require(cpu == target.cpu and subtype & 0x00FFFFFF == target.subtype and kind == filetype,
            "Mach-O architecture/filetype differs")
    require(0 < count <= 512 and count * 8 <= size <= len(raw) - 32, "Mach-O load-command bound")
    offset, versions, options = 32, [], []
    for _ in range(count):
        require(offset + 8 <= 32 + size, "truncated Mach-O command")
        command, length = struct.unpack_from("<II", raw, offset)
        require(length >= 8 and length % 8 == 0 and offset + length <= 32 + size, "invalid Mach-O command extent")
        if command == 0x32:  # LC_BUILD_VERSION
            require(length >= 24, "truncated Mach-O build version")
            platform, minimum, actual_sdk, tools = struct.unpack_from("<4I", raw, offset + 8)
            require(tools <= 8 and length == 24 + tools * 8, "invalid Mach-O build tools")
            versions.append((platform, minimum, actual_sdk))
        elif command == 0x2D:  # LC_LINKER_OPTION: retained, never evaluated as Python/shell input.
            require(length >= 16, "truncated Mach-O linker option")
            number = struct.unpack_from("<I", raw, offset + 8)[0]
            values = raw[offset + 12:offset + length].split(b"\0")
            require(0 < number <= 32 and len(values) > number and all(not value for value in values[number:]),
                    "invalid Mach-O linker-option strings")
            require(all(0 < len(value) <= 1024 for value in values[:number]), "Mach-O linker-option bound")
            options.append([value.decode("ascii") for value in values[:number]])
        offset += length
    require(offset == 32 + size and versions == [(target.platform, 14 << 16, sdk)],
            "Mach-O platform/deployment/SDK differs")
    return {"cpuType": cpu, "cpuSubtype": subtype, "filetype": kind, "platform": target.platform,
            "minimum": "14.0", "sdkCode": sdk, "linkerOptions": options, "bytes": len(raw), "sha256": sha256(raw)}


def inspect_archive(raw, target):
    require(0 < len(raw) <= ARCHIVE_LIMIT and len(raw) == target.archive_size and
            sha256(raw) == target.archive_sha256 and raw.startswith(b"!<arch>\n"), "included archive bytes differ")
    offset, rows, names = 8, [], set()
    while offset < len(raw):
        require(len(rows) < 64 and offset + 60 <= len(raw), "ar member bound/header")
        header = raw[offset:offset + 60]
        require(header[-2:] == b"`\n", "invalid ar header")
        name, text_size = header[:16].decode("ascii").rstrip(), header[48:58].decode("ascii").strip()
        require(re.fullmatch(r"[0-9]{1,10}", text_size), "invalid ar member size")
        size, start = int(text_size), offset + 60
        require(0 < size <= ARCHIVE_LIMIT and start + size <= len(raw), "ar member extent")
        member = raw[start:start + size]
        if name.startswith("#1/"):
            require(re.fullmatch(r"#1/[0-9]{1,3}", name), "invalid BSD ar name")
            name_size = int(name[3:])
            require(0 < name_size <= 256 and name_size < len(member), "BSD ar name bound")
            name = member[:name_size].rstrip(b"\0").decode("ascii")
            member = member[name_size:]
        else:
            name = name.removesuffix("/")
        require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.+-]{0,127}", name) and name not in names,
                "unsafe/duplicate ar member")
        names.add(name)
        row = {"name": name, "bytes": len(member), "sha256": sha256(member)}
        if name == "__.SYMDEF":
            require(not rows, "ar symbol table must be first")
            row["kind"] = "symbol-table"
        else:
            require(name.endswith(".o"), "unadmitted ar member type")
            row["macho"] = macho(member, target, 1, (26 << 16) | (2 << 8))
        rows.append(row)
        offset = start + size + size % 2
        require(offset <= len(raw) and (not size % 2 or raw[offset - 1:offset] == b"\n"), "invalid ar padding")
    require(offset == len(raw) and len(rows) >= 2 and rows[0]["name"] == "__.SYMDEF" and
            all("macho" in row for row in rows[1:]), "complete native archive required")
    return rows


def unpack(raw, target):
    require(0 < len(raw) <= FETCH_LIMIT and len(raw) == target.size and sha256(raw) == target.sha256,
            "CryptoKit download size/hash mismatch: " + target.name)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        require(0 < len(entries) <= 128 and sum(row.file_size for row in entries) <= ZIP_LIMIT, "Klib ZIP bounds")
        seen = set()
        for row in entries:
            name, mode = row.filename, row.external_attr >> 16
            path = PurePosixPath(name)
            require(name == row.orig_filename and 0 < len(name) <= 512 and name.isascii() and "\\" not in name and
                    not path.is_absolute() and ".." not in path.parts and
                    str(path) + ("/" if row.is_dir() else "") == name and name not in seen,
                    "unsafe/duplicate Klib entry")
            seen.add(name)
            require(row.create_system == 3 and (stat.S_ISDIR(mode) if row.is_dir() else stat.S_ISREG(mode)) and
                    not row.flag_bits & 1 and row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and
                    0 <= row.file_size <= ZIP_LIMIT and (not row.is_dir() or row.file_size == 0), "nonregular/unbounded Klib entry")
        included = [row for row in entries if row.filename.endswith(".a")]
        require(len(included) == 1 and included[0].filename == target.entry and
                included[0].file_size == target.archive_size <= ARCHIVE_LIMIT, "exact single included archive required")
        require("default/manifest" in seen, "Klib manifest missing")
        manifest = archive.getinfo("default/manifest")
        require(0 < manifest.file_size <= 16 * KIB, "Klib manifest bound")
        with archive.open(manifest) as stream:
            manifest_raw = stream.read(16 * KIB + 1)
        require(len(manifest_raw) == manifest.file_size, "Klib manifest extent")
        fields = {}
        for line in manifest_raw.decode("utf-8").splitlines():
            require("=" in line, "Klib manifest format")
            key, value = line.split("=", 1)
            require(key not in fields, "duplicate Klib manifest field")
            fields[key] = value
        require(fields.get("native_targets") == target.native and fields.get("staticLibraries") == "libDwcCryptoKitInterop.a" and
                fields.get("builtins_platform") == "NATIVE" and fields.get("interop") == "true", "Klib target/library differs")
        with archive.open(included[0]) as stream:
            native = stream.read(ARCHIVE_LIMIT + 1)
        require(len(native) == included[0].file_size, "included archive extent")
    return native, {"entry": target.entry, "bytes": len(native), "sha256": sha256(native),
                    "manifestSha256": sha256(manifest_raw), "members": inspect_archive(native, target)}


def installed(path, developer, *, directory=False):
    require(path.is_absolute() and ".." not in path.parts and not any(char in str(path) for char in "\r\n\x00"),
            "invalid installed tool/SDK path")
    canonical = path.resolve(strict=True)
    require(developer in canonical.parents and (canonical.is_dir() if directory else canonical.is_file()),
            "tool/SDK escapes selected installed Xcode")
    if not directory:
        require(os.access(canonical, os.X_OK), "installed tool is not executable")
    return canonical


def swift_inventory(path, developer):
    path = installed(path, developer, directory=True)
    rows = []
    entries = sorted(path.iterdir())
    require(len(entries) <= 1024, "Swift support directory bound")
    for entry in entries:
        if not entry.name.startswith("libswift") or entry.suffix not in (".a", ".dylib", ".tbd"):
            continue
        canonical = entry.resolve(strict=True)
        require(developer in canonical.parents and canonical.is_file(), "Swift support library escapes selected Xcode")
        rows.append({"name": entry.name, "path": str(canonical), "bytes": canonical.stat().st_size})
    require(rows, "installed Swift support inventory is empty")
    return {"path": str(path), "libraries": rows}


class Session:
    def __init__(self, root, directory, command):
        self.root, self.directory = physical(root, directory=True), physical(directory)
        parent = physical(self.directory.parent, directory=True)
        require(parent.stat().st_mode & 0o077 == 0, "private owned evidence parent required")
        require(self.root != self.directory and self.root not in self.directory.parents and
                self.directory not in self.root.parents, "source/evidence paths overlap")
        require(callable(command), "owned command callback required")
        self.directory.mkdir(mode=0o700)
        info = self.directory.stat()
        self.identity = info.st_dev, info.st_ino
        self.command = command
        self.report = {"schema": 1, "scope": SCOPE, "status": "HOLD", "directory": str(self.directory),
                       "fetchLimitBytes": FETCH_LIMIT, "aggregateFetchLimitBytes": TOTAL_FETCH_LIMIT,
                       "fetchedBytes": 0, "targets": [], "commands": [], "runtimeExecuted": False,
                       "writerExecuted": False, "physicalDeviceEvidence": False}

    def guard(self):
        info = physical(self.directory, directory=True).stat()
        require((info.st_dev, info.st_ino) == self.identity and info.st_mode & 0o077 == 0,
                "owned admission directory changed")

    def run(self, label, argv, seconds=120, *, diagnostics=False):
        self.guard()
        row = {"label": "apple-link-" + label, "argv": list(argv), "timeoutSeconds": seconds, "status": "REQUESTED"}
        self.report["commands"].append(row)
        result = self.command(row["label"], list(argv), seconds=seconds)
        self.guard()
        receipt = result.row
        require(receipt.get("argv") == list(argv) and receipt.get("timeoutSeconds") == seconds and
                receipt.get("launchAttempted") is True and type(receipt.get("waitExitCode")) is int and
                receipt["waitExitCode"] == 0 and receipt.get("exitAfterDrain") == 0 and receipt.get("errors") == [],
                "owned command failed or receipt differs: " + label)
        drains, ownership = receipt.get("drains"), receipt.get("ownership", {})
        require(isinstance(drains, list) and drains and all(item.get("survivors") == [] and item.get("error") is None
                for item in drains) and ownership.get("backend") == "darwin-libproc-audit-token" and
                ownership.get("discoveryErrors") == [], "command retirement unknown: " + label)
        streams = {}
        for name in ("stdout", "stderr"):
            raw = read(result.directory / (name + ".log"), LOG_LIMIT)
            observation = receipt.get("streams", {}).get(name, {})
            require(observation.get("truncated") is False and type(observation.get("observedBytes")) is int and
                    observation["observedBytes"] == observation.get("retainedBytes") == len(raw), "command stream incomplete: " + label)
            streams[name] = raw
        row.update(status="COMPLETED", directory=str(result.directory), receipt=receipt,
                   streams={name: {"bytes": len(raw), "sha256": sha256(raw)} for name, raw in streams.items()})
        if diagnostics:
            for raw in streams.values():
                require(not re.search(rb"(?im)(?:^|[ :])(?:warning|error|fatal error):|could not find or use auto-linked|"
                                      rb"undefined symbols|library not found|framework not found", raw),
                        "compiler/linker diagnostics prevent admission: " + label)
        return streams["stdout"].decode("utf-8")

    def execute(self):
        metadata, header = read(self.root / METADATA, 16 * MIB), read(self.root / HEADER, 128 * KIB)
        check_pins(metadata)
        require(header and set(re.findall(rb"^static inline[^\n]*\b(p2pkit_[a-z0-9_]+)\(", header, re.M)) ==
                {name.encode() for name in BRIDGE_FUNCTIONS}, "maintained bridge helper inventory changed")
        self.report["inputs"] = {METADATA: sha256(metadata), HEADER: sha256(header)}
        write(self.directory / "p2pkit_nw.h.retained", header)
        source = b'#include "p2pkit_nw.h"\n' + b"".join(
            ("__attribute__((used)) static __typeof__(&" + name + ") const p2pkit_admission_keep_" + str(index) +
             " = &" + name + ";\n").encode() for index, name in enumerate(BRIDGE_FUNCTIONS)) + b"int main(void) { return 0; }\n"
        source_path = self.directory / "bridge.m"
        write(source_path, source)
        self.report["bridgeSourceSha256"] = sha256(source)
        developer = physical(XCODE).resolve(strict=True)
        require(developer == XCODE and developer.is_dir(), "canonical Xcode 16.2 installation required")
        require(self.run("xcode-version", ["/usr/bin/xcodebuild", "-version"]) == XCODE_VERSION,
                "Xcode 16.2 build differs")
        toolchain = developer / "Toolchains/XcodeDefault.xctoolchain/usr"
        tools = {}
        for name in ("clang", "ld", "swift"):
            text = self.run("find-" + name, ["/usr/bin/xcrun", "--find", name]).strip()
            path = installed(Path(text), developer)
            require(path == (toolchain / "bin" / name).resolve(strict=True), "selected Xcode toolchain differs")
            tools[name] = str(path)
        self.run("clang-version", [tools["clang"], "--version"])
        self.run("linker-version", [tools["ld"], "-v"])
        sdks = {}
        for sdk in ("iphoneos", "iphonesimulator"):
            path = installed(Path(self.run("sdk-" + sdk, ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-path"]).strip()),
                             developer, directory=True)
            platform = "iPhoneOS.platform" if sdk == "iphoneos" else "iPhoneSimulator.platform"
            require((developer / "Platforms" / platform / "Developer/SDKs") in path.parents, "SDK platform path differs")
            version = self.run("sdk-version-" + sdk, ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-version"]).strip()
            require(version == SDK_VERSION, "installed SDK version differs")
            sdks[sdk] = {"path": str(path), "version": version,
                         "toolchainSwift": swift_inventory(toolchain / "lib/swift" / sdk, developer),
                         "sdkSwift": swift_inventory(path / "usr/lib/swift", developer)}
        self.report["installed"] = {"developer": str(developer), "tools": tools, "sdks": sdks}
        curl = self.run("curl-version", ["/usr/bin/curl", "--disable", "--version"])
        match = re.match(r"curl ([0-9]+)\.([0-9]+)\.([0-9]+)(?:[ -])", curl)
        require(match and tuple(map(int, match.groups())) >= (8, 4, 0), "curl with streaming max-filesize enforcement required")
        require(len(TARGETS) == 3 and sum(target.size for target in TARGETS) <= TOTAL_FETCH_LIMIT,
                "exact bounded three-target acquisition required")
        for target in TARGETS:
            self.guard()
            target_directory = self.directory / target.name
            target_directory.mkdir(mode=0o700)
            klib, native = target_directory / target.filename, target_directory / "libDwcCryptoKitInterop.a"
            write(klib, b"")
            downloaded = self.run("fetch-" + target.name,
                ["/usr/bin/curl", "--disable", "--fail", "--silent", "--show-error", "--proto", "=https", "--tlsv1.2",
                 "--proxy", "", "--retry", "0", "--max-redirs", "0", "--connect-timeout", "15", "--max-time", "60",
                 "--max-filesize", str(FETCH_LIMIT), "--output", str(klib), "--write-out",
                 "%{http_code}\n%{size_download}\n%{url_effective}\n", target.url], 90)
            require(downloaded.splitlines() == ["200", str(target.size), target.url], "HTTP source/size differs")
            raw = read(klib, FETCH_LIMIT)
            self.report["fetchedBytes"] += len(raw)
            require(self.report["fetchedBytes"] <= TOTAL_FETCH_LIMIT, "aggregate download bound")
            archive, inspection = unpack(raw, target)
            write(native, archive)
            row = {"target": target.name, "triple": target.triple, "url": target.url, "klibBytes": len(raw),
                   "klibSha256": sha256(raw), "archive": inspection, "status": "LINK_NOT_STARTED"}
            self.report["targets"].append(row)
            sdk = sdks[target.sdk]
            compiler = [tools["clang"], "-target", target.triple, "-isysroot", sdk["path"]]
            obj, executable = target_directory / "bridge.o", target_directory / "link-admission"
            self.run("compile-" + target.name, [*compiler, "-std=gnu11", "-fblocks", "-fobjc-arc", "-fno-modules",
                "-Wall", "-Wextra", "-Werror", "-I", str((self.root / HEADER).parent), "-c", str(source_path), "-o", str(obj)],
                diagnostics=True)
            row["object"] = macho(read(obj, MIB), target, 1, (18 << 16) | (2 << 8))
            self.run("link-" + target.name, [*compiler, "-fobjc-arc", "-fuse-ld=" + tools["ld"], str(obj),
                "-Xlinker", "-force_load", "-Xlinker", str(native), "-Xlinker", "-fatal_warnings",
                "-L" + sdk["toolchainSwift"]["path"], "-L" + sdk["sdkSwift"]["path"],
                "-framework", "Network", "-framework", "Foundation", "-o", str(executable)], diagnostics=True)
            row["executable"] = macho(read(executable, PRODUCT_LIMIT), target, 2, (18 << 16) | (2 << 8))
            row["status"] = "LINKED_NOT_EXECUTED"
        for name, digest in self.report["inputs"].items():
            require(sha256(read(self.root / name, 16 * MIB)) == digest, "admission source input changed")
        self.guard()
        self.report["status"] = "ADMITTED_LINK_ONLY"
        return self.report


def admit(root: Path, directory: Path, command) -> dict:
    """Run after genuine mDNS admission, before custody/writer, on mac14 only.

    The callback must return a finalized Runtime.Command or raise. There is no
    cache import, native execution, simulator boot, writer, or publication here.
    A failure keeps all files and a HOLD result; the controller still owns global
    cleanup/retirement and must not continue to the writer on that failure.
    """
    session = Session(root, directory, command)
    try:
        return session.execute()
    except BaseException as error:
        session.report.update(status="HOLD", error={"type": type(error).__name__, "message": str(error)})
        if isinstance(error, AdmissionError):
            error.report = session.report
        raise
    finally:
        session.guard()
        write(session.directory / "result.json", (json.dumps(session.report, sort_keys=True, indent=2,
              allow_nan=False) + "\n").encode())
