#!/usr/bin/env python3
"""Read actual APK/MSI/DMG/DEB metadata without installing or launching apps.

Only packaging on the native producer calls the OS readers. Synthetic parser
tests are not native package qualification. No metadata comes from a Release title.
"""

import ctypes
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import struct
import subprocess
import tarfile
import tempfile
import threading


SPEC = importlib.util.spec_from_file_location("application_release_version", Path(__file__).with_name("application_release_version.py"))
VERSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERSION)
LIMIT = 8 * 1024**2
PAYLOAD_LIMIT = 512 * 1024**2
STREAM_LIMIT = 1024**3
MAIN_CLASS = "dev/p2pkit/sample/desktop/ui/MainKt.class"


def need(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    values = {}
    for key, value in pairs:
        need(key not in values, "Duplicate artifact identity field")
        values[key] = value
    return values


def embedded(raw, version, source):
    need(0 < len(raw) <= 4096, "Missing/oversized embedded application identity")
    value = json.loads(raw, object_pairs_hook=unique)
    need(value == VERSION.embedded_identity(version, source), "Embedded application source/version differs")
    return value


def jar_identity(directory, version, source, zip_input):
    found = []
    for jar in directory.glob("*.jar"):
        need(jar.is_file() and not jar.is_symlink(), "Linked/nonregular application JAR")
        with zip_input(jar) as archive:
            matches = [x for x in archive.infolist() if x.filename == "p2pkit-release.json"]
            mains = [x for x in archive.infolist() if x.filename == MAIN_CLASS]
            need(len(matches) <= 1 and len(mains) <= 1 and bool(matches) == bool(mains),
                 "Identity must be in the same unique application main-class JAR")
            if matches:
                need(matches[0].file_size <= 4096 and not matches[0].flag_bits & 1, "Invalid embedded JAR identity")
                found.append(embedded(archive.read(matches[0]), version, source))
    need(len(found) == 1, "Missing/ambiguous application JAR identity")
    return found[0]


def apk_manifest(raw):
    """Bounded Android binary XML reader for the real manifest root attributes."""
    need(8 <= len(raw) <= LIMIT, "APK manifest size outside bound")

    def integer(offset, size=4):
        need(0 <= offset and offset + size <= len(raw), "Truncated APK manifest")
        return int.from_bytes(raw[offset:offset + size], "little")

    need(integer(0, 2) == 3 and integer(2, 2) == 8 and integer(4) == len(raw), "Not Android binary XML")
    strings, resources, result = None, None, None
    position, depth = 8, 0
    while position < len(raw):
        kind, header, length = integer(position, 2), integer(position + 2, 2), integer(position + 4)
        end = position + length
        need(8 <= header <= length and end <= len(raw) and length % 4 == 0, "Invalid Android XML chunk")
        if kind == 1:
            need(strings is None and header >= 28, "Duplicate/invalid XML string pool")
            count, styles, flags = integer(position + 8), integer(position + 12), integer(position + 16)
            start, styles_start = integer(position + 20), integer(position + 24)
            need(count <= 65536 and header + 4 * (count + styles) <= start < length and
                 (styles_start == 0 or start <= styles_start <= length), "Invalid XML string pool extent")
            limit = position + (styles_start or length)
            strings, decoded_bytes = [], 0

            def encoded_length(offset, width):
                need(offset + width <= limit, "Truncated XML string length")
                first = integer(offset, width)
                if first & (1 << (width * 8 - 1)):
                    need(offset + 2 * width <= limit, "Truncated XML string length")
                    return ((first & ((1 << (width * 8 - 1)) - 1)) << (width * 8)) | integer(offset + width, width), offset + 2 * width
                return first, offset + width

            for index in range(count):
                offset = position + start + integer(position + header + 4 * index)
                need(position + start <= offset < limit, "XML string offset escapes pool")
                utf16_length, offset = encoded_length(offset, 1 if flags & 0x100 else 2)
                if flags & 0x100:
                    size, offset = encoded_length(offset, 1)
                    need(offset + size < limit and raw[offset + size] == 0, "Truncated UTF8 XML string")
                    decoded_bytes += size * 4
                    need(decoded_bytes <= LIMIT, "XML decoded string pool exceeds bound")
                    text = raw[offset:offset + size].decode("utf-8")
                    need(len(text.encode("utf-16-le")) // 2 == utf16_length, "XML string character length differs")
                else:
                    size = utf16_length * 2
                    need(offset + size + 2 <= limit and raw[offset + size:offset + size + 2] == b"\0\0",
                         "Truncated UTF16 XML string")
                    decoded_bytes += size * 2
                    need(decoded_bytes <= LIMIT, "XML decoded string pool exceeds bound")
                    text = raw[offset:offset + size].decode("utf-16-le")
                strings.append(text)
        elif kind == 0x180:
            need(resources is None and strings is not None and header == 8, "Invalid XML resource map")
            resources = [integer(offset) for offset in range(position + header, end, 4)]
            need(len(resources) <= len(strings), "XML resource map exceeds string pool")
        elif kind == 0x102:
            need(strings is not None and header == 16 and length >= 36, "Invalid XML start element")

            def string(index):
                need(index < len(strings), "Invalid XML string index")
                return strings[index]

            name = string(integer(position + 20))
            if depth == 0:
                need(result is None and name == "manifest" and integer(position + 16) == 0xffffffff,
                     "Missing/duplicate manifest root")
                attr_start, attr_size, count = integer(position + 24, 2), integer(position + 26, 2), integer(position + 28, 2)
                need(attr_start >= 20 and attr_size == 20 and count <= 1024 and
                     position + 16 + attr_start + count * attr_size <= end, "Invalid manifest attributes")
                result, seen = {}, set()
                for index in range(count):
                    offset = position + 16 + attr_start + index * attr_size
                    ns_index, key_index, raw_index = integer(offset), integer(offset + 4), integer(offset + 8)
                    namespace = None if ns_index == 0xffffffff else string(ns_index)
                    key = string(key_index)
                    need((namespace, key) not in seen and integer(offset + 12, 2) == 8, "Duplicate/invalid manifest attribute")
                    seen.add((namespace, key))
                    value_type, value = raw[offset + 15], integer(offset + 16)
                    if namespace is None and key == "package":
                        need(value_type == 3, "Manifest package is not a string")
                        result["applicationId"] = string(value)
                        need(raw_index == 0xffffffff or string(raw_index) == result["applicationId"],
                             "Raw/typed Android package differs")
                    if namespace == "http://schemas.android.com/apk/res/android":
                        need(key != "versionCodeMajor", "Unexpected extended Android version code")
                        if key in ("versionCode", "versionName"):
                            need(resources is not None and key_index < len(resources) and resources[key_index] ==
                                 {"versionCode": 0x0101021b, "versionName": 0x0101021c}[key], "Android attribute resource ID differs")
                            if key == "versionCode":
                                need(value_type in (0x10, 0x11), "Manifest versionCode is not a literal integer")
                                result[key] = value
                            else:
                                need(value_type == 3, "Manifest versionName is not a literal string")
                                result[key] = string(value)
                            if raw_index != 0xffffffff:
                                need(string(raw_index) == str(result[key]), "Raw/typed Android version differs")
            depth += 1
        elif kind == 0x103:
            need(depth > 0 and header == 16 and length == 24, "Invalid XML end element")
            depth -= 1
        else:
            need(kind in (0x100, 0x101), "Unexpected Android XML chunk type")
        position = end
    need(depth == 0 and result is not None and set(result) == {"applicationId", "versionCode", "versionName"},
         "Incomplete Android manifest version identity")
    return result


def inspect_apk(archive, version, source):
    manifest = archive.getinfo("AndroidManifest.xml")
    identity = archive.getinfo("assets/p2pkit-release.json")
    need(manifest.file_size <= LIMIT and identity.file_size <= 4096, "APK identity inputs exceed bounds")
    actual = apk_manifest(archive.read(manifest))
    expected = VERSION.version_fields(version)
    need(actual == {"applicationId": "dev.p2pkit.sample.android", "versionCode": expected["androidVersionCode"],
                    "versionName": version}, "Actual APK manifest version/package differs")
    return {"binaryManifest": actual, "embeddedIdentity": embedded(archive.read(identity), version, source)}


def native_fields(system, fields, version):
    expected = VERSION.version_fields(version)
    if system == "linux":
        need(fields.get("Package") == "p2pkit-sample" and fields.get("Version") == expected["debianVersion"] and
             fields.get("Architecture") == "amd64", "Actual DEB package/version/architecture differs")
    elif system == "windows":
        need(fields.get("ProductName") == "P2pKit Sample" and fields.get("ProductVersion") == expected["nativeVersion"] and
             isinstance(fields.get("Template"), str) and re.fullmatch(r"x64;[0-9]+(?:,[0-9]+)*", fields["Template"]),
             "Actual MSI product/version/architecture differs")
    elif system == "macos":
        need(fields.get("CFBundleShortVersionString") == expected["nativeVersion"] and
             fields.get("CFBundleVersion") == expected["nativeVersion"], "Actual DMG application versions differ")
    else:
        raise ValueError("Unsupported native package platform")
    return fields


def run(command, timeout=45):
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    captured, errors = [bytearray(), bytearray()], []

    def read(stream, index, limit):
        try:
            while True:
                data = stream.read(min(65536, limit - len(captured[index]) + 1))
                if not data:
                    break
                need(len(captured[index]) + len(data) <= limit, "Native metadata output exceeds bound")
                captured[index].extend(data)
        except (OSError, ValueError) as error:
            errors.append(error)
            if process.poll() is None:
                process.kill()

    readers = [threading.Thread(target=read, args=(stream, index, limit), daemon=True)
               for index, (stream, limit) in enumerate(((process.stdout, LIMIT), (process.stderr, 65536)))]
    for reader in readers:
        reader.start()
    try:
        need(process.wait(timeout=timeout) == 0, "Native package metadata reader failed")
        for reader in readers:
            reader.join(timeout=5)
        need(not errors and not any(reader.is_alive() for reader in readers), "Native metadata capture failed to close")
        return bytes(captured[0])
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        for reader in readers:
            reader.join(timeout=5)
        process.stdout.close()
        process.stderr.close()


@contextmanager
def msi_database(path):
    """Read-only Windows Installer database/summary API; never msiexec."""
    from ctypes import wintypes
    api = ctypes.WinDLL("msi", use_last_error=True)
    uint, handle = wintypes.UINT, wintypes.UINT
    signatures = {
        "MsiOpenDatabaseW": [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(handle)],
        "MsiDatabaseOpenViewW": [handle, wintypes.LPCWSTR, ctypes.POINTER(handle)],
        "MsiViewExecute": [handle, handle], "MsiViewFetch": [handle, ctypes.POINTER(handle)],
        "MsiRecordGetStringW": [handle, uint, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)],
        "MsiRecordReadStream": [handle, uint, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)],
        "MsiGetSummaryInformationW": [handle, wintypes.LPCWSTR, uint, ctypes.POINTER(handle)],
        "MsiSummaryInfoGetPropertyW": [handle, uint, ctypes.POINTER(uint), ctypes.POINTER(ctypes.c_int),
                                      ctypes.POINTER(wintypes.FILETIME), wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)],
        "MsiCloseHandle": [handle],
    }
    for name, arguments in signatures.items():
        getattr(api, name).argtypes = arguments
        getattr(api, name).restype = uint
    database = handle()
    need(api.MsiOpenDatabaseW(str(path), None, ctypes.byref(database)) == 0, "Cannot open MSI read-only")
    try:
        yield api, database
    finally:
        api.MsiCloseHandle(database)


@contextmanager
def msi_records(api, database, query):
    handle = ctypes.c_uint
    view = handle()
    need(api.MsiDatabaseOpenViewW(database, query, ctypes.byref(view)) == 0, "Cannot query MSI database")
    try:
        need(api.MsiViewExecute(view, 0) == 0, "Cannot execute MSI read-only query")
        def rows():
            count = 0
            while True:
                record = handle()
                status = api.MsiViewFetch(view, ctypes.byref(record))
                if status == 259:
                    return
                need(status == 0, "MSI row read failed")
                try:
                    count += 1
                    need(count <= 20000, "MSI row count exceeds bound")
                    yield record
                finally:
                    api.MsiCloseHandle(record)
        iterator = rows()
        try:
            yield iterator
        finally:
            iterator.close()
    finally:
        api.MsiCloseHandle(view)


def msi_rows(api, database, query, columns):
    from ctypes import wintypes
    result = []
    with msi_records(api, database, query) as rows:
        for record in rows:
            fields = []
            for column in range(1, columns + 1):
                size, buffer = wintypes.DWORD(4096), ctypes.create_unicode_buffer(4096)
                need(api.MsiRecordGetStringW(record, column, buffer, ctypes.byref(size)) == 0, "Invalid MSI property length")
                fields.append(buffer.value)
            result.append(fields)
    return result


def msi_fields(api, database):
    from ctypes import wintypes
    fields = {}
    for name in ("ProductName", "ProductVersion"):
        rows = msi_rows(api, database, f"SELECT `Value` FROM `Property` WHERE `Property`='{name}'", 1)
        need(len(rows) == 1, "Missing/duplicate MSI property")
        fields[name] = rows[0][0]
    summary = wintypes.UINT()
    need(api.MsiGetSummaryInformationW(database, None, 0, ctypes.byref(summary)) == 0, "Missing MSI summary")
    try:
        kind, integer, stamp = wintypes.UINT(), ctypes.c_int(), wintypes.FILETIME()
        size, buffer = wintypes.DWORD(4096), ctypes.create_unicode_buffer(4096)
        need(api.MsiSummaryInfoGetPropertyW(summary, 7, ctypes.byref(kind), ctypes.byref(integer), ctypes.byref(stamp),
                                           buffer, ctypes.byref(size)) == 0 and kind.value == 30, "Invalid MSI template")
        fields["Template"] = buffer.value
        kind, integer, size = wintypes.UINT(), ctypes.c_int(), wintypes.DWORD(4096)
        need(api.MsiSummaryInfoGetPropertyW(summary, 15, ctypes.byref(kind), ctypes.byref(integer), ctypes.byref(stamp),
                                           buffer, ctypes.byref(size)) == 0 and kind.value == 3,
             "Missing MSI source-compression flags")
        fields["WordCount"] = integer.value
    finally:
        api.MsiCloseHandle(summary)
    return fields


def compressed_msi_file(attributes, word_count):
    need(attributes == "" or attributes.isdecimal(), "Invalid MSI file flags")
    flags = int(attributes or "0")
    need(type(word_count) is int and 0 <= word_count <= 0x7fffffff and 0 <= flags <= 0x7fff and
         not flags & 0x2000 and (flags & 0x4000 or word_count & 2),
         "MSI installer does not consume this compressed cabinet file")


def cabinet_member(path, key, expected_size):
    """Bound the exact CFFILE before expand.exe can write it; no external cabinet chain."""
    size = path.stat().st_size
    need(36 <= size <= PAYLOAD_LIMIT, "Invalid embedded cabinet size")
    with path.open("rb") as stream:
        header = stream.read(36)
        signature, reserved1, total, reserved2, files_offset, reserved3, minor, major, folders, files, flags, _, cabinet = \
            struct.unpack("<4s5I2B5H", header)
        need(signature == b"MSCF" and not (reserved1 or reserved2 or reserved3) and total == size and
             (major, minor) == (1, 3) and 0 < folders <= 20000 and 0 < files <= 20000 and
             flags in (0, 4) and cabinet == 0, "Unsupported/spanned/malformed embedded cabinet")
        folder_reserved = 0
        if flags & 4:
            reserve = stream.read(4)
            need(len(reserve) == 4, "Truncated cabinet reserve")
            header_reserved, folder_reserved, _ = struct.unpack("<HBB", reserve)
            stream.seek(header_reserved, 1)
        need(stream.tell() + folders * (8 + folder_reserved) <= files_offset < size, "Cabinet tables overlap")
        data_offsets = []
        for _ in range(folders):
            entry = stream.read(8)
            need(len(entry) == 8, "Truncated cabinet folder")
            data_offset, blocks, compression = struct.unpack("<IHH", entry)
            need(files_offset < data_offset < size and blocks > 0 and compression & 15 in (0, 1, 3),
                 "Invalid cabinet data folder")
            data_offsets.append(data_offset)
            stream.seek(folder_reserved, 1)
        stream.seek(files_offset)
        seen, matches = set(), 0
        for _ in range(files):
            entry = stream.read(16)
            need(len(entry) == 16, "Truncated cabinet file")
            expanded, offset, folder, _, _, _ = struct.unpack("<II4H", entry)
            name = bytearray()
            while True:
                char = stream.read(1)
                need(char and len(name) <= 4096 and stream.tell() <= min(data_offsets), "Invalid cabinet file name")
                if char == b"\0":
                    break
                name.extend(char)
            text = name.decode("utf-8")
            need(text.casefold() not in seen and folder < folders, "Duplicate/spanned cabinet file")
            seen.add(text.casefold())
            if text.casefold() == key.casefold():
                matches += 1
                need(text == key and expanded == expected_size and offset + expanded <= STREAM_LIMIT,
                     "Cabinet payload size/identity differs before expansion")
        need(matches == 1 and stream.tell() <= min(data_offsets), "Missing/overlapping cabinet payload")


def msi_payload(api, database, directory, word_count):
    """Extract only the application's data file from its embedded MSI cabinet."""
    from ctypes import wintypes
    files = msi_rows(api, database, "SELECT `File`,`FileName`,`Sequence`,`FileSize`,`Attributes` FROM `File`", 5)
    matches = [x for x in files if x[1].split("|")[-1].startswith("p2p-sample-desktop-ui-") and x[1].endswith(".jar")]
    need(len(matches) == 1, "Missing/ambiguous MSI application JAR")
    key, _, sequence, size, attributes = matches[0]
    compressed_msi_file(attributes, word_count)
    need(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,71}", key) and sequence.isdecimal() and size.isdecimal() and
         0 < int(size) <= PAYLOAD_LIMIT, "Invalid MSI application file record")
    media = msi_rows(api, database, "SELECT `LastSequence`,`Cabinet` FROM `Media` ORDER BY `DiskId`", 2)
    previous, selected = 0, []
    for last, cabinet in media:
        need(last.isdecimal() and previous < int(last), "Invalid MSI media sequence")
        if previous < int(sequence) <= int(last):
            selected.append(cabinet)
        previous = int(last)
    need(len(selected) == 1 and re.fullmatch(r"#[A-Za-z0-9_.-]{1,72}", selected[0]), "MSI must use one embedded payload cabinet")
    cabinet = directory / "payload.cab"
    with msi_records(api, database, f"SELECT `Data` FROM `_Streams` WHERE `Name`='{selected[0][1:]}'") as rows:
        seen = 0
        for record in rows:
            seen += 1
            need(seen == 1, "Duplicate MSI embedded cabinet")
            total = 0
            with cabinet.open("xb") as output:
                while True:
                    amount, buffer = wintypes.DWORD(1024**2), ctypes.create_string_buffer(1024**2)
                    need(api.MsiRecordReadStream(record, 1, buffer, ctypes.byref(amount)) == 0, "MSI cabinet read failed")
                    if not amount.value:
                        break
                    total += amount.value
                    need(total <= PAYLOAD_LIMIT, "MSI cabinet exceeds bound")
                    output.write(buffer.raw[:amount.value])
        need(seen == 1, "Missing embedded MSI cabinet")
    output = directory / "expanded"
    output.mkdir()
    cabinet_member(cabinet, key, int(size))
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetSystemDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    kernel.GetSystemDirectoryW.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel.GetSystemDirectoryW(buffer, len(buffer))
    need(0 < length < len(buffer), "Cannot locate native Windows system directory")
    run([str(Path(buffer.value) / "expand.exe"), str(cabinet), "-F:" + key, str(output)])
    path = output / key
    need([x.name for x in output.iterdir()] == [key] and path.is_file() and not path.is_symlink() and
         not getattr(path.lstat(), "st_file_attributes", 0) & 0x400 and path.stat().st_size == int(size),
         "MSI cabinet extraction differs from its exact data-file record")
    path.rename(output / "application.jar")
    return output


class LimitedReader:
    def __init__(self, stream):
        self.stream, self.count = stream, 0

    def read(self, size):
        need(0 <= size <= STREAM_LIMIT, "Unbounded DEB stream request")
        data = self.stream.read(min(size, STREAM_LIMIT - self.count + 1))
        self.count += len(data)
        need(self.count <= STREAM_LIMIT, "DEB expanded stream exceeds bound")
        return data


def deb_payload(stream, directory):
    found, count = 0, 0
    bounded = LimitedReader(stream)
    with tarfile.open(fileobj=bounded, mode="r|") as archive:
        for member in archive:
            count += 1
            need(count <= 20000, "DEB file count exceeds bound")
            name = member.name.removeprefix("./")
            need(not name.startswith("/") and ".." not in name.split("/"), "Unsafe DEB data path")
            if "/lib/app/" not in name or not name.rsplit("/", 1)[-1].startswith("p2p-sample-desktop-ui-") or not name.endswith(".jar"):
                continue
            found += 1
            need(found == 1 and member.isfile() and 0 < member.size <= PAYLOAD_LIMIT, "Missing/ambiguous/special DEB application JAR")
            with archive.extractfile(member) as source, (directory / "application.jar").open("xb") as output:
                remaining = member.size
                while remaining:
                    data = source.read(min(1024**2, remaining))
                    need(data, "Truncated DEB application JAR")
                    output.write(data)
                    remaining -= len(data)
    while bounded.read(1024**2):
        pass
    need(found == 1, "Missing DEB application JAR")


@contextmanager
def native_stream(command):
    # Data-only native reader: bounded bytes in LimitedReader, one fixed wall
    # timer, and confirmed child reaping on every return. No installer execution.
    need(os.name == "posix", "DEB data stream requires the native POSIX host")
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    expired = threading.Event()

    def retire():
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def timeout():
        expired.set()
        retire()  # Include dpkg-deb's decompressor; it can inherit the stdout pipe.

    timer = threading.Timer(45, timeout)
    timer.start()
    try:
        yield process.stdout
        need(process.wait(timeout=5) == 0 and not expired.is_set(), "Native package stream reader failed or timed out")
    finally:
        timer.cancel()
        retire()
        process.wait(timeout=5)
        process.stdout.close()
        timer.join()


def inspect_native(path, system, version, source, zip_input):
    if system in ("windows", "linux"):
        with tempfile.TemporaryDirectory(prefix="p2pkit-installer-readback-") as temporary:
            directory = Path(temporary).resolve(strict=True)
            if system == "windows":
                with msi_database(path) as (api, database):
                    fields = native_fields(system, msi_fields(api, database), version)
                    payload = msi_payload(api, database, directory, fields["WordCount"])
                reader = "MsiOpenDatabaseW/READONLY + embedded cabinet"
            else:
                raw = run(["dpkg-deb", "--field", str(path), "Package", "Version", "Architecture"]).decode("utf-8")
                fields = native_fields(system, unique(line.split(": ", 1) for line in raw.splitlines()), version)
                with native_stream(["dpkg-deb", "--fsys-tarfile", str(path)]) as stream:
                    deb_payload(stream, directory)
                reader, payload = "dpkg-deb control + data-only tar", directory
            return {"reader": reader, "fields": fields, "embeddedIdentity": jar_identity(payload, version, source, zip_input)}
    need(system == "macos", "Unsupported installer platform")
    # Never recursively delete a possibly still-mounted volume. A failed attach
    # or detach leaves this new owned directory for runner-level reconciliation.
    directory = Path(tempfile.mkdtemp(prefix="p2pkit-dmg-readback-")).resolve(strict=True)
    mount = directory / "mounted"
    mount.mkdir()
    try:
        raw = run(["/usr/bin/hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen", "-mountpoint", str(mount),
                   "-plist", str(path)])
        data = plistlib.loads(raw)
        need([x["mount-point"] for x in data.get("system-entities", []) if "mount-point" in x] == [str(mount)],
             "DMG mounted outside the owned read-only location")
        app = mount / "P2pKit Sample.app"
        for entry in (app, app / "Contents", app / "Contents/app"):
            need(entry.resolve(strict=True) == entry and entry.is_dir(), "Linked/missing DMG application ancestry")
        plist = app / "Contents/Info.plist"
        need(plist.is_file() and not plist.is_symlink() and plist.stat().st_size <= LIMIT, "Invalid DMG Info.plist")
        values = plistlib.loads(plist.read_bytes())
        fields = {key: values.get(key) for key in ("CFBundleShortVersionString", "CFBundleVersion")}
        identity = jar_identity(app / "Contents/app", version, source, zip_input)
        return {"reader": "hdiutil read-only / Info.plist", "fields": native_fields(system, fields, version),
                "embeddedIdentity": identity}
    finally:
        # Attempt even when attach failed: hdiutil can have mounted before its
        # response/timing failed. Nonzero detach is a failure, never an excuse
        # to traverse/delete the uncertain mount. Python retains primary cause.
        run(["/usr/bin/hdiutil", "detach", str(mount)], timeout=30)
        need(not os.path.ismount(mount), "DMG volume retirement unconfirmed")
        mount.rmdir()
        directory.rmdir()
