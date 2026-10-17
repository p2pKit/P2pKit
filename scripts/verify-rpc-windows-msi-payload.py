#!/usr/bin/env python3
"""Compare MSI application payloads and pinned components statically. Never install, load, sign or run custom actions.

The caller owns the source-bound WiX dark invocation and its fresh extraction directory. This helper
does not prove that arbitrary supplied XML came from an MSI, or grant authority to execute its payload.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET
import zipfile

SCOPE = "MSI_STATIC_COMPONENT_EQUALITY_NOT_INSTALLED_RUNTIME"
IMAGE_SCOPE = "WINDOWS_APP_IMAGE_BYTES_NOT_INSTALLED_OR_RUNTIME_QUALIFIED"
NS = "{http://schemas.microsoft.com/wix/2006/wi}"
DLL = "p2pkit-windows-profile.dll"
PIN = "META-INF/p2pkit/windows-profile-parent.properties"
PARENT_JAR_STEM = "p2pkit-windows-profile-parent-pin"
ADAPTER_JAR = "p2pkit-windows-loader-jdk21.jar"
ADAPTER_PATH = "app/resources/rpc-loader-jdk21/" + ADAPTER_JAR
ADAPTER_MODULE = "dev.p2pkit.rpc.windows.loader"
ADAPTER_SCOPE = "STATIC_JDK21_PREVIEW_MODULE_NOT_LOAD_AUTHORITY"
XML_LIMIT = 8 * 1024 * 1024
MAX_ELEMENTS = 50_000
MAX_MSI = 1024 * 1024 * 1024
IMAGE_METADATA = "app/.jpackage.xml"


class PayloadPathMismatch(ValueError):
    """A refusal with bounded observations of the original unequal sets, not path authority."""
    def __init__(self, installed, payload, pinned):
        super().__init__("MSI and completed image application paths differ")
        missing, extra = set(installed) - set(payload), set(payload) - set(installed)
        self.diagnostic = {
            "imageFiles": len(installed), "msiFiles": len(payload),
            "missingFiles": len(missing), "extraFiles": len(extra),
            "caseFoldEqual": {name.casefold() for name in installed} == {name.casefold() for name in payload},
            "missingNameSha256": sorted(digest(name.encode("utf-8")) for name in missing)[:16],
            "extraNameSha256": sorted(digest(name.encode("utf-8")) for name in extra)[:16],
        }
        # Same already-completed fixed component observations as the passing receipt.
        self.compared_files = [dict(item) for item in pinned]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ordinary(path, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    require(expected and not path.is_symlink() and not getattr(info, "st_file_attributes", 0) & 0x400,
            "Expected an ordinary directory" if directory else "Expected an ordinary file")
    return info


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_mode


def read(path, maximum):
    before = ordinary(path)
    require(0 < before.st_size <= maximum, "Input exceeds its bound")
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    require(len(data) == before.st_size and identity(ordinary(path)) == identity(before),
            "Input changed during inspection")
    return data


def file_hash(path, maximum, *, compose_suffix=False, allow_empty=False):
    before = ordinary(path)
    require((0 <= before.st_size if allow_empty else 0 < before.st_size) and before.st_size <= maximum,
            "Input exceeds its bound")
    total = 0
    hasher = hashlib.sha256()
    # Compose 1.11.1 FileUtilsKt.contentHash uses MD5 only to mangle the filename. Never trust it
    # as payload authority: SHA256 and the source-bound image receipt remain mandatory below.
    name_hasher = hashlib.md5(usedforsecurity=False) if compose_suffix else None
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            total += len(chunk)
            require(total <= before.st_size, "Input grew during inspection")
            hasher.update(chunk)
            if name_hasher is not None:
                name_hasher.update(chunk)
    require(total == before.st_size and identity(ordinary(path)) == identity(before),
            "Input changed during inspection")
    result = {"bytes": total, "sha256": hasher.hexdigest()}
    if name_hasher is not None:
        # Each unsigned byte uses Integer.toHexString, not a zero-padded digest or BigInteger.
        result["composeSuffix"] = "".join(format(byte, "x") for byte in name_hasher.digest())
    return result


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate inspection JSON field")
        result[key] = value
    return result


def component(value):
    require(isinstance(value, str) and 0 < len(value) <= 255 and value not in (".", "..") and
            value[-1] not in (".", " ") and not any(ord(char) < 32 or char in '/\\:<>|?*"' for char in value),
            "Unsafe logical component")
    return value


def beneath(root, parts):
    """Reject links/reparse objects at every traversed extraction/image component; not native custody."""
    ordinary(root, directory=True)
    current = root
    for index, part in enumerate(parts):
        current = current / component(part)
        ordinary(current, directory=index != len(parts) - 1)
    return current


def installation_defaults(product, elements, parents):
    """Validate the observed dark form, not installed ACLs or arbitrary MSI actions."""
    packages = [node for node in elements if node.tag == NS + "Package"]
    require(len(packages) == 1 and parents.get(packages[0]) is product and
            packages[0].get("Platform") == "x64" and
            packages[0].get("InstallScope") in (None, "perMachine"),
            "MSI package must declare unambiguous x64 machine defaults")
    properties = [node for node in elements if node.tag == NS + "Property"]
    all_users = [node for node in properties if node.get("Id") == "ALLUSERS"]
    require(len(all_users) == 1 and parents.get(all_users[0]) is product and
            all_users[0].get("Value") == "1" and
            not any(node.get("Id") in ("MSIINSTALLPERUSER", "WIXUI_INSTALLDIR") for node in properties),
            "MSI machine default or chooser properties conflict")
    require(not any(parents.get(node) is product and node.get("Id") == "INSTALLDIR" and
                    node.get("Value") is not None for node in properties),
            "MSI INSTALLDIR property overrides its directory default")
    directories = {node.get("Id"): node for node in elements if node.tag == NS + "Directory"}
    expected = (("INSTALLDIR", "P2pKit Sample"), ("ProgramFiles64Folder", None), ("TARGETDIR", "SourceDir"))
    current = directories.get("INSTALLDIR")
    for identifier, name in expected:
        require(current is not None and current is directories.get(identifier) and
                current.get("Name") == name, "MSI default installation directory differs")
        current = parents.get(current)
    require(current is product, "MSI default directory is outside the original Product")
    chooser_dialogs = {"InstallDirDlg", "BrowseDlg"}
    for node in elements:
        require(not (node.tag in (NS + "Dialog", NS + "DialogRef") and node.get("Id") in chooser_dialogs),
                "MSI declares an installation directory chooser")
        if node.tag == NS + "Publish":
            require(node.get("Dialog") not in chooser_dialogs and node.get("Value") not in chooser_dialogs and
                    node.get("Property") not in ("INSTALLDIR", "WIXUI_INSTALLDIR") and
                    not (node.get("Event") == "SetTargetPath" and node.get("Value") in
                         ("INSTALLDIR", "WIXUI_INSTALLDIR", "[INSTALLDIR]", "[WIXUI_INSTALLDIR]")),
                    "MSI routes an installation directory chooser")
    return {"scope": "STATIC_MSI_DEFAULTS_NOT_INSTALLED_AUTHORITY", "platform": "x64", "allUsers": "1",
            "directoryChain": [{"id": identifier, "name": name} for identifier, name in reversed(expected)],
            "directoryChooser": "NOT_DECLARED", "administrativeOverrides": "NOT_PREVENTED"}


def file_table(xml):
    text = xml.decode("utf-8-sig")
    require("<!DOCTYPE" not in text.upper() and "<!ENTITY" not in text.upper(),
            "DTD and entity declarations are forbidden")
    root = ET.fromstring(text)
    require(root.tag == NS + "Wix" and len(root.findall(NS + "Product")) == 1,
            "Expected one decompiled MSI Product")
    elements = list(root.iter())
    require(len(elements) <= MAX_ELEMENTS, "Decompiler XML inventory exceeds its bound")
    parents = {child: node for node in elements for child in node}
    directories, file_ids = set(), set()
    rows = []
    for node in elements:
        if node.tag == NS + "Directory":
            identifier = node.get("Id")
            require(identifier and identifier not in directories, "Duplicate or missing Directory identifier")
            directories.add(identifier)
        if node.tag != NS + "File":
            continue
        identifier = node.get("Id", "")
        require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,71}", identifier) and identifier not in file_ids,
                "Duplicate or unsafe File identifier")
        file_ids.add(identifier)
        name = component(node.get("Name"))
        owner = parents.get(node)
        require(owner is not None and owner.tag == NS + "Component", "File lacks its owning Component")
        owner = parents.get(owner)
        parts = [name]
        depth = 0
        while owner is not None and owner.tag == NS + "Directory" and owner.get("Id") != "INSTALLDIR":
            depth += 1
            require(depth <= 64, "Directory nesting exceeds its bound")
            # WiX dark omits Name for MSI's dot directory. It contributes no path segment.
            if owner.get("Name") not in (None, "."):
                parts.append(component(owner.get("Name")))
            owner = parents.get(owner)
        # Non-application files such as shortcuts can exist elsewhere. They cannot supply compared payloads.
        logical = "/".join(reversed(parts)) if (owner is not None and owner.tag == NS + "Directory" and
                                               owner.get("Id") == "INSTALLDIR") else None
        rows.append((name, identifier, node.get("Source", ""), logical))
    require("INSTALLDIR" in directories and rows, "Application Directory/File inventory is missing")
    return rows, installation_defaults(root.find(NS + "Product"), elements, parents)


def pin_content(jar):
    ordinary(jar)
    with zipfile.ZipFile(jar) as archive:
        require(len(archive.infolist()) <= 100_000, "Parent JAR inventory exceeds its bound")
        entries = [entry for entry in archive.infolist() if entry.filename == PIN]
        require(len(entries) == 1 and 0 < entries[0].file_size <= 4096 and not entries[0].flag_bits & 1,
                "Missing, duplicate, encrypted or oversized parent pin")
        with archive.open(entries[0]) as stream:
            data = stream.read(4097)
        require(len(data) == entries[0].file_size, "Parent pin size mismatch")
        return data


def image_inventory(image):
    """Observe ordinary files, not handle custody or installed filesystem policy."""
    ordinary(image, directory=True)
    files, names, pending = {}, set(), [(image, ())]
    while pending:
        directory, parts = pending.pop()
        ordinary(directory, directory=True)
        for path in directory.iterdir():
            relative = (*parts, component(path.name))
            require(len(relative) <= 64 and len(names) < MAX_ELEMENTS, "Image inventory exceeds existing bounds")
            name = "/".join(relative)
            require(name.casefold() not in names, "Image has case-colliding paths")
            names.add(name.casefold())
            if stat.S_ISDIR(path.lstat().st_mode):
                ordinary(path, directory=True)
                pending.append((path, relative))
            else:
                files[name] = file_hash(beneath(image, relative), MAX_MSI, allow_empty=True)
    return files


def extracted_inventory(extracted, rows):
    ordinary(extracted, directory=True)
    folder = extracted / "File"
    ordinary(folder, directory=True)
    members = set()
    for path in folder.iterdir():
        require(len(members) < MAX_ELEMENTS, "Extraction inventory exceeds existing bound")
        ordinary(path)
        members.add(path.name)
    require(members == {row[1] for row in rows}, "Extraction File inventory differs from MSI table")
    result, folded = {}, set()
    for _, identifier, source, target in rows:
        require(target is not None and target.casefold() not in folded,
                "MSI application path is outside INSTALLDIR or duplicated")
        folded.add(target.casefold())
        path = beneath(extracted, ["File", identifier])
        declared = Path(source)
        require(declared.is_absolute() and ".." not in declared.parts and declared == path,
                "Decompiler Source escapes or differs from the owned extraction")
        result[target] = file_hash(path, MAX_MSI, allow_empty=True)
    return result


def full_payload(rows, extracted, image, pinned):
    before = image_inventory(image)
    payload = extracted_inventory(extracted, rows)
    # Source-pinned JDK21 WixAppImageFragmentBuilder excludes exactly AppImageFile's
    # Windows app/.jpackage.xml. No other hidden file or metadata pattern is exempt.
    installed = {name: value for name, value in before.items() if name != IMAGE_METADATA}
    require(all(installed.get(item["target"]) == {"bytes": item["bytes"], "sha256": item["sha256"]}
                for item in pinned), "Full image differs from earlier pinned components")
    if set(payload) != set(installed):
        raise PayloadPathMismatch(installed, payload, pinned)
    require(payload == installed, "MSI application payload differs from completed image")
    require(image_inventory(image) == before and extracted_inventory(extracted, rows) == payload,
            "Application payload changed during full inspection")
    canonical = json.dumps(installed, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return {"scope": "STATIC_APPLICATION_FILES_NOT_INSTALLED_OR_STARTUP_AUTHORITY",
            "files": len(installed), "bytes": sum(value["bytes"] for value in installed.values()),
            "inventorySha256": digest(canonical),
            "excludedImageMetadata": ([{"target": IMAGE_METADATA, **before[IMAGE_METADATA]}]
                                      if IMAGE_METADATA in before else [])}


def inspect(wxs, extracted, image, inspection, msi):
    xml = read(wxs, XML_LIMIT)
    receipt_bytes = read(inspection, 65_536)
    receipt = json.loads(receipt_bytes, object_pairs_hook=unique_object)
    require(isinstance(receipt, dict) and receipt.get("scope") == IMAGE_SCOPE and receipt.get("result") == "PASS",
            "A passing current application-image inspection is required")
    require(all(isinstance(receipt.get(key), str) and re.fullmatch(r"[a-f0-9]{40}", receipt[key])
                for key in ("source", "tree")), "Full source/tree pins required")
    require(all(isinstance(receipt.get(key), str) and re.fullmatch(r"[a-f0-9]{64}", receipt[key])
                for key in ("dllSha256", "manifestSha256")), "Missing image component pins")
    parent = receipt.get("parentPin")
    require(isinstance(parent, dict) and
            all(isinstance(parent.get(key), str) and re.fullmatch(r"[a-f0-9]{64}", parent[key])
                for key in ("pinSha256", "jarSha256")) and type(parent.get("jarBytes")) is int and
            0 < parent["jarBytes"] <= 512 * 1024 * 1024, "Missing parent pin observation")
    parent_name = component(parent.get("file"))
    require(re.fullmatch(re.escape(PARENT_JAR_STEM) + r"(?:-[a-f0-9]{16,32})?\.jar", parent_name),
            "Unexpected parent-pin JAR")
    msi_observation = file_hash(msi, MAX_MSI)
    require(receipt.get("msi") == {"file": msi.name, **msi_observation}, "MSI differs from image inspection")
    rows, defaults = file_table(xml)
    expected = [(DLL, "app/resources/rpc-profile/windows-x64/" + DLL, 32 * 1024 * 1024,
                 receipt["dllSha256"]),
                ("component.manifest", "app/resources/rpc-profile/windows-x64/component.manifest", 4096,
                 receipt["manifestSha256"]),
                (parent_name, "app/" + parent_name, 512 * 1024 * 1024, None)]
    adapter = None
    if "adapter" in receipt:
        adapter = receipt["adapter"]
        require(isinstance(adapter, dict) and adapter.get("scope") == ADAPTER_SCOPE and
                adapter.get("file") == ADAPTER_PATH and adapter.get("module") == ADAPTER_MODULE and
                type(adapter.get("probeMajor")) is int and adapter["probeMajor"] == 65 and
                type(adapter.get("probeMinor")) is int and adapter["probeMinor"] == 65535 and
                adapter.get("nativeExecution") == "NOT_PERFORMED" and
                adapter.get("installedAuthority") == "NOT_ESTABLISHED" and
                type(adapter.get("jarBytes")) is int and 0 < adapter["jarBytes"] <= 16 * 1024 * 1024 and
                isinstance(adapter.get("jarSha256"), str) and
                re.fullmatch(r"[a-f0-9]{64}", adapter["jarSha256"]), "Invalid preview adapter image observation")
        expected.append((ADAPTER_JAR, ADAPTER_PATH, 16 * 1024 * 1024, adapter["jarSha256"]))
    else:
        require(not any(row[0].casefold() == ADAPTER_JAR.casefold() for row in rows),
                "MSI adapter has no optional image observation")
    comparisons = []
    extracted = extracted.absolute()
    image = image.absolute()
    for name, target, maximum, expected_hash in expected:
        matching = [row for row in rows if row[0].casefold() == name.casefold()]
        require(len(matching) == 1 and matching[0][0] == name and matching[0][3] == target,
                "Missing, duplicate or misplaced MSI component")
        _, identifier, source, _ = matching[0]
        extracted_file = beneath(extracted, ["File", identifier])
        # WiX 3 dark -x writes compressed files as File/<File.Id>, not their installed names.
        source_path = Path(source)
        require(source_path.is_absolute() and ".." not in source_path.parts and source_path == extracted_file,
                "Decompiler Source escapes or differs from the owned extraction")
        image_file = beneath(image, target.split("/"))
        image_observation = file_hash(image_file, maximum, compose_suffix=name == parent_name)
        compose_suffix = image_observation.pop("composeSuffix", None)
        require(expected_hash is None or image_observation["sha256"] == expected_hash,
                "App image component changed after inspection")
        if name == DLL:
            require(image_observation["bytes"] == receipt.get("dllBytes"), "App image DLL size pin mismatch")
        if name == ADAPTER_JAR:
            require(image_observation == {"bytes": adapter["jarBytes"], "sha256": adapter["jarSha256"]},
                    "App image adapter JAR changed after inspection")
        if name == parent_name:
            require(image_observation == {"bytes": parent["jarBytes"], "sha256": parent["jarSha256"]},
                    "App image parent JAR changed after inspection")
            # Accept only the original producer name or its exact Compose content-derived mangling.
            require(parent_name in (PARENT_JAR_STEM + ".jar", PARENT_JAR_STEM + "-" + compose_suffix + ".jar"),
                    "Parent-pin JAR filename differs from Compose content mangling")
            require(digest(pin_content(image_file)) == parent["pinSha256"], "App image parent pin changed")
        require(file_hash(extracted_file, maximum) == image_observation,
                "MSI component payload differs from the app image")
        comparisons.append({"target": target, "extractedMember": "File/" + identifier, **image_observation})
    application_payload = full_payload(rows, extracted, image, comparisons)
    require(file_hash(msi, MAX_MSI) == msi_observation and read(wxs, XML_LIMIT) == xml and
            read(inspection, 65_536) == receipt_bytes, "Inspection inputs changed before final observation")
    return {"scope": SCOPE, "result": "PASS", "source": receipt["source"], "tree": receipt["tree"],
            "msi": {"file": msi.name, **msi_observation}, "wxsSha256": digest(xml),
            "imageInspectionSha256": digest(receipt_bytes), "comparedFiles": comparisons,
            "installationDefaults": defaults,
            "extractionInvocation": "CALLER_OWNED_SOURCE_BOUND_DARK_RUN_REQUIRED",
            "fullApplicationPayloadEquality": "PASS", "applicationPayload": application_payload,
            "installation": "NOT_PERFORMED",
            "nativeExecution": "NOT_PERFORMED", "runtimeQualification": "NOT_PERFORMED",
            "signing": "NOT_PERFORMED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("wxs", "extracted", "image", "inspection", "msi", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.wxs, args.extracted, args.image, args.inspection, args.msi)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(SCOPE + ": PASS")


if __name__ == "__main__":
    main()
