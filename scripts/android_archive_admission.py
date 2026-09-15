#!/usr/bin/env python3
"""Whole official Android archives -> installed bytes, never runtime certification.

`capture` is a genuine fresh HTTPS producer plus a streaming comparison. `admit`
requires that producer's terminal immutable receipt and rechecks its originals and
installed bytes. Neither accepts a caller's trusted/downloaded/passed assertion.
The operator must separately hold the shared host/Actions execution lease. This
module only owns the maintained same-state Gradle lease while beneath a command
leaf. It never installs, extracts, launches an SDK tool or removes a mismatch.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import stat
import struct
import subprocess
import sys
import time
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zlib

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import android_ui_controller as controller

MIB, GIB = 1024 ** 2, 1024 ** 3
CHUNK = 64 * 1024
JSON_LIMIT, HEADER_LIMIT, SMALL_LIMIT = 4 * MIB, 64 * 1024, 256 * 1024
METADATA_LIMIT, MEMBER_LIMIT, GRAPH_LIMIT = 16 * MIB, 4096, 8192
EXPANSION_LIMIT, FILE_LIMIT = 4 * GIB, 3 * GIB
# Archive-only policy; the dependency writer's separate 16 GiB admission is unchanged.
FLOOR, RESERVE = 8 * GIB, 3 * GIB
TOTAL_SECONDS, COMPARE_SECONDS = 1800, 300
IMAGE_PACKAGE = "system-images;android-37.0;google_apis_playstore_ps16k;arm64-v8a"
IMAGE_PATH = "system-images/android-37.0/google_apis_playstore_ps16k/arm64-v8a"
IMAGE_URL = ("https://dl.google.com/android/repository/sys-img/google_apis_playstore/"
             "arm64-v8a-playstore-ps16k-37.0_r05.zip")
EMULATOR_NAME = "emulator-darwin_aarch64-15507667.zip"
EMULATOR_URL = "https://redirector.gvt1.com/edgedl/android/repository/" + EMULATOR_NAME
PINS = {
    "image": {"url": IMAGE_URL, "bytes": 2216674212, "publisherSha256": None,
              "prefix": "arm64-v8a", "seconds": 900},
    "emulator": {"url": EMULATOR_URL, "bytes": 383903546,
                 "publisherSha256": "aebcd4dde29a4921d47e5e79b8c1ffece69a70f5b280d8dc7033ebaffa737072",
                 "prefix": "emulator", "seconds": 300},
}
# Names/sizes from the retained official r05 central directory, not a publisher
# digest. Fresh complete archive structure and every member still require proof.
IMAGE_MEMBERS = {
    "NOTICE.txt": 6623492, "VerifiedBootParams.textproto": 356, "advancedFeatures.ini": 844,
    "build.prop": 5629, "data/empty_data_disk": 107, "data/local.prop": 46,
    "data/misc/GoldfishSkinConfig": 783, "data/misc/emulator/config/radioconfig.xml": 1433,
    "data/misc/emulator/version.txt": 101,
    "data/misc/modem_simulator/etc/modem_simulator/files/numeric_operator.xml": 297,
    "data/misc/modem_simulator/iccprofile_for_carrierapitests.xml": 16537,
    "data/misc/modem_simulator/iccprofile_for_sim0.xml": 14647,
    "data/misc/modem_simulator/iccprofile_for_sim_tel_alaska.xml": 14474,
    "data/misc/pixel_10_pro_fold/devicestate/device_state_configuration.xml": 3290,
    "data/misc/pixel_10_pro_fold/display_settings.xml": 303,
    "data/misc/pixel_10_pro_fold/displayconfig/display_layout_configuration.xml": 1311,
    "data/misc/pixel_10_pro_fold/extra_feature.xml": 829,
    "data/misc/pixel_9_pro_fold/devicestate/device_state_configuration.xml": 3290,
    "data/misc/pixel_9_pro_fold/display_settings.xml": 303,
    "data/misc/pixel_9_pro_fold/displayconfig/display_layout_configuration.xml": 1311,
    "data/misc/pixel_9_pro_fold/extra_feature.xml": 829,
    "data/misc/pixel_fold/devicestate/device_state_configuration.xml": 3290,
    "data/misc/pixel_fold/display_settings.xml": 303,
    "data/misc/pixel_fold/displayconfig/display_layout_configuration.xml": 1311,
    "data/misc/pixel_fold/extra_feature.xml": 829,
    "encryptionkey.img": 18874368, "kernel-ranchu": 16205318, "kernel_cmdline.txt": 16,
    "ramdisk.img": 1564932, "source.properties": 427, "system.img": 2982150144, "vendor.img": 79691776,
}

Rejected, need = controller.Rejected, controller.need


class Budget:
    def __init__(self, seconds, disk=None):
        self.deadline = time.monotonic() + seconds
        self.disk, self.next_disk = disk, 0

    def __call__(self):
        now = time.monotonic()
        need(now < self.deadline, "Archive operation deadline")
        if self.disk is not None and now >= self.next_disk:
            need(shutil.disk_usage(self.disk).free >= FLOOR, "Separate free-space floor exhausted")
            self.next_disk = now + 1


def identity(info):
    return {key: getattr(info, "st_" + key) for key in
            ("dev", "ino", "mode", "nlink", "uid", "size", "mtime_ns", "ctime_ns")}


def physical(path, *, missing=False):
    need(path.is_absolute() and ".." not in path.parts, "Nonabsolute/parent input path")
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            need(missing, "Missing physical input")
            continue
        need(not stat.S_ISLNK(info.st_mode), "Linked physical input path")
    return path


@contextmanager
def original(path, limit):
    physical(path)
    before = identity(path.lstat())
    need(stat.S_ISREG(before["mode"]) and before["nlink"] == 1 and before["size"] <= limit,
         "Nonregular/aliased/oversized original")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        need(identity(os.fstat(stream.fileno())) == before, "Original changed before open")
        yield stream, before
        need(identity(os.fstat(stream.fileno())) == before, "Original changed during read")
    need(identity(path.lstat()) == before, "Original changed after read")


def exact(stream, length):
    need(type(length) is int and 0 <= length <= JSON_LIMIT, "Unbounded structural read")
    value = stream.read(length)
    need(len(value) == length, "Truncated archive structure")
    return value


def file_binding(path, limit, check, keep=False):
    digest, count, chunks = hashlib.sha256(), 0, []
    with original(path, limit) as (stream, before):
        while True:
            check()
            block = stream.read(min(CHUNK, limit - count + 1))
            if not block:
                break
            count += len(block)
            need(count <= limit, "Original grew beyond its bound")
            digest.update(block)
            if keep:
                need(count <= JSON_LIMIT, "Unbounded buffered original")
                chunks.append(block)
        need(count == before["size"], "Original length differs")
    return {"bytes": count, "sha256": digest.hexdigest()}, b"".join(chunks) if keep else None


def safe_name(raw, directory=False):
    name = raw.decode("ascii")
    need(0 < len(raw) <= 1024 and name.endswith("/") == directory, "Unsupported ZIP name/type")
    name = name[:-1] if directory else name
    parts = name.split("/")
    need(len(parts) <= 24 and all(re.fullmatch(r"[A-Za-z0-9._+@ -]{1,200}", part) and
         part not in (".", "..") and not part.endswith((" ", ".")) for part in parts), "Unsafe archive name")
    return name


def extra_fields(raw, central):
    """ZIP32 Unix timestamps/UIDs only; no path override, ZIP64 or encryption."""
    seen, offset = set(), 0
    while offset < len(raw):
        need(offset + 4 <= len(raw), "Truncated ZIP extra header")
        tag, length = struct.unpack_from("<HH", raw, offset)
        offset += 4
        need(tag in (0x5455, 0x7875) and tag not in seen and offset + length <= len(raw),
             "Unsupported/duplicate ZIP extra field")
        seen.add(tag)
        value = raw[offset:offset + length]
        offset += length
        if tag == 0x5455:
            need(value and value[0] & ~7 == 0 and len(value) ==
                 (1 + (4 if value[0] & 1 else 0) if central else 1 + 4 * bin(value[0]).count("1")),
                 "Malformed Unix ZIP timestamp")
        else:
            need(len(value) >= 5 and value[0] == 1 and 1 <= value[1] <= 8, "Malformed ZIP UID field")
            end_uid = 2 + value[1]
            need(end_uid < len(value) and 1 <= value[end_uid] <= 8 and
                 end_uid + 1 + value[end_uid] == len(value), "Malformed ZIP GID field")


def zip_structure(stream, size, check):
    """Parse the entire ZIP32 graph; no zipfile extraction or skipped extents."""
    need(22 <= size <= FILE_LIMIT, "Unsupported archive size")
    stream.seek(size - 22)
    end = struct.unpack("<I4H2IH", exact(stream, 22))
    signature, disk, directory_disk, on_disk, count, directory_size, directory_offset, comment = end
    need(signature == 0x06054B50 and disk == directory_disk == comment == 0 and
         0 < count == on_disk <= MEMBER_LIMIT and directory_size <= JSON_LIMIT and
         directory_offset + directory_size == size - 22, "Invalid/multipart/ZIP64/commented/trailing ZIP EOCD")
    stream.seek(directory_offset)
    rows, names, total = [], set(), 0
    for _ in range(count):
        check()
        fields = struct.unpack("<I6H3I5H2I", exact(stream, 46))
        sig, made, version, flags, method, mtime, mdate, crc, compressed, length, nl, xl, cl, start_disk, ia, ea, local = fields
        need(sig == 0x02014B50 and made >> 8 == 3 and version in (10, 20) and start_disk == 0 and
             flags & ~0x080E == 0 and method in (0, 8) and (method == 8 or flags & 6 == 0) and
             (version == 20 or method == 0 and flags & 8 == 0) and
             cl == 0 and ia in (0, 1) and ea & 0xFFFF in (0, 0x10, 0x20, 0x30) and
             compressed < 0xFFFFFFFF and length <= FILE_LIMIT and local < directory_offset and
             0 < nl <= 1024 and xl <= SMALL_LIMIT, "Unsupported ZIP central entry")
        raw_name, extra = exact(stream, nl), exact(stream, xl)
        mode = ea >> 16
        kind = "directory" if stat.S_ISDIR(mode) else "link" if stat.S_ISLNK(mode) else "file"
        need(stat.S_ISREG(mode) or kind in ("directory", "link"), "Special ZIP entry")
        need(ea & 0x10 == 0 or kind == "directory", "Conflicting Unix/DOS ZIP type")
        need(mode & 0o7000 == 0, "Privileged/sticky ZIP mode")
        name = safe_name(raw_name, kind == "directory")
        need(name.casefold() not in names, "Duplicate/case-alias archive member")
        names.add(name.casefold())
        extra_fields(extra, True)
        need(kind != "directory" or length == 0, "Nonempty ZIP directory")
        need(kind != "link" or 0 < length <= 4096, "Invalid ZIP link-text bound")
        total += length
        need(total <= EXPANSION_LIMIT, "ZIP expansion budget")
        rows.append({"name": name, "kind": kind, "mode": mode, "flags": flags, "method": method,
                     "bytes": length, "compressedBytes": compressed, "crc32": crc, "localOffset": local,
                     "rawName": raw_name, "version": version, "mtime": mtime, "mdate": mdate,
                     "centralExtraSha256": hashlib.sha256(extra).hexdigest(), "centralExtraBytes": len(extra)})
    need(stream.tell() == directory_offset + directory_size, "Central directory count/length differs")
    rows.sort(key=lambda row: row["localOffset"])
    expected = 0
    for index, row in enumerate(rows):
        check()
        need(row["localOffset"] == expected, "Overlapping/gapped/prefixed local ZIP records")
        stream.seek(expected)
        sig, version, flags, method, mtime, mdate, crc, compressed, length, nl, xl = struct.unpack(
            "<I5H3I2H", exact(stream, 30))
        need(sig == 0x04034B50 and (version, flags, method, mtime, mdate) ==
             tuple(row[key] for key in ("version", "flags", "method", "mtime", "mdate")) and
             nl == len(row["rawName"]) and xl <= SMALL_LIMIT, "Local/central header mismatch")
        need(exact(stream, nl) == row["rawName"], "Local/central filename mismatch")
        extra = exact(stream, xl)
        extra_fields(extra, False)
        row["localExtraBytes"], row["localExtraSha256"] = len(extra), hashlib.sha256(extra).hexdigest()
        row["dataOffset"] = stream.tell()
        wanted = (row["crc32"], row["compressedBytes"], row["bytes"])
        actual = (crc, compressed, length)
        need(all(got in (0, want) for got, want in zip(actual, wanted)) if flags & 8 else actual == wanted,
             "Local ZIP size/CRC differs")
        next_offset = rows[index + 1]["localOffset"] if index + 1 < len(rows) else directory_offset
        end_data = row["dataOffset"] + row["compressedBytes"]
        need(row["dataOffset"] <= end_data <= next_offset, "ZIP payload overlaps another record")
        descriptor_length = next_offset - end_data
        if flags & 8:
            need(descriptor_length in (12, 16), "Missing/oversized ZIP descriptor")
            stream.seek(end_data)
            descriptor = exact(stream, descriptor_length)
            if descriptor_length == 16:
                need(descriptor[:4] == b"PK\x07\x08", "Wrong ZIP descriptor signature")
                descriptor = descriptor[4:]
            need(struct.unpack("<III", descriptor) == wanted, "ZIP descriptor differs from central entry")
        else:
            need(descriptor_length == 0, "Unexpected data after ZIP payload")
        row["descriptorBytes"] = descriptor_length
        expected = next_offset
        del row["rawName"]
    return rows


def member_blocks(stream, row, check):
    stream.seek(row["dataOffset"])
    remaining, count, crc = row["compressedBytes"], 0, 0
    decoder = zlib.decompressobj(-15) if row["method"] == 8 else None
    while remaining:
        check()
        raw = exact(stream, min(CHUNK, remaining))
        remaining -= len(raw)
        while True:
            block = decoder.decompress(raw, CHUNK) if decoder else raw
            if decoder:
                need(not decoder.unused_data, "Trailing bytes inside compressed member")
                raw = decoder.unconsumed_tail
            count += len(block)
            need(count <= row["bytes"], "Member expands beyond declared size")
            crc = zlib.crc32(block, crc)
            if block:
                yield block
            if decoder is None or not raw and len(block) < CHUNK:
                break
            check()
    need(decoder is None or decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
         "Incomplete deflate member")
    need(count == row["bytes"] and crc & 0xFFFFFFFF == row["crc32"], "Member length/CRC mismatch")


def namespace(rows, prefix):
    """Account for inferred directories too, including case and file/link parents."""
    nodes, spellings = {"": "directory"}, {"": ""}
    for row in rows:
        name = row["name"]
        need(name == prefix or name.startswith(prefix + "/"), "Archive member outside package prefix")
        relative = name[len(prefix):].lstrip("/")
        need(relative or row["kind"] == "directory", "Nondirectory package prefix")
        row["relative"] = relative
        paths = [(relative, row["kind"])]
        parts = relative.split("/") if relative else []
        paths.extend(("/".join(parts[:length]), "directory") for length in range(1, len(parts)))
        for path, kind in paths:
            need(path.casefold() not in spellings or spellings[path.casefold()] == path,
                 "Case-alias inferred directory")
            need(path not in nodes or nodes[path] == kind, "Archive file/link has descendants")
            nodes[path], spellings[path.casefold()] = kind, path
    need("source.properties" in nodes and nodes["source.properties"] == "file" and
         "package.xml" not in nodes and len(nodes) + 1 <= GRAPH_LIMIT, "Unsupported package namespace")
    return {**nodes, "package.xml": "file"}


def image_rows(rows):
    actual = {row["relative"]: row["bytes"] for row in rows}
    need(actual == IMAGE_MEMBERS and len(rows) == len(IMAGE_MEMBERS), "Not the complete 32-member r05 image")
    need(all(row["kind"] == "file" and row["mode"] == 0o100644 and
             (row["method"], row["flags"]) in ((0, 0), (8, 8)) and
             row["centralExtraBytes"] == 0 for row in rows), "Changed r05 member type/mode/flags/metadata")


def installed_graph(root, check, rows):
    """Read metadata, never unknown file contents or link targets. Keep partial rows."""
    physical(root)
    base = identity(root.lstat())
    need(stat.S_ISDIR(base["mode"]) and base["uid"] == os.getuid(), "Package root is not an owned directory")
    pending, inodes = [""], set()
    while pending:
        check()
        relative = pending.pop()
        path = root / relative
        physical(path.parent)
        info = identity(path.lstat())
        kind = "directory" if stat.S_ISDIR(info["mode"]) else "file" if stat.S_ISREG(info["mode"]) else "link"
        rows[relative] = {"identity": info, "kind": kind}
        need(info["dev"] == base["dev"] and info["uid"] == base["uid"] and info["mode"] & 0o7000 == 0,
             "Cross-device/foreign/privileged installed member")
        need(kind != "link" or stat.S_ISLNK(info["mode"]), "Special installed member")
        need((info["dev"], info["ino"]) not in inodes and (kind == "directory" or info["nlink"] == 1),
             "Aliased installed namespace")
        inodes.add((info["dev"], info["ino"]))
        need(len(rows) + len(pending) <= GRAPH_LIMIT and relative.count("/") < 24, "Installed graph bound")
        if kind == "directory":
            need(info["mode"] & 0o022 == 0, "Group/other-writable installed directory")
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(path, flags)
            try:
                need(identity(os.fstat(fd)) == info, "Installed directory changed before listing")
                names = []
                # scandir(fd) avoids following a replacement of the directory path.
                with os.scandir(fd) as entries:
                    for entry in entries:
                        check()
                        names.append(entry.name)
                        need(len(rows) + len(pending) + len(names) <= GRAPH_LIMIT, "Installed membership bound")
                        need("/" not in entry.name and safe_name(entry.name.encode("ascii")) == entry.name,
                             "Unsafe installed member name")
                rows[relative]["children"] = sorted(names)
                need(identity(os.fstat(fd)) == info, "Installed directory changed during listing")
            finally:
                os.close(fd)
            need(identity(path.lstat()) == info, "Installed directory changed after listing")
            pending.extend(relative + "/" + name if relative else name for name in reversed(sorted(names)))
    return rows


def resolve_links(nodes, links):
    """Resolve only the already admitted namespace; never dereference the SDK."""
    def resolve(parts, seen):
        current = []
        while parts:
            part, parts = parts[0], parts[1:]
            if part == ".":
                continue
            if part == "..":
                need(current, "Archive link escapes package")
                current.pop()
                continue
            current.append(part)
            name = "/".join(current)
            need(name in nodes, "Missing archive link target")
            if name in links:
                need(name not in seen and len(seen) < 32, "Archive link cycle/depth")
                current.pop()
                return resolve(current + links[name].split("/") + parts, seen | {name})
            need(not parts or nodes[name] == "directory", "Archive link traverses nondirectory")
        return "/".join(current)

    for name, text in links.items():
        need(0 < len(text) <= 4096 and not text.startswith("/") and "\\" not in text and
             all(part in (".", "..") or re.fullmatch(r"[A-Za-z0-9._+@ -]{1,200}", part) and
                 not part.endswith((" ", ".")) for part in text.split("/")), "Unsafe archive link text")
        target = resolve(name.split("/")[:-1] + text.split("/"), {name})
        need(target != "package.xml", "Installer record cannot be a loader target")


PROPERTIES = {
    "image": {
        "Pkg.Desc": "System Image Page Size 16k arm64-v8a with Google Play.", "Pkg.Revision": "5",
        "Pkg.Dependencies": "emulator#35.4.9", "AndroidVersion.ApiLevel": "37.0",
        "AndroidVersion.ExtensionLevel": "22", "AndroidVersion.IsBaseSdk": "true",
        "SystemImage.Abi": "arm64-v8a", "SystemImage.TagId": "google_apis_playstore,page_size_16kb",
        "SystemImage.TagDisplay": "Google APIs PlayStore,Page Size 16KB", "SystemImage.GpuSupport": "true",
        "Addon.VendorId": "google", "Addon.VendorDisplay": "Google Inc.",
    },
    "emulator": {"Pkg.UserSrc": "false", "Pkg.Revision": "36.6.11", "Pkg.Path": "emulator",
                 "Pkg.Desc": "Android Emulator", "Pkg.BuildId": "15507667"},
}


def source_properties(raw, role):
    need(0 < len(raw) <= SMALL_LIMIT, "Source properties bound")
    values = {}
    for line in raw.decode("ascii").splitlines():
        need("=" in line and "\\" not in line, "Unsupported source property")
        key, value = line.split("=", 1)
        need(key not in values, "Duplicate source property")
        values[key] = value
    need(values == PROPERTIES[role], "Authenticated source properties differ from the selected package")
    return values


def installer_metadata(raw, role, properties):
    """Exact installer-only exception. It grants neither path nor code authority."""
    need(properties == PROPERTIES[role], "Installer lacks authenticated source metadata")
    need(0 < len(raw) <= SMALL_LIMIT and b"\0" not in raw and b"<!" not in raw and
         raw.count(b"<?") <= 1 and (b"<?" not in raw or raw.startswith(b"<?xml ")), "Unsupported installer XML")
    raw.decode("utf-8")
    prefixes, count, depth = {}, 0, 0
    parser = ET.iterparse(io.BytesIO(raw), events=("start-ns", "start", "end"))
    for event, value in parser:
        if event == "start-ns":
            prefix, uri = value
            need(prefix not in prefixes and len(prefixes) < 32, "Redefined/excessive XML namespace")
            prefixes[prefix] = uri
        elif event == "start":
            count, depth = count + 1, depth + 1
            need(count <= 96 and depth <= 12, "Installer XML structure bound")
        else:
            depth -= 1
    document = parser.root
    need(document.tag == "{http://schemas.android.com/repository/android/common/02}repository" and
         document.attrib == {} and len(document) == 2 and [child.tag for child in document] ==
         ["license", "localPackage"], "Unsupported installer repository")
    license_id = "android-sdk-arm-dbt-license" if role == "image" else "android-sdk-license"
    license_node, package = document
    need(license_node.attrib == {"id": license_id, "type": "text"} and len(license_node) == 0 and
         (license_node.text or "").strip() and not (license_node.tail or "").strip(),
         "Missing/changed installer license identity")

    def node(tag, text="", attributes=None, children=()):
        return (tag, attributes or {}, text, list(children))

    def shape(element):
        attrs = dict(element.attrib)
        xsi = "{http://www.w3.org/2001/XMLSchema-instance}type"
        if xsi in attrs:
            parts = attrs[xsi].split(":")
            need(len(parts) == 2 and parts[0] in prefixes, "Unknown installer type namespace")
            attrs[xsi] = "{" + prefixes[parts[0]] + "}" + parts[1]
        need(not (element.tail or "").strip(), "Unexpected installer mixed content")
        return node(element.tag, (element.text or "").strip(), attrs, [shape(child) for child in element])

    xsi = "{http://www.w3.org/2001/XMLSchema-instance}type"
    revision = ("5",) if role == "image" else ("36", "6", "11")
    details = []
    if role == "image":
        details = [node("api-level", "37.0"), node("extension-level", "22"), node("base-extension", "true"),
                   node("tag", children=[node("id", "google_apis_playstore"), node("display", "Google APIs PlayStore")]),
                   node("tag", children=[node("id", "page_size_16kb"), node("display", "Page Size 16KB")]),
                   node("vendor", children=[node("id", "google"), node("display", "Google Inc.")]),
                   node("abi", "arm64-v8a"), node("abis", "arm64-v8a")]
    details_type = ("{http://schemas.android.com/sdk/android/repo/sys-img2/05}sysImgDetailsType" if role == "image"
                    else "{http://schemas.android.com/repository/android/generic/02}genericDetailsType")
    children = [node("type-details", attributes={xsi: details_type}, children=details),
                node("revision", children=[node(key, value) for key, value in zip(("major", "minor", "micro"), revision)]),
                node("display-name", "16 KB Page Size Google Play ARM 64 v8a System Image" if role == "image"
                     else "Android Emulator"), node("uses-license", attributes={"ref": license_id})]
    if role == "image":
        children.append(node("dependencies", children=[node("dependency", attributes={"path": "emulator"}, children=[
            node("min-revision", children=[node("major", "35"), node("minor", "4"), node("micro", "9")])])]))
    package_id = IMAGE_PACKAGE if role == "image" else "emulator"
    need(not (document.text or "").strip() and shape(package) ==
         node("localPackage", attributes={"path": package_id, "obsolete": "false"}, children=children),
         "Installer package/revision/dependency/type differs")
    return {"package": package_id, "revision": ".".join(revision), "licenseId": license_id,
            "authority": "HASH_RETAINED_INSTALLER_RECORD_ONLY"}


def compare_member(stream, row, installed, observed, check, record):
    a, b, raw = hashlib.sha256(), hashlib.sha256(), []
    count_a, count_b = 0, 0
    try:
        need(identity(installed.lstat()) == observed["identity"], "Installed member changed before comparison")
        need(row["mode"] == observed["identity"]["mode"], "Archive/installed member mode differs")
        if row["kind"] == "directory":
            need(not list(member_blocks(stream, row, check)), "Nonempty directory stream")
        elif row["kind"] == "link":
            data = b"".join(member_blocks(stream, row, check))
            value = os.readlink(installed).encode("ascii")
            a.update(data)
            b.update(value)
            count_a, count_b = len(data), len(value)
            need(data == value, "Archive/installed symlink text differs")
            raw.append(data)
        else:
            with original(installed, row["bytes"]) as (target, opened):
                need(opened == observed["identity"] and opened["size"] == row["bytes"], "Installed file size/identity differs")
                for block in member_blocks(stream, row, check):
                    actual = target.read(len(block))
                    a.update(block)
                    b.update(actual)
                    count_a, count_b = count_a + len(block), count_b + len(actual)
                    need(block == actual, "Archive/installed file bytes differ")
                    if row["relative"] == "source.properties":
                        need(count_a <= SMALL_LIMIT, "Source metadata bound")
                        raw.append(block)
                need(target.read(1) == b"", "Installed file has trailing bytes")
        need(identity(installed.lstat()) == observed["identity"], "Installed member changed after comparison")
        record["status"] = "BYTE_EQUAL"
        return b"".join(raw)
    finally:
        record.update({"archiveBytesRead": count_a, "installedBytesRead": count_b,
                       "archiveSha256": a.hexdigest(), "installedSha256": b.hexdigest()})


def compare_package(role, archive, package, check, result):
    """No extraction. The result is populated before each failure-prone operation."""
    result.update({"role": role, "archivePath": str(archive), "packagePath": str(package),
                   "status": "INCOMPLETE", "members": [], "installedBefore": {}, "installedAfter": {}})
    with original(archive, PINS[role]["bytes"]) as (stream, before):
        need(before["size"] == PINS[role]["bytes"], "Archive whole-body size differs")
        digest, count = hashlib.sha256(), 0
        while True:
            check()
            block = stream.read(CHUNK)
            if not block:
                break
            count += len(block)
            need(count <= PINS[role]["bytes"], "Archive grew during hashing")
            digest.update(block)
        need(count == before["size"], "Archive read did not reach its declared EOF")
        result["archive"] = {"bytes": count, "sha256": digest.hexdigest()}
        result["archiveIdentity"] = before
        expected_hash = PINS[role]["publisherSha256"]
        need(expected_hash is None or digest.hexdigest() == expected_hash, "Published emulator SHA256 differs")
        rows = zip_structure(stream, count, check)
        nodes = namespace(rows, PINS[role]["prefix"])
        if role == "image":
            image_rows(rows)
        result["archiveEntries"] = rows
        installed_graph(package, check, result["installedBefore"])
        observed = result["installedBefore"]
        need({key: value["kind"] for key, value in observed.items()} == nodes,
             "Installed namespace is not exactly archive plus package.xml; no unknown content was read")
        props, links = None, {}
        for row in rows:
            record = {"path": row["relative"], "kind": row["kind"], "status": "INCOMPLETE"}
            result["members"].append(record)
            raw = compare_member(stream, row, package / row["relative"], observed[row["relative"]], check, record)
            if row["kind"] == "link":
                links[row["relative"]] = raw.decode("ascii")
            elif row["relative"] == "source.properties":
                props = source_properties(raw, role)
        resolve_links(nodes, links)
        result["linkTexts"], result["sourceProperties"] = links, props
        metadata = package / "package.xml"
        need(identity(metadata.lstat()) == observed["package.xml"]["identity"], "Installer metadata changed")
        bound, raw = file_binding(metadata, SMALL_LIMIT, check, keep=True)
        result["installer"] = {**bound, **installer_metadata(raw, role, props)}
        installed_graph(package, check, result["installedAfter"])
        need(result["installedBefore"] == result["installedAfter"], "Installed graph changed during comparison")
        # Retain one complete graph on success, not two independently mutable copies.
        result["installedAfter"] = "EXACTLY_EQUAL_TO_BEFORE"
    result["status"] = "WHOLE_ARCHIVE_INSTALLED_CONTENT_MATCH"
    return raw


def approved_url(value, role):
    need(role in PINS, "Unknown archive role")
    need(type(value) is str and len(value) <= 4096 and all(33 <= ord(c) <= 126 for c in value), "Unsafe HTTPS URL")
    url = urlsplit(value)
    need(url.scheme == "https" and url.username is None and url.password is None and url.port in (None, 443) and
         not url.fragment and "\\" not in value, "Unauthenticated/credential-bearing URL")
    if role == "image":
        need(value == IMAGE_URL, "Image redirects/alternate URLs are not admitted")
    else:
        cdn = bool(re.fullmatch(r"r[0-9]{1,3}---sn-[a-z0-9-]{1,80}\.gvt1\.com", url.hostname or ""))
        expected = "/android/repository/" if url.hostname == "dl.google.com" else "/edgedl/android/repository/"
        need((url.hostname in ("redirector.gvt1.com", "dl.google.com") or cdn) and
             url.path == expected + EMULATOR_NAME and len(url.query) <= 2048,
             "Unreviewed emulator redirect origin/path")
    return value


def response_headers(raw, role, head):
    need(0 < len(raw) <= HEADER_LIMIT and raw.endswith(b"\r\n\r\n"), "Incomplete/oversized HTTP headers")
    lines = raw[:-4].split(b"\r\n")
    match = re.fullmatch(rb"HTTP/1\.[01] ([1-5][0-9]{2})(?: [\x20-\x7e]*)?", lines[0])
    need(match, "Unsupported HTTP response line")
    status, fields = int(match[1]), {}
    for line in lines[1:]:
        need(b":" in line and not line.startswith((b" ", b"\t")), "Malformed/folded HTTP header")
        name, value = line.split(b":", 1)
        need(re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) and
             all(byte == 9 or 32 <= byte <= 126 for byte in value), "Unsupported HTTP header bytes")
        name, value = name.decode("ascii").lower(), value.decode("ascii").strip()
        need(name not in fields, "Duplicate HTTP header")
        fields[name] = value
    need("transfer-encoding" not in fields and "content-range" not in fields and
         fields.get("content-encoding", "identity").lower() == "identity", "Transformed/ranged HTTP body")
    if head and status in (301, 302, 303, 307, 308):
        need(role == "emulator" and "location" in fields, "Unapproved HTTP redirect")
        approved_url(fields["location"], role)
    else:
        need(status == 200 and fields.get("content-length") == str(PINS[role]["bytes"]) and
             "location" not in fields, "HTTP status/whole-body length differs")
    return {"status": status, "fields": fields}


CURL_FORMAT = ("%{stderr}HTTP_CODE=%{http_code}\nSIZE_DOWNLOAD=%{size_download}\n"
               "SSL_VERIFY_RESULT=%{ssl_verify_result}\nURL_EFFECTIVE=%{url_effective}\n"
               "NUM_REDIRECTS=%{num_redirects}\n")


def curl_arguments(url, role, head):
    approved_url(url, role)
    seconds = 30 if head else PINS[role]["seconds"]
    return ["/usr/bin/curl", "-q", "--globoff", "--silent", "--show-error", "--fail", "--http1.1", "--include",
            "--proto", "=https", "--proto-redir", "=https", "--proxy", "", "--noproxy", "*",
            "--connect-timeout", "30", "--max-time", str(seconds), "--max-redirs", "0",
            "--max-filesize", str(PINS[role]["bytes"]), "--speed-time", "30", "--speed-limit", "1024",
            "--header", "Accept-Encoding: identity", "--output", "-", "--write-out", CURL_FORMAT,
            *(["--head"] if head else []), "--url", url]


def curl_environment(environment, private_home):
    for key, value in environment.items():
        lower = key.lower()
        need(not value or not ("proxy" in lower or lower.startswith(("curl_", "dyld_", "ld_")) or
             lower in ("ssl_cert_file", "ssl_cert_dir", "sslkeylogfile", "xdg_config_home")),
             "Resolve ambient curl/proxy/TLS/loader overrides before capture")
    # No inherited tokens, credentials, CA overrides, netrc/curlrc or user headers.
    # -q is also first in the exact argv; neither default config nor netrc is enabled.
    controlled = {key: value for key, value in environment.items() if key.startswith("P2PKIT_AUDIT_")}
    controlled.update(HOME=str(private_home), TMPDIR=str(private_home), PATH="/usr/bin:/bin", LC_ALL="C",
                      GRADLE_USER_HOME=environment["GRADLE_USER_HOME"])
    return controlled


def curl_status(raw, url, header, count):
    fields = {}
    for line in raw.decode("ascii").splitlines():
        need("=" in line, "Curl status is incomplete or contains an error")
        key, value = line.split("=", 1)
        need(key not in fields, "Duplicate curl status")
        fields[key] = value
    need(fields == {"HTTP_CODE": str(header["status"]), "SIZE_DOWNLOAD": str(count), "SSL_VERIFY_RESULT": "0",
                    "URL_EFFECTIVE": url, "NUM_REDIRECTS": "0"}, "Actual curl TLS/status/URL/length differs")
    return fields


def metadata_size(directory):
    size = 0
    for path in directory.iterdir():
        if path.name in ("image.body.original", "emulator.body.original", "curl-home"):
            continue
        info = path.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Unexpected evidence entry")
        size += info.st_size
    return size


def retain_json(runner, path, value):
    raw = runner.json_bytes(value)
    # Even a bound failure retains its actual, explicitly incomplete prefix.
    room = max(0, METADATA_LIMIT - MIB - metadata_size(path.parent))
    limit = min(JSON_LIMIT, room)
    with runner.new_file(path) as output:
        output.write(raw[:limit])
        output.flush()
        os.fsync(output.fileno())
    need(len(raw) <= limit, "Metadata retention bound; original prefix is incomplete")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


class CurlCapture:
    """One fixed curl transfer, not a replacement audit/process supervisor.

    Controller.Commands has intentional 240s/512MiB bounds. These two archives
    instead need 900s/300s and up to 2.2GB. The maintained outer command still owns
    every child and all cancellation/drain; no subprocess escapes that domain.
    """
    def __init__(self, runner, evidence, environment, check):
        self.runner, self.evidence, self.environment, self.check = runner, evidence, environment, check
        self.children, self.records = [], []

    def run(self, role, url, *, head=False, hop=0):
        need(role in PINS and type(head) is bool and type(hop) is int and 0 <= hop <= 3, "Invalid capture request")
        label = role + (f"-head-{hop}" if head else "")
        argv = curl_arguments(url, role, head)
        seconds, limit = (30, 0) if head else (PINS[role]["seconds"], PINS[role]["bytes"])
        paths = {kind: self.evidence / (label + "." + kind + ".original") for kind in ("headers", "body", "stderr")}
        record = {"argv": argv, "role": role, "head": head, "label": label, "timeoutSeconds": seconds,
                  "startedUtc": self.runner.utc(), "exitCode": None, "stdoutEof": False, "stderrEof": False,
                  "errors": [], "retention": "PARTIAL", "originals": {key: str(path) for key, path in paths.items()}}
        self.records.append(record)
        child, selector, pipes = None, None, []
        hashes = {key: hashlib.sha256() for key in paths}
        counts, pending, header = {key: 0 for key in paths}, bytearray(), None
        try:
            deadline = time.monotonic() + seconds
            with self.runner.new_file(paths["headers"]) as headers, self.runner.new_file(paths["body"]) as body, \
                    self.runner.new_file(paths["stderr"]) as stderr:
                selector = selectors.DefaultSelector()
                child = subprocess.Popen(argv, cwd=self.evidence, env=self.environment, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, bufsize=0)
                self.children.append(child)
                record["pid"] = child.pid
                pipes = [child.stdout, child.stderr]
                for name, pipe in (("stdout", child.stdout), ("stderr", child.stderr)):
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe, selectors.EVENT_READ, name)

                def retain(kind, block, target, bound):
                    target.write(block)
                    target.flush()
                    hashes[kind].update(block)
                    counts[kind] += len(block)
                    need(counts[kind] <= bound, "Curl " + kind + " output bound; retained prefix is incomplete")

                while selector.get_map() or child.poll() is None:
                    self.check()
                    need(time.monotonic() < deadline, "Whole curl request deadline")
                    for key, _ in selector.select(0.1):
                        block = os.read(key.fileobj.fileno(), CHUNK)
                        if not block:
                            record[key.data + "Eof"] = True
                            selector.unregister(key.fileobj)
                            continue
                        if key.data == "stderr":
                            retain("stderr", block, stderr, HEADER_LIMIT)
                            continue
                        if header is None:
                            pending.extend(block)
                            split = pending.find(b"\r\n\r\n")
                            if split < 0:
                                need(len(pending) <= HEADER_LIMIT, "HTTP header bound")
                                continue
                            first, block = bytes(pending[:split + 4]), bytes(pending[split + 4:])
                            pending.clear()
                            retain("headers", first, headers, HEADER_LIMIT)
                            if block:
                                retain("body", block, body, limit)
                                block = b""
                            header = response_headers(first, role, head)
                        if block:
                            retain("body", block, body, limit)
                if pending:
                    retain("headers", bytes(pending), headers, HEADER_LIMIT)
                    pending.clear()
                record["exitCode"] = child.poll()
                for target in (headers, body, stderr):
                    target.flush()
                    os.fsync(target.fileno())
                need(record["exitCode"] == 0 and record["stdoutEof"] and record["stderrEof"] and header is not None,
                     "Curl did not finish naturally with both EOFs")
                need(counts["body"] == limit, "Incomplete whole curl body")
                status_raw = file_binding(paths["stderr"], HEADER_LIMIT, self.check, keep=True)[1]
                record["statusFields"] = curl_status(status_raw, url, header, counts["body"])
                record["response"] = header
                record["retention"] = "COMPLETE_AUTHENTICATED_TRANSFER"
        except BaseException as error:
            record["errors"].append(type(error).__name__ + ": " + str(error))
            # Preserve a truncated header too; it must never become a valid response.
            if pending:
                try:
                    physical(paths["headers"])
                    before = identity(paths["headers"].lstat())
                    flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
                    with os.fdopen(os.open(paths["headers"], flags), "ab") as output:
                        need(identity(os.fstat(output.fileno())) == before, "Header original changed")
                        raw = bytes(pending[:HEADER_LIMIT + CHUNK])
                        output.write(raw)
                        hashes["headers"].update(raw)
                        counts["headers"] += len(raw)
                except BaseException as failure:
                    record["errors"].append("Header prefix retention: " + type(failure).__name__)
            raise
        finally:
            record["endedUtc"] = self.runner.utc()
            record["bindings"] = {key: {"bytes": counts[key], "sha256": hashes[key].hexdigest()} for key in paths}
            if child is not None:
                try:
                    record["exitCode"] = child.poll()
                except BaseException as error:
                    record["errors"].append("Exit observation: " + type(error).__name__)
            for pipe in pipes:
                try:
                    pipe.close()
                except BaseException as error:
                    record["errors"].append("Pipe close: " + type(error).__name__)
            if selector is not None:
                try:
                    selector.close()
                except BaseException as error:
                    record["errors"].append("Selector close: " + type(error).__name__)
            retain_json(self.runner, self.evidence / (label + ".json"), record)
        need(not record["errors"] and record["exitCode"] == 0, "Curl finalization did not succeed")
        return record

    def download(self, role):
        url, seen = PINS[role]["url"], set()
        if role == "emulator":
            for hop in range(4):
                need(url not in seen, "Emulator redirect loop")
                seen.add(url)
                record = self.run(role, url, head=True, hop=hop)
                if record["response"]["status"] == 200:
                    break
                url = record["response"]["fields"]["location"]
            else:
                need(False, "Emulator redirect limit")
        # Exactly one GET body: no GET redirect, retry, range, resume or splice.
        return self.run(role, url)


def selected_sdk(environment, root, check):
    need(environment.get("ANDROID_HOME") and not environment.get("ANDROID_SDK_ROOT"), "Select only ANDROID_HOME")
    sdk = physical(Path(environment["ANDROID_HOME"]))
    need(sdk.is_dir(), "Selected SDK is not a physical directory")
    local = root / "local.properties"
    if os.path.lexists(local):
        raw = file_binding(local, SMALL_LIMIT, check, keep=True)[1]
        values = {}
        for line in raw.decode("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "!")):
                continue
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)\s*[=:]\s*([^\\]*)", line)
            need(match and match[1] not in values, "Ambiguous/escaped local SDK configuration")
            values[match[1]] = match[2]
        need("sdk.dir" not in values or values["sdk.dir"] == str(sdk), "local.properties selects another SDK")
    return sdk


def capture_request(argv, root):
    need(type(argv) is list and len(argv) == 6 and argv[0] in ("python3", "/usr/bin/python3", sys.executable) and
         argv[1:4] == ["-I", "-B", "-S"] and argv[4] in ("scripts/android_archive_admission.py",
         str(root / "scripts/android_archive_admission.py")) and argv[5] == "capture", "Not the exact isolated capture request")


def json_original(path, check):
    binding, raw = file_binding(path, JSON_LIMIT, check, keep=True)
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate original JSON key")
            result[key] = value
        return result
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, "Nonfinite original JSON"))
    need(type(result) is dict, "Original JSON must be an object")
    return binding, result


def output_binding(runner, path, check):
    bound = file_binding(path, JSON_LIMIT, check)[0]
    return runner.json_bytes({"path": str(path), **bound})


def confirm_inputs(runner, evidence, role, archive, package, compared, check):
    """Recheck the first package after the other package's potentially long work."""
    observed = {}
    try:
        need(identity(physical(archive).lstat()) == compared["archiveIdentity"], "Archive changed before final seal")
        installed_graph(package, check, observed)
        need(observed == compared["installedBefore"], "Installed package changed before final seal")
    except BaseException:
        retain_json(runner, evidence / (role + "-final-rejected.json"), {"installed": observed, "status": "INCOMPLETE"})
        raise


def capture(runner, state, context, owner, environment, check):
    start = runner.read_json(state / "evidence" / owner / "start.json")
    capture_request(start.get("requestedArgv"), ROOT)
    evidence = state / "evidence" / owner / "android-archives"
    physical(evidence, missing=True).mkdir(mode=0o700)
    result = {"schema": 1, "status": "INCOMPLETE", "ownerId": owner, "source": context["source"],
              "jobId": context["id"], "host": context["host"], "gradleHome": context["gradleHome"],
              "runtime": "NOT_RUN", "independentReview": "REQUIRED_SEPARATELY", "errors": [],
              "packages": {}, "startedUtc": runner.utc(), "retained": {}}
    transport, good = None, False
    try:
        initial_required = FLOOR + RESERVE + sum(pin["bytes"] for pin in PINS.values())
        need(shutil.disk_usage(evidence).free >= initial_required,
             "Need archive-only 8GiB floor plus 3GiB spare reserve and exact archive bytes")
        sdk = selected_sdk(environment, ROOT, check)
        result["sdk"] = str(sdk)
        home = evidence / "curl-home"
        home.mkdir(mode=0o700)
        home_before = identity(home.lstat())
        controlled = curl_environment(environment, home)
        result["curl"] = {"path": "/usr/bin/curl", **file_binding(Path("/usr/bin/curl"), 64 * MIB, check)[0]}
        transport = CurlCapture(runner, evidence, controlled, check)
        for role in ("image", "emulator"):
            download = transport.download(role)
            comparison = {}
            path = evidence / (role + "-comparison.json")
            try:
                budget = Budget(COMPARE_SECONDS, evidence)
                def compare_check():
                    check()
                    budget()
                installer = compare_package(role, evidence / (role + ".body.original"),
                                            sdk / (IMAGE_PATH if role == "image" else "emulator"),
                                            compare_check, comparison)
                need(comparison["archive"] == download["bindings"]["body"], "Compared archive differs from producer bytes")
                with runner.new_file(evidence / (role + "-package.xml.original")) as output:
                    output.write(installer)
                    output.flush()
                    os.fsync(output.fileno())
            finally:
                result["packages"][role] = retain_json(runner, path, comparison)
        need(identity(physical(home).lstat()) == home_before and not list(home.iterdir()),
             "Curl private home changed or contains unexpected files")
        need(file_binding(Path("/usr/bin/curl"), 64 * MIB, check)[0] ==
             {key: result["curl"][key] for key in ("bytes", "sha256")}, "Curl binary changed during capture")
        for role in ("image", "emulator"):
            comparison = json_original(evidence / (role + "-comparison.json"), check)[1]
            confirm_inputs(runner, evidence, role, evidence / (role + ".body.original"),
                           sdk / (IMAGE_PATH if role == "image" else "emulator"), comparison, check)
        for path in sorted(evidence.iterdir()):
            if path == home:
                continue
            if path.name in ("image.body.original", "emulator.body.original"):
                role = path.name.split(".", 1)[0]
                comparison = json_original(evidence / (role + "-comparison.json"), check)[1]
                need(identity(path.lstat()) == comparison["archiveIdentity"], "Archive changed before capture seal")
                result["retained"][path.name] = comparison["archive"]
            else:
                result["retained"][path.name] = file_binding(path, JSON_LIMIT, check)[0]
        result["publisherWholeArchiveChecksum"] = {"image": None, "emulator": {"sha256": PINS["emulator"]["publisherSha256"]}}
        result["status"] = "AUTHENTICATED_OFFICIAL_ORIGIN_CONTENT_MATCH_PENDING_TERMINAL_RECEIPT"
        good = True
    except BaseException as error:
        result["errors"].append(type(error).__name__ + ": " + str(error))
    finally:
        result["endedUtc"] = runner.utc()
        result["childrenAtReturn"] = []
        for child in ([] if transport is None else transport.children):
            row = {"pid": child.pid, "exitCode": None}
            result["childrenAtReturn"].append(row)
            try:
                row["exitCode"] = child.poll()
            except BaseException as error:
                result["errors"].append("Final child observation: " + type(error).__name__ + ": " + str(error))
        try:
            result["sourceAfter"] = runner.source_snapshot(ROOT)
            need(result["sourceAfter"] == context["source"], "Source changed during capture")
            need(all(row["exitCode"] == 0 for row in result["childrenAtReturn"]), "Curl child not retired successfully")
        except BaseException as error:
            result["errors"].append(type(error).__name__ + ": " + str(error))
        if result["errors"]:
            result["status"], good = "INCOMPLETE", False
        # Reserve one MiB beyond ordinary metadata for this final failure/success summary.
        need(len(runner.json_bytes(result)) <= MIB and metadata_size(evidence) <= METADATA_LIMIT - MIB,
             "Final capture metadata bound")
        runner.write_new_json(evidence / "result.json", result)
    return evidence / "result.json", good


def admit_producer(checker, receipt, context, root, purpose):
    argv = receipt.get("requestedArgv")
    capture_request(argv, root)
    checker.validate(receipt, 0, controller.purpose(purpose), root, root / "gradlew", argv)
    need(receipt.get("executedArgv") == argv and receipt.get("kind") == "command" and
         receipt.get("jobId") == context["id"] and receipt.get("host") == context["host"] and
         receipt.get("gradleHome") == context["gradleHome"] and receipt.get("sourceBefore") == context["source"],
         "Capture belongs to another source/state/host/request")


def retained_transfer(directory, role, head, hop, check):
    label = role + (f"-head-{hop}" if head else "")
    record = json_original(directory / (label + ".json"), check)[1]
    argv = record.get("argv")
    need(type(argv) is list and argv and type(argv[-1]) is str, "Missing original curl request")
    need(record.get("label") == label and record.get("role") == role and record.get("head") is head and
         argv == curl_arguments(argv[-1], role, head) and
         record.get("timeoutSeconds") == (30 if head else PINS[role]["seconds"]) and
         type(record.get("exitCode")) is int and record["exitCode"] == 0 and
         record.get("stdoutEof") is True and record.get("stderrEof") is True and record.get("errors") == [] and
         record.get("retention") == "COMPLETE_AUTHENTICATED_TRANSFER" and
         type(record.get("pid")) is int and record["pid"] > 0 and
         all(type(record.get(key)) is str and record[key] for key in ("startedUtc", "endedUtc")),
         "Original curl did not complete this authenticated bounded request")
    paths = {kind: directory / (label + "." + kind + ".original") for kind in ("headers", "body", "stderr")}
    need(record.get("originals") == {key: str(path) for key, path in paths.items()}, "Curl originals relocated")
    raw_header = file_binding(paths["headers"], HEADER_LIMIT, check, keep=True)[1]
    header = response_headers(raw_header, role, head)
    status = curl_status(file_binding(paths["stderr"], HEADER_LIMIT, check, keep=True)[1], argv[-1], header,
                         0 if head else PINS[role]["bytes"])
    need(record.get("response") == header and record.get("statusFields") == status, "Curl response originals disagree")
    if head:
        need(file_binding(paths["body"], 0, check)[0] == record.get("bindings", {}).get("body"), "HEAD retained entity bytes")
    return record


def admit_retained(runner, checker, artifacts, state, context, owner, environment, producer_path,
                   producer_purpose, check, evidence, result):
    """Canonical producer + all retained originals + a second whole installed comparison.

    Called only inside execute's admitted active command domain and held LeafLock.
    It does not accept a reviewed/trusted/downloaded assertion or confer runtime authority.
    """
    producer_path = runner.absolute_path(str(producer_path))
    receipt, receipt_binding = controller.canonical_receipt(runner, artifacts, state, producer_path)
    need(receipt["id"] != owner, "An active producer cannot admit itself")
    admit_producer(checker, receipt, context, ROOT, producer_purpose)
    directory = state / "evidence" / receipt["id"] / "android-archives"
    profile_path = directory / "result.json"
    profile_binding, profile = json_original(profile_path, check)
    stdout_path = Path(receipt["evidenceDirectory"]) / "product.stdout.log"
    stdout_binding, stdout = file_binding(stdout_path, SMALL_LIMIT, check, keep=True)
    need(stdout == runner.json_bytes({"path": str(profile_path), **profile_binding}),
         "Canonical producer stdout does not bind this capture result")
    need(profile.get("schema") == 1 and profile.get("status") ==
         "AUTHENTICATED_OFFICIAL_ORIGIN_CONTENT_MATCH_PENDING_TERMINAL_RECEIPT" and
         profile.get("ownerId") == receipt["id"] and profile.get("source") == profile.get("sourceAfter") == context["source"] and
         profile.get("jobId") == context["id"] and profile.get("host") == context["host"] and
         profile.get("gradleHome") == context["gradleHome"] and profile.get("errors") == [] and
         profile.get("runtime") == "NOT_RUN" and profile.get("independentReview") == "REQUIRED_SEPARATELY" and
         profile.get("publisherWholeArchiveChecksum") ==
         {"image": None, "emulator": {"sha256": PINS["emulator"]["publisherSha256"]}}, "Incomplete/different capture profile")
    sdk = selected_sdk(environment, ROOT, check)
    need(str(sdk) == profile.get("sdk"), "SDK selection changed since capture")
    curl = {"path": "/usr/bin/curl", **file_binding(Path("/usr/bin/curl"), 64 * MIB, check)[0]}
    need(curl == profile.get("curl"), "Capture's system curl binding changed")
    expected_files, commands = {"result.json", "curl-home"}, []
    for role in ("image", "emulator"):
        url = PINS[role]["url"]
        if role == "emulator":
            seen = set()
            for hop in range(4):
                need(url not in seen, "Retained redirect loop")
                seen.add(url)
                record = retained_transfer(directory, role, True, hop, check)
                need(record["argv"][-1] == url, "Retained redirect chain is not from the published URL")
                commands.append(record)
                if record["response"]["status"] == 200:
                    break
                url = record["response"]["fields"]["location"]
            else:
                need(False, "Retained redirect limit")
        record = retained_transfer(directory, role, False, 0, check)
        need(record["argv"][-1] == url, "GET is not the HEAD-admitted URL")
        commands.append(record)
        expected_files.update((role + "-comparison.json", role + "-package.xml.original"))
    need(profile.get("childrenAtReturn") == [{"pid": row.get("pid"), "exitCode": 0} for row in commands],
         "Capture child retirement observation differs")
    for command in commands:
        label = command["label"]
        expected_files.add(label + ".json")
        expected_files.update(Path(path).name for path in command["originals"].values())
    need({path.name for path in directory.iterdir()} == expected_files and
         physical(directory / "curl-home").is_dir() and not list((directory / "curl-home").iterdir()),
         "Retained capture namespace changed")
    retained = profile.get("retained")
    need(type(retained) is dict and set(retained) == expected_files - {"result.json", "curl-home"} and
         metadata_size(directory) <= METADATA_LIMIT, "Capture retained manifest/metadata bound differs")
    body_names = {role + ".body.original" for role in ("image", "emulator")}
    for name in sorted(retained):
        if name not in body_names:
            need(file_binding(directory / name, JSON_LIMIT, check)[0] == retained[name], "Retained metadata hash changed")
    for command in commands:
        need(command.get("bindings") == {key: retained[Path(path).name] for key, path in command["originals"].items()},
             "Original curl stream bindings differ from capture manifest")
    result["producer"] = {"path": str(producer_path), **receipt_binding}
    result["captureProfile"] = {"path": str(profile_path), **profile_binding}
    result["packages"] = {}
    for role in ("image", "emulator"):
        path = directory / (role + "-comparison.json")
        original_binding, original_comparison = json_original(path, check)
        need(profile.get("packages", {}).get(role) == original_binding, "Original complete comparison binding differs")
        comparison, budget = {}, Budget(COMPARE_SECONDS, directory)
        def compare_check():
            check()
            budget()
        try:
            raw = compare_package(role, directory / (role + ".body.original"),
                                  sdk / (IMAGE_PATH if role == "image" else "emulator"), compare_check, comparison)
            need(comparison == original_comparison and comparison["archive"] == retained[role + ".body.original"] and
                 file_binding(directory / (role + "-package.xml.original"), SMALL_LIMIT, check, keep=True)[1] == raw,
                 "Installed/archive/installer inputs changed since the genuine producer")
        finally:
            result["packages"][role] = retain_json(runner, evidence / (role + "-rechecked.json"), comparison)
    for role in ("image", "emulator"):
        comparison = json_original(directory / (role + "-comparison.json"), check)[1]
        confirm_inputs(runner, evidence, role, directory / (role + ".body.original"),
                       sdk / (IMAGE_PATH if role == "image" else "emulator"), comparison, check)
    for name in sorted(retained):
        if name not in body_names:
            need(file_binding(directory / name, JSON_LIMIT, check)[0] == retained[name],
                 "Retained metadata changed during admission")
    need(controller.canonical_receipt(runner, artifacts, state, producer_path)[1] == receipt_binding and
         file_binding(profile_path, JSON_LIMIT, check)[0] == profile_binding and
         file_binding(stdout_path, SMALL_LIMIT, check)[0] == stdout_binding, "Producer binding changed during admission")
    result["status"] = "AUTHENTICATED_OFFICIAL_ORIGIN_CONTENT_MATCH_PENDING_ADMISSION_RECEIPT"


def execute(args):
    need(os.getuid() != 0, "Use an ordinary native user session, not a root workaround")
    runner = controller.load_tool("run-audit-command.py")
    processes = controller.load_tool("audit_processes.py")
    state, context = runner.context_at(os.environ["P2PKIT_AUDIT_STATE_DIR"])
    owner = controller.admit_outer(runner, processes, state, context, ROOT, os.environ)
    check = Budget(TOTAL_SECONDS, state)
    lock = runner.LeafLock(state)
    try:
        lock.acquire()
        if args.action == "capture":
            path, good = capture(runner, state, context, owner, os.environ, check)
        else:
            evidence = state / "evidence" / owner / "android-archive-admission"
            physical(evidence, missing=True).mkdir(mode=0o700)
            result = {"schema": 1, "ownerId": owner, "source": context["source"], "status": "INCOMPLETE",
                      "runtime": "NOT_RUN", "independentReview": "REQUIRED_SEPARATELY", "errors": []}
            good = False
            try:
                admit_retained(runner, controller.load_tool("check-audit-receipt.py"),
                               controller.load_tool("verify-android-acceptance-artifacts.py"), state, context, owner,
                               os.environ, args.producer_receipt, args.producer_purpose, check, evidence, result)
                need(runner.source_snapshot(ROOT) == context["source"], "Source changed during admission")
                good = True
            except BaseException as error:
                result["status"] = "INCOMPLETE"
                result["errors"].append(type(error).__name__ + ": " + str(error))
            path = evidence / "result.json"
            retain_json(runner, path, result)
        sys.stdout.buffer.write(output_binding(runner, path, lambda: None))
        sys.stdout.buffer.flush()
        return 0 if good else 1
    finally:
        # An outer command leaf did not acquire this lock. Release it before the
        # maintained outer finalizer runs this same owned home's wrapper --stop.
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("capture", help="fresh fixed official archive producer; never installs/launches")
    admit = actions.add_parser("admit", help="canonical terminal producer and whole-input revalidation")
    admit.add_argument("--producer-receipt", required=True, type=Path)
    admit.add_argument("--producer-purpose", required=True)
    args = parser.parse_args()
    try:
        return execute(args)
    except (Exception, KeyboardInterrupt) as error:
        print("Android archive admission HOLD: " + type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
