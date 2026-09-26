#!/usr/bin/env python3
"""Retain development sample apps from one ordinary hosted workflow build.

prepare runs before any build; package runs only after successful build AND
same-home Gradle stop steps. The workflow, not this helper, proves those outcomes.
Environment checks are consistency checks, not independent hosted attestation.
No builds, downloads, signing, app launches, installation or device tests occur here.
Use Python 3.9+ with -I -B -S. Inputs must remain exclusively owned during packaging.
"""

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
IDENTITY_SPEC = importlib.util.spec_from_file_location("sample_artifact_identity", ROOT / "scripts/sample_artifact_identity.py")
IDENTITY = importlib.util.module_from_spec(IDENTITY_SPEC)
IDENTITY_SPEC.loader.exec_module(IDENTITY)
REPOSITORY = "p2pKit/P2pKit"
IMAGE = "samples/p2p-sample-desktop-ui/build/compose/binaries/main/app"
INSTALLER_ROOT = "samples/p2p-sample-desktop-ui/build/compose/binaries/main"
INSTALLER_FORMATS = {"linux": "deb", "windows": "msi", "macos": "dmg"}
CLI = "samples/p2p-sample-desktop/build/install/p2p-sample-desktop"
APK = "samples/p2p-sample-android/build/outputs/apk/debug"
LICENSES = {"P2pKit-LICENSE": "LICENSE", "JmDNS-LICENSE": "library/p2p-transport-lan/vendor/jmdns/LICENSE",
            "JmDNS-NOTICE.txt": "library/p2p-transport-lan/vendor/jmdns/NOTICE.txt"}
MAX_FILES, MAX_FILE, MAX_TOTAL = 20000, 512 * 1024**2, 1024**3
CHUNK = 1024**2
SCOPE = {"kind": "DEVELOPMENT_SAMPLE_BUILD_ARTIFACTS", "productionSigning": "NOT_REQUESTED_OR_VERIFIED",
         "desktopInstaller": True, "installationTest": "NOT_PERFORMED", "signatureVerification": "NOT_PERFORMED",
         "appLaunch": "NOT_PERFORMED", "networkRuntime": "NOT_PERFORMED",
         "physicalDeviceQualification": "NOT_PERFORMED"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    require(path.is_file() and not path.is_symlink(), "Missing or linked JSON input")
    with path.open("rb") as stream:
        raw = stream.read(CHUNK + 1)
    require(0 < len(raw) <= CHUNK, "Oversized or empty JSON input")
    return json.loads(raw, object_pairs_hook=unique_pairs)


def write_new(path, value):
    with path.open("xb") as stream:
        stream.write((json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def physical_directory(path):
    require(path.is_absolute() and path.resolve(strict=True) == path, "Directory is not a physical absolute path")
    for part in (path, *path.parents):
        info = part.lstat()
        require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "Linked/reparse or non-directory ancestor")


def safe_name(value):
    require(isinstance(value, str) and 0 < len(value.encode("utf-8")) <= 4096 and
            not any(ord(char) < 32 or ord(char) == 127 or char in "\\:" for char in value), "Unsafe archive path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value and
            all(part not in ("", ".", "..") for part in value.split("/")), "Unsafe relative path")
    require(all(not part.endswith((".", " ")) and not re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)
                for part in path.parts), "Nonportable archive path")
    return value


def signature(path):
    info = path.lstat()
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode]


def hash_stream(stream, expected_size):
    digest, count = hashlib.sha256(), 0
    while True:
        block = stream.read(min(CHUNK, expected_size - count + 1))
        if not block:
            break
        count += len(block)
        require(count <= expected_size, "Input grew beyond its bound")
        digest.update(block)
    require(count == expected_size, "Truncated input")
    return digest.hexdigest()


def copy_stream(reader, writer, expected_size):
    count = 0
    while True:
        block = reader.read(min(CHUNK, expected_size - count + 1))
        if not block:
            break
        count += len(block)
        require(count <= expected_size, "Copy input grew beyond its bound")
        writer.write(block)
    require(count == expected_size, "Copy input was truncated")


def file_hash(path, limit=MAX_FILE):
    before = signature(path)
    require(stat.S_ISREG(before[-1]) and not getattr(path.lstat(), "st_file_attributes", 0) & 0x400 and
            0 <= before[2] <= limit, "Missing, linked, special or oversized file")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require([opened.st_dev, opened.st_ino] == before[:2], "File changed before read")
        digest = hash_stream(stream, before[2])
    require(signature(path) == before, "File changed during read")
    return {"bytes": before[2], "sha256": digest}


def git(root, *arguments):
    result = subprocess.run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(root),
                             *arguments], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    require(result.returncode == 0 and len(result.stdout) <= CHUNK, "Cannot inspect source identity")
    return result.stdout.strip()


def context(root, environment=None):
    env = os.environ if environment is None else environment
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            env.get("GITHUB_REPOSITORY") == REPOSITORY and env.get("GITHUB_SERVER_URL") == "https://github.com" and
            env.get("GITHUB_API_URL") == "https://api.github.com", "Not the expected ordinary hosted context")
    fields = {key: env.get("GITHUB_" + key.upper(), "") for key in
              ("sha", "event_name", "ref", "run_id", "run_attempt", "job", "workflow_ref", "workflow_sha")}
    for key in ("sha", "workflow_sha"):
        require(re.fullmatch(r"[0-9a-f]{40}", fields[key]), "Invalid source/workflow SHA")
    for key in ("run_id", "run_attempt"):
        require(re.fullmatch(r"[1-9][0-9]{0,19}", fields[key]), "Invalid run identity")
    require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,99}", fields["job"]), "Invalid job identity")
    event, ref = fields["event_name"], fields["ref"]
    require((event in ("push", "schedule") and ref == "refs/heads/main") or
            (event == "pull_request" and re.fullmatch(r"refs/pull/[1-9][0-9]*/merge", ref)) or
            (event == "workflow_dispatch" and re.fullmatch(r"refs/heads/[A-Za-z0-9_./-]+", ref)),
            "Unsupported event/ref")
    require(re.fullmatch(re.escape(REPOSITORY) + r"/\.github/workflows/[A-Za-z0-9_-]+\.ya?ml@refs/[A-Za-z0-9_./-]+",
                         fields["workflow_ref"]), "Invalid workflow reference")
    physical_directory(root)
    require(Path(env.get("GITHUB_WORKSPACE", "")) == root, "Checkout is not the workflow workspace")
    require(git(root, "rev-parse", "HEAD").decode("ascii") == fields["sha"], "Checkout SHA differs from event")
    tree = git(root, "rev-parse", "HEAD^{tree}").decode("ascii")
    require(re.fullmatch(r"[0-9a-f]{40}", tree) and
            not git(root, "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"),
            "Source is dirty or lacks a valid tree")
    system = platform.system()
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine().lower())
    require(system in ("Linux", "Windows", "Darwin") and arch and sys.maxsize > 2**32 and
            env.get("RUNNER_OS") == {"Linux": "Linux", "Windows": "Windows", "Darwin": "macOS"}[system] and
            env.get("RUNNER_ARCH") == {"x64": "X64", "arm64": "ARM64"}[arch], "Runner/Python architecture differs")
    translation = "NOT_APPLICABLE"
    if system == "Darwin":
        probe = subprocess.run(["/usr/sbin/sysctl", "-in", "sysctl.proc_translated"], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=10, check=False)
        require((probe.returncode == 0 and probe.stdout.strip() == b"0") or
                (probe.returncode == 1 and not probe.stdout.strip() and not probe.stderr.strip()),
                "Translated or indeterminate Mac process")
        translation = "NATIVE_0" if probe.returncode == 0 else "OPTIONAL_KEY_ABSENT_EXIT_1"
    return {"repository": REPOSITORY, "commit": fields.pop("sha"), "tree": tree, **fields,
            "canonicalVersion": IDENTITY.VERSION.repository_version(root)["canonicalVersion"],
            "platform": {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}[system],
            "architecture": arch, "osRelease": platform.release(), "python": platform.python_version(),
            "translation": translation}


def output_path(value, environment=None):
    env = os.environ if environment is None else environment
    parent = Path(env.get("RUNNER_TEMP", ""))
    physical_directory(parent)
    output = Path(value)
    require(output == parent / "p2pkit-sample-apps", "Output must be the dedicated RUNNER_TEMP directory")
    return output


def generated_roots(identity):
    return [IMAGE, CLI, INSTALLER_ROOT + "/" + INSTALLER_FORMATS[identity["platform"]]] + (
        [APK] if identity["platform"] == "linux" else [])


def prepare(root, output):
    identity = context(root)
    roots = generated_roots(identity)
    for relative in roots:
        require(not os.path.lexists(root / relative), "Intended generated application output already exists")
        for parent in (root / relative).parents:
            if os.path.lexists(parent):
                physical_directory(parent)
            if parent == root:
                break
    output.mkdir(mode=0o700)
    physical_directory(output)
    write_new(output / ".prepare.json", {"schema": 1, "context": identity, "root": str(root),
              "outputIdentity": signature(output)[:2], "generatedRoots": roots})


def inventory(root):
    physical_directory(root)
    root_mode = stat.S_IMODE(root.stat().st_mode)
    require(not root_mode & 0o7000, "Privileged/sticky application root")
    entries, total = [{"path": "", "mode": root_mode, "type": "directory"}], 0

    def walk_error(error):
        raise error

    for directory, directories, files in os.walk(root, followlinks=False, onerror=walk_error):
        for name in sorted(directories + files):
            path = Path(directory) / name
            relative = safe_name(path.relative_to(root).as_posix())
            info = path.lstat()
            mode = stat.S_IMODE(info.st_mode)
            require(not mode & 0o7000, "Privileged/sticky artifact mode")
            entry = {"path": relative, "mode": mode}
            if stat.S_ISLNK(info.st_mode):
                link = os.readlink(path)
                require(link and len(link.encode("utf-8")) <= 4096 and not os.path.isabs(link) and "\\" not in link and ":" not in link and
                        not any(ord(char) < 32 or ord(char) == 127 for char in link), "Unsafe symbolic link")
                require(root in path.resolve(strict=True).parents, "Escaping or root-alias symbolic link")
                entry.update(type="symlink", target=link)
            else:
                require(not getattr(info, "st_file_attributes", 0) & 0x400, "Reparse-point artifact")
                if stat.S_ISDIR(info.st_mode):
                    entry.update(type="directory")
                else:
                    require(stat.S_ISREG(info.st_mode), "Special artifact file")
                    entry.update(type="file", **file_hash(path))
                    total += entry["bytes"]
            entries.append(entry)
            require(len(entries) <= MAX_FILES and total <= MAX_TOTAL, "Application exceeds packaging bounds")
    require(any(entry["type"] == "file" and entry["bytes"] > 0 for entry in entries), "Empty application image")
    return sorted(entries, key=lambda item: item["path"])


def zip_input(path):
    # Bound central-directory allocation before ZipFile reads it; these sample
    # payloads do not require ZIP64, concatenated or multi-volume archives.
    # Python trusts ZIP64 overrides and iterates bytes, not the EOCD count, so
    # validate the actual records before it constructs any ZipInfo objects.
    size = path.stat().st_size
    with path.open("rb") as stream:
        tail_start = max(0, size - 65557)
        stream.seek(tail_start)
        tail = stream.read(65557)
        offset = tail.rfind(b"PK\x05\x06")
        require(offset >= 0 and len(tail) - offset >= 22, "Missing ZIP directory")
        _, disk, central_disk, count_here, count, central_bytes, central_offset, comment = struct.unpack_from(
            "<4s4H2LH", tail, offset)
        end = tail_start + offset
        if end >= 20:
            stream.seek(end - 20)
            require(stream.read(4) != b"PK\x06\x07", "ZIP64 locator is not supported")
        require(disk == central_disk == 0 and count_here == count and count <= MAX_FILES and
                central_bytes <= 16 * CHUNK and len(tail) - offset == 22 + comment and
                central_offset + central_bytes == end, "Unsupported/oversized ZIP directory extent")
        stream.seek(central_offset)
        for _ in range(count):
            require(stream.tell() + 46 <= end, "ZIP central record count exceeds its extent")
            header = stream.read(46)
            require(len(header) == 46 and header[:4] == b"PK\x01\x02", "Malformed ZIP central record")
            compressed, expanded = struct.unpack_from("<LL", header, 20)
            name_bytes, extra_bytes, comment_bytes, disk_start = struct.unpack_from("<4H", header, 28)
            local_offset = struct.unpack_from("<L", header, 42)[0]
            require(disk_start == 0 and compressed != 0xFFFFFFFF and expanded != 0xFFFFFFFF and
                    local_offset < central_offset and stream.tell() + name_bytes + extra_bytes + comment_bytes <= end,
                    "Unsupported ZIP64/multivolume or invalid ZIP record extent")
            stream.seek(name_bytes, 1)
            extra = stream.read(extra_bytes)
            require(len(extra) == extra_bytes, "Truncated ZIP extra fields")
            position = 0
            while position < len(extra):
                require(position + 4 <= len(extra), "Truncated ZIP extra field header")
                kind, length = struct.unpack_from("<HH", extra, position)
                require(kind != 1 and position + 4 + length <= len(extra), "ZIP64 or truncated ZIP extra field")
                position += 4 + length
            stream.seek(comment_bytes, 1)
        require(stream.tell() == end, "ZIP central record count differs from actual records")
    return zipfile.ZipFile(path)


def verify_archive(path, entries, prefix):
    expected = {safe_name(prefix + ("/" + entry["path"] if entry["path"] else "")): entry for entry in entries}
    seen = set()
    zipped = path.suffix == ".zip"
    with (zip_input(path) if zipped else tarfile.open(path, "r:gz")) as archive:
        for item in archive.infolist() if zipped else archive:
            name = item.filename.rstrip("/") if zipped else item.name
            safe_name(name)
            require(name in expected and name not in seen, "Unexpected or duplicate archive entry")
            seen.add(name)
            expected_entry = expected[name]
            mode = (item.external_attr >> 16) if zipped else item.mode
            if zipped:
                require(not item.flag_bits & 1 and stat.S_IFMT(mode) in (stat.S_IFDIR, stat.S_IFLNK, stat.S_IFREG),
                        "Encrypted or special archive entry")
            kind = ("directory" if item.is_dir() else "symlink" if stat.S_ISLNK(mode) else "file") if zipped else (
                "directory" if item.isdir() else "symlink" if item.issym() else "file" if item.isfile() else "special")
            require(kind == expected_entry["type"] and stat.S_IMODE(mode) == expected_entry["mode"],
                    "Archive type or mode differs")
            if kind == "file":
                require((item.file_size if zipped else item.size) == expected_entry["bytes"], "Archive size differs")
                with (archive.open(item) if zipped else archive.extractfile(item)) as stream:
                    require(hash_stream(stream, expected_entry["bytes"]) == expected_entry["sha256"], "Archive payload differs")
            elif kind == "symlink":
                if zipped:
                    require(item.file_size == len(expected_entry["target"].encode("utf-8")), "Archive link size differs")
                target = archive.read(item).decode("utf-8") if zipped else item.linkname
                require(target == expected_entry["target"], "Archive link differs")
            else:
                require((item.file_size if zipped else item.size) == 0, "Archive directory has a payload")
    require(seen == set(expected), "Archive entries are missing")


def archive_image(source, destination, entries):
    prefix = safe_name(source.name)
    if destination.suffix == ".zip":
        with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for entry in entries:
                name = prefix + ("/" + entry["path"] if entry["path"] else "") + ("/" if entry["type"] == "directory" else "")
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = ({"file": stat.S_IFREG, "directory": stat.S_IFDIR,
                                       "symlink": stat.S_IFLNK}[entry["type"]] | entry["mode"]) << 16
                if entry["type"] == "file":
                    with (source / entry["path"]).open("rb") as reader, archive.open(info, "w") as writer:
                        copy_stream(reader, writer, entry["bytes"])
                else:
                    archive.writestr(info, entry.get("target", "").encode("utf-8"))
    else:
        with destination.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for entry in entries:
                    info = tarfile.TarInfo(prefix + ("/" + entry["path"] if entry["path"] else ""))
                    info.mode = entry["mode"]
                    info.type = {"file": tarfile.REGTYPE, "directory": tarfile.DIRTYPE,
                                 "symlink": tarfile.SYMTYPE}[entry["type"]]
                    if entry["type"] == "file":
                        info.size = entry["bytes"]
                        with (source / entry["path"]).open("rb") as reader:
                            archive.addfile(info, reader)
                    else:
                        info.linkname = entry.get("target", "")
                        archive.addfile(info)
    require(inventory(source) == entries, "Application changed during packaging")
    verify_archive(destination, entries, prefix)
    return {"file": destination.name, **file_hash(destination, MAX_TOTAL + 32 * CHUNK), "entries": entries}


def native_architectures(path, system):
    require(path.is_file(), "Missing native launcher or runtime VM")
    size = path.stat().st_size
    with path.open("rb") as stream:
        header = stream.read(64)
        if system == "linux":
            require(len(header) == 64 and header[:5] == b"\x7fELF\x02" and header[5] in (1, 2), "Not a 64-bit ELF image")
            cpu = int.from_bytes(header[18:20], "little" if header[5] == 1 else "big")
            result = [{62: "x64", 183: "arm64"}.get(cpu)]
        elif system == "windows":
            require(len(header) == 64 and header[:2] == b"MZ", "Not a PE image")
            offset = int.from_bytes(header[60:64], "little")
            require(64 <= offset <= min(size - 26, 65536), "Invalid PE header offset")
            stream.seek(offset)
            pe = stream.read(26)
            require(pe[:4] == b"PE\0\0" and pe[24:26] == b"\x0b\x02", "Not a 64-bit PE image")
            result = [{0x8664: "x64", 0xAA64: "arm64"}.get(int.from_bytes(pe[4:6], "little"))]
        else:
            endian = {b"\xcf\xfa\xed\xfe": "little", b"\xfe\xed\xfa\xcf": "big"}.get(header[:4])
            cpus = []
            if endian:
                cpus = [int.from_bytes(header[4:8], endian)]
            else:
                require(header[:4] in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"), "Not a supported Mach-O image")
                count = int.from_bytes(header[4:8], "big")
                require(1 <= count <= 8, "Invalid fat Mach-O architecture count")
                width = 20 if header[:4] == b"\xca\xfe\xba\xbe" else 32
                stream.seek(8)
                data = stream.read(width * count)
                require(len(data) == width * count, "Truncated fat Mach-O header")
                ranges = []
                for index in range(count):
                    record = data[index * width:(index + 1) * width]
                    cpu = int.from_bytes(record[:4], "big")
                    length_width = 4 if width == 20 else 8
                    offset = int.from_bytes(record[8:8 + length_width], "big")
                    length = int.from_bytes(record[8 + length_width:8 + 2 * length_width], "big")
                    require(offset >= 8 + width * count and length >= 32 and offset + length <= size and
                            all(offset + length <= start or offset >= end for start, end in ranges), "Invalid Mach-O slice extent")
                    stream.seek(offset)
                    thin = stream.read(8)
                    slice_endian = {b"\xcf\xfa\xed\xfe": "little", b"\xfe\xed\xfa\xcf": "big"}.get(thin[:4])
                    require(slice_endian and int.from_bytes(thin[4:8], slice_endian) == cpu, "Fat Mach-O slice differs")
                    ranges.append((offset, offset + length))
                    cpus.append(cpu)
            result = [{0x1000007: "x64", 0x100000C: "arm64"}.get(cpu) for cpu in cpus]
    require(result and None not in result and len(result) == len(set(result)), "Unknown/duplicate native architecture")
    return sorted(result)


def desktop_layout(image, cli, identity):
    system, arch = identity["platform"], identity["architecture"]
    app, runtime, launcher, vm = {
        "windows": ("app", "runtime", "P2pKit Sample.exe", "bin/server/jvm.dll"),
        "linux": ("lib/app", "lib/runtime", "bin/P2pKit Sample", "lib/server/libjvm.so"),
        "macos": ("Contents/app", "Contents/runtime/Contents/Home", "Contents/MacOS/P2pKit Sample", "lib/server/libjvm.dylib"),
    }[system]
    inspected = {}
    for label, path in (("launcher", image / launcher), ("runtimeVm", image / runtime / vm)):
        require(image in path.resolve(strict=True).parents, "Native binary escapes application")
        inspected[label] = native_architectures(path, system)
        require(arch in inspected[label], "Native binary does not match runner architecture")
    runtime_java = image / runtime / "bin" / ("java.exe" if system == "windows" else "java")
    inspected["runtimeJava"] = native_architectures(runtime_java, system) if runtime_java.exists() else None
    require(inspected["runtimeJava"] is None or arch in inspected["runtimeJava"], "Bundled Java launcher architecture differs")
    require(system == "windows" or (image / launcher).stat().st_mode & 0o111, "Application launcher is not executable")
    release = image / runtime / "release"
    require(release.is_file() and release.stat().st_size <= CHUNK, "Missing/oversized bundled runtime release metadata")
    fields = unique_pairs(re.findall(r'^([A-Z_]+)="([^"\r\n]*)"$', release.read_text("utf-8"), re.MULTILINE))
    require(fields.get("JAVA_VERSION"), "Bundled runtime version absent")
    release_arch = fields.get("OS_ARCH")
    if release_arch:
        require({"amd64": "x64", "x86_64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(release_arch) == arch,
                "Bundled runtime release architecture differs")
    config = image / app / "P2pKit Sample.cfg"
    require(config.is_file() and config.stat().st_size <= CHUNK and
            re.search(r"(?m)^app\.mainclass=dev\.p2pkit\.sample\.desktop\.ui\.MainKt\s*$", config.read_text("utf-8")),
            "Wrong/missing packaged application main class")
    jars = inspect_jars(image / app, "dev/p2pkit/sample/desktop/ui/MainKt.class")
    cli_launcher = cli / "bin" / ("p2p-sample-desktop.bat" if system == "windows" else "p2p-sample-desktop")
    require(cli_launcher.is_file() and cli_launcher.stat().st_size <= CHUNK and
            "dev.p2pkit.sample.desktop.MainKt" in cli_launcher.read_text("utf-8"),
            "CLI distribution launcher/libraries absent")
    inspect_jars(cli / "lib", "dev/p2pkit/sample/desktop/MainKt.class")
    require(system == "windows" or cli_launcher.stat().st_mode & 0o111, "CLI launcher is not executable")
    return {**inspected, "javaVersion": fields["JAVA_VERSION"], "releaseArchitecture": release_arch,
            "embeddedIdentity": IDENTITY.jar_identity(image / app, identity["canonicalVersion"], identity["commit"], zip_input),
            "jarCount": jars, "cliRequiresExternalJava": "17+", "layoutOnlyNotRuntimeExecution": True}


def inspect_jars(directory, main_class):
    jars, mains = list(directory.glob("*.jar")), 0
    require(0 < len(jars) <= 1024, "Application JARs absent or excessive")
    for path in jars:
        with zip_input(path) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)), "Duplicate JAR entry")
            if main_class in names:
                with archive.open(main_class) as stream:
                    require(stream.read(4) == b"\xca\xfe\xba\xbe", "Packaged main class is not a class file")
                mains += 1
    require(mains == 1, "Missing or ambiguous packaged main class")
    return len(jars)


def copy_checked(source, destination, limit=MAX_FILE):
    before = file_hash(source, limit)
    with source.open("rb") as reader, destination.open("xb") as writer:
        copy_stream(reader, writer, before["bytes"])
    require(file_hash(source, limit) == before == file_hash(destination, limit), "Copied file differs")
    return {"file": destination.name, **before}


def desktop_installer(root, destination, identity):
    kind = INSTALLER_FORMATS[identity["platform"]]
    directory = root / INSTALLER_ROOT / kind
    physical_directory(directory)
    files = list(directory.glob("*." + kind))
    require(len(files) == 1, "Missing or ambiguous native installer")
    name = "desktop-installer-" + identity["platform"] + "-" + identity["architecture"] + "-" + identity["commit"][:12] + "." + kind
    artifact = copy_checked(files[0], destination / name)
    require(artifact["bytes"] >= 512, "Truncated native installer")
    with (destination / name).open("rb") as stream:
        if kind == "dmg":
            stream.seek(-512, 2)
            valid = stream.read(8) == b"koly\x00\x00\x00\x04"
        else:
            valid = stream.read(8) == {"msi": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "deb": b"!<arch>\n"}[kind]
    require(valid, "Native installer container header differs")
    metadata = IDENTITY.inspect_native(destination / name, identity["platform"], identity["canonicalVersion"],
                                       identity["commit"], zip_input)
    require(file_hash(destination / name) == {key: artifact[key] for key in ("bytes", "sha256")},
            "Installer changed during native metadata inspection")
    return {**artifact, "nativeMetadata": metadata}


def android_artifact(root, destination, identity):
    directory = root / APK
    physical_directory(directory)
    metadata_hash = file_hash(directory / "output-metadata.json", CHUNK)
    metadata = read_json(directory / "output-metadata.json")
    require(isinstance(metadata, dict) and metadata.get("applicationId") == "dev.p2pkit.sample.android" and
            metadata.get("variantName") == "debug" and isinstance(metadata.get("artifactType"), dict) and
            metadata["artifactType"].get("type") == "APK" and
            isinstance(metadata.get("elements"), list) and len(metadata["elements"]) == 1, "Wrong AGP APK metadata")
    item = metadata["elements"][0]
    require(isinstance(item, dict), "Malformed AGP output entry")
    name = safe_name(item.get("outputFile"))
    expected = IDENTITY.VERSION.version_fields(identity["canonicalVersion"])
    require("/" not in name and name.endswith(".apk") and item.get("type") == "SINGLE" and item.get("filters") == [] and
            type(item.get("versionCode")) is int and item["versionCode"] == expected["androidVersionCode"] and
            item.get("versionName") == expected["canonicalVersion"],
            "Ambiguous/split APK or changed sample version")
    require(sorted(path.name for path in directory.glob("*.apk")) == [name], "Missing or ambiguous APK outputs")
    artifact = copy_checked(directory / name, destination / name)
    require(artifact["bytes"] > 0, "Empty APK")
    with zip_input(destination / name) as archive:
        entries, total = {}, 0
        for entry in archive.infolist():
            safe_name(entry.filename.rstrip("/"))
            require(entry.filename not in entries and not entry.flag_bits & 1 and
                    not stat.S_ISLNK(entry.external_attr >> 16) and entry.file_size <= MAX_FILE, "Unsafe APK entry")
            entries[entry.filename] = entry
            total += entry.file_size
            require(total <= MAX_TOTAL, "APK contents exceed bound")
        require(all(name in entries and entries[name].file_size > 0 for name in ("AndroidManifest.xml", "classes.dex")),
                "APK lacks manifest or executable DEX")
        require(archive.testzip() is None, "APK CRC verification failed")
        actual = IDENTITY.inspect_apk(archive, identity["canonicalVersion"], identity["commit"])
    require(file_hash(directory / "output-metadata.json", CHUNK) == metadata_hash, "AGP metadata changed during inspection")
    return {"artifact": artifact, "agpMetadata": {"applicationId": metadata["applicationId"], "variant": "debug",
            "versionCode": item["versionCode"], "versionName": item["versionName"]},
            "apkInspection": {**actual, "signerIdentity": "NOT_VERIFIED"},
            "metadataFile": metadata_hash}


def finish_manifest(root, directory, identity, payload):
    notices = directory / "licenses"
    notices.mkdir()
    for name, relative in LICENSES.items():
        copy_checked(root / relative, notices / name, CHUNK)
    write_new(directory / "manifest.json", {"schema": 3, "sourceAndRun": identity, "scope": SCOPE,
              "versionBinding": IDENTITY.VERSION.version_fields(identity["canonicalVersion"]), **payload})
    lines = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            lines.append(file_hash(path, MAX_TOTAL + 32 * CHUNK)["sha256"] + "  " + path.relative_to(directory).as_posix())
    with (directory / "checksums.sha256").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")


def package(root, output):
    physical_directory(output)
    prepared = read_json(output / ".prepare.json")
    identity = context(root)
    require(prepared == {"schema": 1, "context": identity, "root": str(root), "outputIdentity": signature(output)[:2],
                         "generatedRoots": generated_roots(identity)},
            "Prepare identity differs from current source/run/output")
    require(set(path.name for path in output.iterdir()) == {".prepare.json"}, "Output is not an unused prepared directory")
    images = root / IMAGE
    physical_directory(images)
    name = "P2pKit Sample.app" if identity["platform"] == "macos" else "P2pKit Sample"
    require([path.name for path in images.iterdir()] == [name], "Missing or ambiguous Desktop app image")
    image, cli = images / name, root / CLI
    image_entries, cli_entries = inventory(image), inventory(cli)
    inspected = desktop_layout(image, cli, identity)
    stage = output / ".packaging"
    stage.mkdir(mode=0o700)
    try:
        desktop = stage / "desktop"
        desktop.mkdir()
        suffix = ".zip" if identity["platform"] == "windows" else ".tar.gz"
        label = identity["platform"] + "-" + identity["architecture"] + "-" + identity["commit"][:12]
        artifacts = [archive_image(source, desktop / (kind + "-" + label + suffix), entries) for source, kind, entries in
                     ((image, "desktop-ui", image_entries), (cli, "desktop-cli", cli_entries))]
        artifacts.append(desktop_installer(root, desktop, identity))
        finish_manifest(root, desktop, identity, {"artifacts": artifacts, "layoutInspection": inspected,
                        "installerInspection": "Native version metadata and byte hashes; not installed or signature-verified"})
        if identity["platform"] == "linux":
            android = stage / "android"
            android.mkdir()
            finish_manifest(root, android, identity, android_artifact(root, android, identity))
        require(context(root) == identity, "Source/run changed during packaging")
        for directory in stage.iterdir():
            directory.rename(output / directory.name)
        write_new(output / ".complete.json", {"schema": 1, "context": identity, "scope": SCOPE})
    finally:
        shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "package"))
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    try:
        output = output_path(arguments.output)
        {"prepare": prepare, "package": package}[arguments.command](ROOT, output)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, UnicodeError, subprocess.SubprocessError,
            zipfile.BadZipFile, tarfile.TarError) as error:
        print("Sample app packaging failed: " + type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 1
    print("Sample app " + arguments.command + " complete; no runtime or release qualification claimed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
