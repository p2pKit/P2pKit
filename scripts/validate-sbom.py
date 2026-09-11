#!/usr/bin/python3
"""Validate paired release graphs, not the entire CycloneDX schema or binaries."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn


MAX_BYTES = 16 * 1024 * 1024
NAMESPACE = "http://cyclonedx.org/schema/bom/1.6"
MODULES = frozenset((
    "p2p-core", "p2p-transport-lan", "p2p-network-provisioning-android",
    "p2p-network-provisioning-desktop",
))
REQUIRED = MODULES | {
    "kotlinx-coroutines-core", "jmdns", "slf4j-api", "cryptography-provider-jdk-jvm",
    "cryptography-provider-cryptokit-iosarm64", "cryptography-provider-cryptokit-iossimulatorarm64",
    "cryptography-provider-cryptokit-iosx64",
}
CONTAMINATION = ("/Users/", "/home/", "p2p-sample", "dokka-base", "gradle-api")
IDENTITY_FIELDS = ("type", "group", "name", "version", "purl", "cpe")
ROOT = Path(__file__).resolve().parents[1]
VENDOR_RELATIVE = Path("library/p2p-transport-lan/vendor/jmdns")
PRODUCER_RELATIVE = Path("library/p2p-transport-lan/build/embedded-jmdns/p2pkit-internal-jmdns.jar")
PRIVATE_NAMESPACE = "dev.p2pkit.transport.lan.internal.jmdns"
PRIVATE_PATH = PRIVATE_NAMESPACE.replace(".", "/")
NOTICE_PATH = "META-INF/p2pkit/third-party/jmdns"
PATCH_PATH = "patches/410-lifecycle.patch"
FOLLOWUP_PATCH_PATHS = ("patches/415-opt-rcode.patch",)
EMBEDDED_IDENTITY = {
    "group": "dev.p2pkit.internal", "name": "jmdns", "version": "3.6.3-p2pkit.410.2",
    "bomRef": "urn:p2pkit:embedded:jmdns:3.6.3-p2pkit.410.2",
    "purl": "pkg:generic/p2pkit/jmdns@3.6.3-p2pkit.410.2",
}
UPSTREAM = {
    "mavenCoordinate": "org.jmdns:jmdns:3.6.3", "purl": "pkg:maven/org.jmdns/jmdns@3.6.3",
    "sourceUrl": "https://repo.maven.apache.org/maven2/org/jmdns/jmdns/3.6.3/jmdns-3.6.3-sources.jar",
    "binarySha256": "6b6eb1623cb1d9e51467312ea62c567da005c2aa5a95347f566a11b8703c0ef1",
    "sourceSha256": "cad6d4c88381bcc2a70da44b8d2818b0e300e7d56ceb5263df7cee96e1a08cfb",
    "tag": "v3.6.3", "commit": "93b326381940f3fcd250d770a14a36de4c2dfcda",
    "tree": "3c5c49ea18184f2cffdee3ef76203e0f0977dfe6",
    "notice": {"path": "NOTICE.txt",
               "sha256": "4fce3bc043f1f950be796ecae804e0d26765343a49af11b23d62a3328f4c0d11", "sizeBytes": 775},
}
NORMALIZATION = {"lineEndings": "LF", "javaTrailingWhitespace": "removed", "noticeTrailingWhitespace": "removed"}
RESOURCE_ENTRIES = {
    "LICENSE": "META-INF/LICENSE",
    "MODIFICATIONS.txt": f"{NOTICE_PATH}/MODIFICATIONS.txt",
    "NOTICE.txt": f"{NOTICE_PATH}/NOTICE.txt",
    f"src/main/resources/{PRIVATE_PATH}/version.properties": f"{PRIVATE_PATH}/version.properties",
}
PROPERTY_PREFIX = "p2pkit:embedded-jmdns:"


class SbomError(ValueError):
    pass


def invalid(kind: str, reason: str) -> NoReturn:
    raise SbomError(f"{kind} SBOM content gate failed: {reason}")


def read_bounded(path: str, kind: str) -> bytes:
    # Bound the read itself, including growth after open; do not stat then read().
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        invalid(kind, f"input must contain 1..{MAX_BYTES} bytes")
    return raw


def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            invalid("JSON", "duplicate object key")
        result[key] = value
    return result


def no_nonfinite(value: str) -> NoReturn:
    invalid("JSON", "non-finite number")


class NoDtdBuilder(ET.TreeBuilder):
    def doctype(self, name: str, public_id: str, system_id: str) -> NoReturn:
        # A parser callback covers UTF-16 declarations as well as UTF-8.
        invalid("XML", "DTD/entity declarations are forbidden")


def text(value: Any, kind: str, field: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        invalid(kind, f"missing or invalid {field}")
    return value


def array(value: Any, kind: str, field: str) -> list:
    if not isinstance(value, list):
        invalid(kind, f"invalid {field} list")
    return value


def json_document(raw: bytes, kind: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=no_duplicate_keys,
                           parse_constant=no_nonfinite)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as error:
        invalid(kind, f"parser error ({type(error).__name__})")
    if not isinstance(value, dict):
        invalid(kind, "root is not an object")
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(read_bounded(str(path), "Vendor provenance")).hexdigest()


def normalized_sha256(path: Path) -> str:
    raw = read_bounded(str(path), "Vendor provenance")
    if b"\r" in raw or re.search(rb"[ \t]+(?:\n|$)", raw):
        invalid("Vendor provenance", "declared LF/trailing-whitespace normalization differs from actual bytes")
    return hashlib.sha256(raw).hexdigest()


def vendor_file(directory: Path, relative: Any) -> Path:
    relative = text(relative, "Vendor provenance", "file path")
    path = PurePosixPath(relative)
    if (path.is_absolute() or str(path) != relative or ".." in path.parts or
            not re.fullmatch(r"[A-Za-z0-9_./-]+", relative)):
        invalid("Vendor provenance", "unsafe or non-normalized file path")
    candidate = directory
    for part in path.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            invalid("Vendor provenance", "symlinked vendor input")
    if not candidate.is_file():
        invalid("Vendor provenance", f"missing file {relative}")
    return candidate


def sha256_text(value: Any, field: str) -> str:
    value = text(value, "Vendor provenance", field)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        invalid("Vendor provenance", f"invalid {field}")
    return value


def source_roster(directory: Path, relative: str) -> list[str]:
    entries = list((directory / relative).rglob("*"))
    if any(path.is_symlink() for path in entries):
        invalid("Vendor provenance", "unaccounted or symlinked source-tree input")
    return sorted(path.relative_to(directory).as_posix() for path in entries if path.is_file())


def load_vendor_manifest(directory: Path) -> tuple[dict, str]:
    """Check the reviewed source manifest against actual bytes, not a second copy of its claims."""
    directory = Path(directory)
    if directory.is_symlink():
        invalid("Vendor provenance", "symlinked vendor directory")
    raw = read_bounded(str(vendor_file(directory, "PROVENANCE.json")), "Vendor provenance")
    manifest = json_document(raw, "Vendor provenance")
    if (set(manifest) != {"schema", "component", "upstream", "relocation", "normalization", "sources", "resources",
                         "lifecyclePatch", "followupPatches", "manifestEntry"} or type(manifest.get("schema")) is not int or
            manifest["schema"] != 2 or manifest.get("component") != EMBEDDED_IDENTITY or
            manifest.get("upstream") != UPSTREAM or
            manifest.get("normalization") != NORMALIZATION or
            manifest.get("relocation") != {"from": "javax.jmdns", "to": PRIVATE_NAMESPACE} or
            manifest.get("manifestEntry") != f"{NOTICE_PATH}/PROVENANCE.json"):
        invalid("Vendor provenance", "wrong schema, component, ancestry or relocation identity")

    sources = array(manifest.get("sources"), "Vendor provenance", "sources")
    source_paths, upstream_paths = [], set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {
                "path", "upstreamPath", "upstreamSha256", "relocatedSha256", "sha256"}:
            invalid("Vendor provenance", "invalid source record")
        path = source["path"]
        actual = vendor_file(directory, path)
        if not path.startswith(f"src/main/java/{PRIVATE_PATH}/") or not path.endswith(".java"):
            invalid("Vendor provenance", "source lies outside the private Java namespace")
        source_paths.append(path)
        if normalized_sha256(actual) != sha256_text(source["sha256"], "modified source SHA-256"):
            invalid("Vendor provenance", f"modified source hash differs: {path}")
        originals = [source[key] for key in ("upstreamPath", "upstreamSha256", "relocatedSha256")]
        if any(value is None for value in originals):
            if originals != [None, None, None]:
                invalid("Vendor provenance", "new source must omit all three original/baseline fields")
        else:
            expected = path.replace(f"src/main/java/{PRIVATE_PATH}/", "src/main/java/javax/jmdns/", 1)
            if source["upstreamPath"] != expected or expected in upstream_paths:
                invalid("Vendor provenance", "duplicate or incorrect upstream source path")
            upstream_paths.add(expected)
            sha256_text(source["upstreamSha256"], "upstream source-file SHA-256")
            sha256_text(source["relocatedSha256"], "relocated baseline SHA-256")
    actual_sources = source_roster(directory, "src/main/java")
    if (source_paths != sorted(set(source_paths)) or source_paths != actual_sources or len(upstream_paths) != 59):
        invalid("Vendor provenance", "source roster must cover all files and the 59 qualified upstream sources")

    resources = array(manifest.get("resources"), "Vendor provenance", "resources")
    resource_paths = []
    for resource in resources:
        if not isinstance(resource, dict) or set(resource) != {"path", "entry", "sha256"}:
            invalid("Vendor provenance", "invalid resource record")
        path = resource["path"]
        actual = vendor_file(directory, path)
        if path not in RESOURCE_ENTRIES or resource["entry"] != RESOURCE_ENTRIES[path]:
            invalid("Vendor provenance", "wrong resource archive entry")
        resource_paths.append(path)
        actual_sha256 = normalized_sha256(actual) if path == "NOTICE.txt" else file_sha256(actual)
        if actual_sha256 != sha256_text(resource["sha256"], "resource SHA-256"):
            invalid("Vendor provenance", f"resource hash differs: {path}")
    if resource_paths != sorted(RESOURCE_ENTRIES):
        invalid("Vendor provenance", "resource roster is missing, duplicate or unsorted")
    actual_resources = set(source_roster(directory, "src/main/resources"))
    if actual_resources != {path for path in RESOURCE_ENTRIES if path.startswith("src/main/resources/")}:
        invalid("Vendor provenance", "unaccounted private source resource")

    patch = manifest.get("lifecyclePatch")
    if not isinstance(patch, dict) or set(patch) != {"path", "sha256"} or patch["path"] != PATCH_PATH:
        invalid("Vendor provenance", "invalid lifecycle patch identity")
    if file_sha256(vendor_file(directory, patch["path"])) != sha256_text(patch["sha256"], "patch SHA-256"):
        invalid("Vendor provenance", "lifecycle patch hash differs")
    followups = array(manifest.get("followupPatches"), "Vendor provenance", "followupPatches")
    for followup in followups:
        if (not isinstance(followup, dict) or set(followup) != {"path", "sha256"} or
                followup["path"] not in FOLLOWUP_PATCH_PATHS):
            invalid("Vendor provenance", "invalid followup patch identity")
        if (file_sha256(vendor_file(directory, followup["path"])) !=
                sha256_text(followup["sha256"], "followup patch SHA-256")):
            invalid("Vendor provenance", "followup patch hash differs")
    if [followup["path"] for followup in followups] != list(FOLLOWUP_PATCH_PATHS):
        invalid("Vendor provenance", "wrong followup patch order or membership")
    if source_roster(directory, "patches") != sorted((PATCH_PATH, *FOLLOWUP_PATCH_PATHS)):
        invalid("Vendor provenance", "patch roster contains undeclared or missing files")
    return manifest, hashlib.sha256(raw).hexdigest()


def upstream_component() -> dict:
    return {"bom-ref": UPSTREAM["purl"], "type": "library", "group": "org.jmdns", "name": "jmdns",
            "version": "3.6.3", "purl": UPSTREAM["purl"],
            "hashes": [{"alg": "SHA-256", "content": UPSTREAM["binarySha256"]}]}


def embedded_component(manifest: dict, manifest_sha256: str, producer_sha256: str) -> dict:
    ancestor = upstream_component()
    ancestor["externalReferences"] = [
        {"type": "source-distribution", "url": UPSTREAM["sourceUrl"],
         "hashes": [{"alg": "SHA-256", "content": UPSTREAM["sourceSha256"]}]},
        {"type": "vcs", "url": f"https://github.com/jmdns/jmdns/tree/{UPSTREAM['commit']}"},
    ]
    properties = {
        "hash-scope": "private-producer-jar", "namespace": PRIVATE_NAMESPACE,
        "provenance-path": f"{VENDOR_RELATIVE.as_posix()}/PROVENANCE.json",
        "source-manifest-sha256": manifest_sha256, "upstream-source-sha256": UPSTREAM["sourceSha256"],
        "lifecycle-patch-sha256": manifest["lifecyclePatch"]["sha256"],
        "upstream-commit": UPSTREAM["commit"], "upstream-tree": UPSTREAM["tree"],
    }
    properties.update({f"followup-patch-sha256:{patch['path']}": patch["sha256"]
                       for patch in manifest["followupPatches"]})
    patches = [manifest["lifecyclePatch"], *manifest["followupPatches"]]
    return {
        "bom-ref": EMBEDDED_IDENTITY["bomRef"], "type": "library",
        **{key: EMBEDDED_IDENTITY[key] for key in ("group", "name", "version", "purl")},
        "hashes": [{"alg": "SHA-256", "content": producer_sha256}], "modified": True,
        "pedigree": {"ancestors": [ancestor], "patches": [
            {"type": "unofficial", "diff": {"url": f"{VENDOR_RELATIVE.as_posix()}/{patch['path']}"}}
            for patch in patches
        ]},
        "properties": [{"name": PROPERTY_PREFIX + key, "value": value} for key, value in sorted(properties.items())],
    }


def upstream_inventory(manifest_sha256: str) -> dict:
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
        "metadata": {"properties": [
            {"name": PROPERTY_PREFIX + "inventory-purpose", "value": "upstream-advisory-ancestry-only"},
            {"name": PROPERTY_PREFIX + "source-manifest-sha256", "value": manifest_sha256},
        ]},
        "components": [upstream_component()],
    }


def validate_upstream_inventory(path: Path, vendor_directory: Path) -> None:
    _, manifest_sha256 = load_vendor_manifest(vendor_directory)
    document = json_document(read_bounded(str(path), "Upstream advisory inventory"), "Upstream advisory inventory")
    if (type(document.get("version")) is not int or document != upstream_inventory(manifest_sha256)):
        invalid("Upstream advisory inventory", "wrong upstream identity or stale vendor provenance binding")


def hash_table(values: Any, kind: str) -> tuple:
    hashes = {}
    for digest in array(values, kind, "hashes"):
        if not isinstance(digest, dict) or set(digest) != {"alg", "content"}:
            invalid(kind, "invalid component hash")
        algorithm = text(digest.get("alg"), kind, "hash algorithm")
        content = text(digest.get("content"), kind, "hash content")
        if algorithm in hashes or not re.fullmatch(r"[0-9a-fA-F]+", content):
            invalid(kind, "duplicate or invalid component hash")
        hashes[algorithm] = content.lower()
    return tuple(sorted(hashes.items()))


def property_table(values: Any, kind: str) -> tuple:
    properties = {}
    for entry in array(values, kind, "properties"):
        if not isinstance(entry, dict) or set(entry) != {"name", "value"}:
            invalid(kind, "invalid provenance property")
        name = text(entry["name"], kind, "property name")
        value = text(entry["value"], kind, "property value")
        if name in properties:
            invalid(kind, "duplicate provenance property")
        properties[name] = value
    return tuple(sorted(properties.items()))


def embedded_provenance(value: dict, kind: str) -> tuple:
    if value.get("modified") is not True or value.get("externalReferences") not in (None, []):
        invalid(kind, "embedded component must explicitly declare its reviewed modification")
    pedigree = value.get("pedigree")
    if not isinstance(pedigree, dict) or set(pedigree) != {"ancestors", "patches"}:
        invalid(kind, "missing or invalid embedded pedigree")
    ancestors = array(pedigree["ancestors"], kind, "ancestors")
    patches = array(pedigree["patches"], kind, "patches")
    if len(ancestors) != 1 or len(patches) != 1 + len(FOLLOWUP_PATCH_PATHS):
        invalid(kind, "embedded pedigree must contain one upstream ancestor and every reviewed local patch")
    ancestor = ancestors[0]
    if not isinstance(ancestor, dict) or set(ancestor) - {
            "bom-ref", *IDENTITY_FIELDS, "hashes", "externalReferences"}:
        invalid(kind, "invalid upstream ancestor")
    ancestor_identity = component(ancestor, kind, include_provenance=False)
    references = []
    for reference in array(ancestor.get("externalReferences"), kind, "ancestor externalReferences"):
        if not isinstance(reference, dict) or set(reference) - {"type", "url", "hashes"}:
            invalid(kind, "invalid upstream external reference")
        references.append((text(reference.get("type"), kind, "external reference type"),
                           text(reference.get("url"), kind, "external reference URL"),
                           hash_table(reference.get("hashes", []), kind)))
    if len(references) != len(set(references)):
        invalid(kind, "duplicate upstream external reference")
    patch_urls = []
    for patch in patches:
        if (not isinstance(patch, dict) or set(patch) != {"type", "diff"} or
                patch.get("type") != "unofficial" or not isinstance(patch.get("diff"), dict) or
                set(patch["diff"]) != {"url"}):
            invalid(kind, "invalid local pedigree patch")
        patch_urls.append(text(patch["diff"]["url"], kind, "patch URL"))
    if len(patch_urls) != len(set(patch_urls)):
        invalid(kind, "duplicate local pedigree patch")
    return (property_table(value.get("properties"), kind), ancestor_identity,
            tuple(sorted(references)), tuple(patch_urls))


def component(value: Any, kind: str, include_provenance: bool = True) -> tuple[str, tuple]:
    if not isinstance(value, dict):
        invalid(kind, "invalid component")
    # The configured aggregate is flat. Do not silently ignore nested nodes.
    if "components" in value and array(value["components"], kind, "nested components"):
        invalid(kind, "nested components are not supported by the release graph")
    ref = text(value.get("bom-ref"), kind, "component bom-ref")
    identity = tuple(text(value.get(key), kind, key, key not in ("type", "name"))
                     for key in IDENTITY_FIELDS)
    provenance = embedded_provenance(value, kind) if include_provenance and value.get("name") == "jmdns" else None
    return ref, (identity, hash_table(value.get("hashes", []), kind), provenance)


def component_table(values: list, root_ref: str, kind: str) -> dict:
    result = {}
    for value in values:
        ref, identity = component(value, kind)
        if ref == root_ref or ref in result:
            invalid(kind, "duplicate component bom-ref")
        result[ref] = identity
    return result


def graph(entries: list, refs: set[str], kind: str) -> dict:
    # Absent leaf entries and explicit empty entries describe the same graph.
    result = {ref: frozenset() for ref in refs}
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - {"ref", "dependsOn"}:
            invalid(kind, "invalid dependency entry")
        ref = text(entry.get("ref"), kind, "dependency ref")
        children = array(entry.get("dependsOn", []), kind, "dependsOn")
        children = [text(child, kind, "dependency target") for child in children]
        if ref not in refs or ref in seen or len(children) != len(set(children)) or set(children) - refs:
            invalid(kind, "duplicate or unresolved dependency reference")
        seen.add(ref)
        result[ref] = frozenset(children)
    return result


def elements(parent: ET.Element) -> list[ET.Element]:
    return [child for child in parent if isinstance(child.tag, str)]


def child(parent: ET.Element, name: str, optional: bool = False) -> ET.Element | None:
    matches = parent.findall(f"{{{NAMESPACE}}}{name}")
    if len(matches) > 1 or (not matches and not optional):
        invalid("XML", f"missing or duplicate {name}")
    return matches[0] if matches else None


def simple_content(node: ET.Element) -> str:
    if elements(node):
        invalid("XML", "invalid simple content")
    # Comments/PIs carry no value, but their tails are part of the element's
    # string value. Looking only at node.text silently truncates that value.
    return (node.text or "") + "".join(child.tail or "" for child in node)


def leaf(parent: ET.Element, name: str) -> str | None:
    node = child(parent, name, optional=True)
    if node is None:
        return None
    if elements(node) or node.attrib:
        invalid("XML", f"invalid {name} leaf")
    return simple_content(node)


def xml_hashes(parent: ET.Element) -> list:
    result = []
    hashes = child(parent, "hashes", optional=True)
    if hashes is not None:
        for digest in elements(hashes):
            if digest.tag != f"{{{NAMESPACE}}}hash" or elements(digest) or set(digest.attrib) != {"alg"}:
                invalid("XML", "invalid component hash")
            result.append({"alg": digest.get("alg"), "content": simple_content(digest)})
    return result


def xml_external_references(parent: ET.Element) -> list:
    container = child(parent, "externalReferences", optional=True)
    result = []
    if container is not None:
        for reference in elements(container):
            if (reference.tag != f"{{{NAMESPACE}}}reference" or set(reference.attrib) != {"type"} or
                    any(node.tag not in {f"{{{NAMESPACE}}}url", f"{{{NAMESPACE}}}hashes"}
                        for node in elements(reference))):
                invalid("XML", "invalid upstream external reference")
            result.append({"type": reference.get("type"), "url": leaf(reference, "url"),
                           "hashes": xml_hashes(reference)})
    return result


def xml_embedded_provenance(node: ET.Element) -> dict:
    modified = leaf(node, "modified")
    if modified not in ("true", "1"):
        invalid("XML", "embedded component must explicitly declare its reviewed modification")
    properties = []
    for entry in elements(child(node, "properties")):
        if entry.tag != f"{{{NAMESPACE}}}property" or set(entry.attrib) != {"name"} or elements(entry):
            invalid("XML", "invalid provenance property")
        properties.append({"name": entry.get("name"), "value": simple_content(entry)})
    pedigree = child(node, "pedigree")
    if any(entry.tag not in {f"{{{NAMESPACE}}}ancestors", f"{{{NAMESPACE}}}patches"}
           for entry in elements(pedigree)):
        invalid("XML", "invalid embedded pedigree")
    ancestors = []
    for ancestor in elements(child(pedigree, "ancestors")):
        if (ancestor.tag != f"{{{NAMESPACE}}}component" or set(ancestor.attrib) != {"type", "bom-ref"} or
                any(entry.tag not in {f"{{{NAMESPACE}}}{name}"
                                     for name in (*IDENTITY_FIELDS[1:], "hashes", "externalReferences")}
                    for entry in elements(ancestor))):
            invalid("XML", "invalid upstream ancestor")
        value = xml_component(ancestor, include_provenance=False)
        value["externalReferences"] = xml_external_references(ancestor)
        ancestors.append(value)
    patches = []
    for patch in elements(child(pedigree, "patches")):
        if (patch.tag != f"{{{NAMESPACE}}}patch" or set(patch.attrib) != {"type"} or
                any(entry.tag != f"{{{NAMESPACE}}}diff" for entry in elements(patch))):
            invalid("XML", "invalid local pedigree patch")
        diff = child(patch, "diff")
        if diff.attrib or any(entry.tag != f"{{{NAMESPACE}}}url" for entry in elements(diff)):
            invalid("XML", "invalid local pedigree patch diff")
        patches.append({"type": patch.get("type"), "diff": {"url": leaf(diff, "url")}})
    return {"modified": True, "properties": properties,
            "pedigree": {"ancestors": ancestors, "patches": patches},
            "externalReferences": xml_external_references(node)}


def xml_component(node: ET.Element, include_provenance: bool = True) -> dict:
    value = {"type": node.get("type"), "bom-ref": node.get("bom-ref")}
    value.update({key: leaf(node, key) for key in IDENTITY_FIELDS if key != "type"})
    nested = child(node, "components", optional=True)
    if nested is not None and elements(nested):
        invalid("XML", "nested components are not supported by the release graph")
    value["hashes"] = xml_hashes(node)
    if include_provenance and value.get("name") == "jmdns":
        value.update(xml_embedded_provenance(node))
    return value


def xml_graph(root: ET.Element) -> list:
    entries = []
    for node in elements(child(root, "dependencies")):
        if node.tag != f"{{{NAMESPACE}}}dependency" or set(node.attrib) != {"ref"}:
            invalid("XML", "invalid dependency entry")
        targets = []
        for target in elements(node):
            if (target.tag != f"{{{NAMESPACE}}}dependency" or elements(target) or
                    set(target.attrib) != {"ref"}):
                invalid("XML", "invalid dependency target")
            targets.append(target.get("ref"))
        entries.append({"ref": node.get("ref"), "dependsOn": targets})
    return entries


def check_contamination(document: dict, root: ET.Element, raw_inputs: tuple[bytes, bytes]) -> None:
    def check(value: Any) -> None:
        if isinstance(value, str) and any(token in value for token in CONTAMINATION):
            raise SbomError("SBOM leaks a workstation path or includes sample/build dependencies")

    for raw in raw_inputs:
        if any(token.encode("ascii") in raw for token in CONTAMINATION):
            raise SbomError("SBOM leaks a workstation path or includes sample/build dependencies")
    pending = [document]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        else:
            check(value)
    for node in root.iter():
        for value in (node.text, node.tail, *node.attrib.values()):
            check(value)


def validate(json_path: str, xml_path: str, group: str, version: str,
             vendor_directory: Path | None = None, producer_path: Path | None = None) -> int:
    json_raw = read_bounded(json_path, "JSON")
    xml_raw = read_bounded(xml_path, "XML")
    document = json_document(json_raw, "JSON")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("component"), dict):
        invalid("JSON", "missing root component")
    root_component = metadata["component"]
    root_ref, root_identity = component(root_component, "JSON")
    revision = document.get("version")
    if (document.get("bomFormat") != "CycloneDX" or document.get("specVersion") != "1.6" or
            type(revision) is not int or revision < 1 or
            [root_component.get(key) for key in ("type", "group", "name", "version")] !=
            ["library", group, "p2pkit", version]):
        invalid("JSON", "wrong format or release identity")
    values = array(document.get("components"), "JSON", "components")
    components = component_table(values, root_ref, "JSON")
    names = {value.get("name") for value in values}
    published = [value for value in values if value.get("group") == group and value.get("name") in MODULES]
    if (not REQUIRED <= names or len(published) != 4 or {c["name"] for c in published} != MODULES or
            any(c.get("version") != version for c in published)):
        invalid("JSON", "required release components are missing or incorrect")
    refs = set(components) | {root_ref}
    dependencies = graph(array(document.get("dependencies"), "JSON", "dependencies"), refs, "JSON")
    if dependencies[root_ref] != {c["bom-ref"] for c in published}:
        invalid("JSON", "root must link exactly to the four published modules")

    manifest, manifest_sha256 = load_vendor_manifest(vendor_directory or ROOT / VENDOR_RELATIVE)
    producer_sha256 = file_sha256(producer_path or ROOT / PRODUCER_RELATIVE)
    expected_ref, expected_component = component(embedded_component(manifest, manifest_sha256, producer_sha256), "JSON")
    embedded = [value for value in values if value.get("name") == "jmdns"]
    if (len(embedded) != 1 or components.get(expected_ref) != expected_component or
            UPSTREAM["purl"] in refs or any(value.get("group") == "unspecified" for value in values)):
        invalid("JSON", "embedded JmDNS identity, producer hash or provenance differs from verified vendor inputs")
    slf4j = [value for value in values if value.get("group") == "org.slf4j" and value.get("name") == "slf4j-api"]
    lan_ref = next(value["bom-ref"] for value in published if value["name"] == "p2p-transport-lan")
    if (len(slf4j) != 1 or slf4j[0].get("version") != "2.0.7" or expected_ref not in dependencies[lan_ref] or
            dependencies[expected_ref] != {slf4j[0]["bom-ref"]}):
        invalid("JSON", "required LAN -> embedded JmDNS -> resolved SLF4J API edges are missing or incorrect")

    try:
        parser = ET.XMLParser(target=NoDtdBuilder(insert_comments=True, insert_pis=True))
        root = ET.fromstring(xml_raw, parser=parser)
    except ET.ParseError as error:
        invalid("XML", f"parser error ({error})")
    if root.tag != f"{{{NAMESPACE}}}bom":
        invalid("XML", "wrong CycloneDX namespace/root")
    xml_revision = root.get("version", "").strip()
    if (not re.fullmatch(r"\+?[0-9]+", xml_revision) or int(xml_revision) != revision or
            root.get("serialNumber") != document.get("serialNumber")):
        invalid("XML", "document revision/serial number differs from JSON")
    xml_root_ref, xml_root_identity = component(xml_component(child(child(root, "metadata"), "component")), "XML")
    if (xml_root_ref, xml_root_identity) != (root_ref, root_identity):
        invalid("XML", "root release identity differs from JSON")
    xml_values = []
    for node in elements(child(root, "components")):
        if node.tag != f"{{{NAMESPACE}}}component":
            invalid("XML", "invalid component element")
        xml_values.append(xml_component(node))
    if component_table(xml_values, root_ref, "XML") != components:
        invalid("XML", "component references, coordinates, hashes or required provenance differ from JSON")
    if graph(xml_graph(root), refs, "XML") != dependencies:
        invalid("XML", "dependency graph differs from JSON")
    check_contamination(document, root, (json_raw, xml_raw))
    return len(components)


def main(arguments: list[str]) -> int:
    if arguments == ["--upstream-inventory"]:
        try:
            validate_upstream_inventory(ROOT / VENDOR_RELATIVE / "upstream.cdx.json", ROOT / VENDOR_RELATIVE)
        except (SbomError, OSError) as error:
            print(f"FATAL: {error}", file=sys.stderr)
            return 1
        print("RESULT: PASS — upstream advisory inventory is bound to verified embedded JmDNS provenance")
        return 0
    if len(arguments) != 4:
        print("Usage: validate-sbom.py <json> <xml> <group> <version> | --upstream-inventory", file=sys.stderr)
        return 2
    try:
        count = validate(*arguments)
    except (SbomError, OSError) as error:
        print(f"FATAL: {error}", file=sys.stderr)
        return 1
    print(f"RESULT: PASS — CycloneDX 1.6 JSON/XML SBOM contains {count} release components, "
          "a connected four-module root, verified embedded JmDNS provenance, and no build/sample contamination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
