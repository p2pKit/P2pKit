#!/usr/bin/python3
"""Validate paired release graphs, not the entire CycloneDX schema or binaries."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, NoReturn


MAX_BYTES = 16 * 1024 * 1024
NAMESPACE = "http://cyclonedx.org/schema/bom/1.6"
MODULES = frozenset((
    "p2p-core", "p2p-transport-lan", "p2p-network-provisioning-android",
    "p2p-network-provisioning-desktop",
))
REQUIRED = MODULES | {
    "kotlinx-coroutines-core", "jmdns", "cryptography-provider-jdk-jvm",
    "cryptography-provider-cryptokit-iosarm64", "cryptography-provider-cryptokit-iossimulatorarm64",
    "cryptography-provider-cryptokit-iosx64",
}
CONTAMINATION = ("/Users/", "/home/", "p2p-sample", "dokka-base", "gradle-api")
IDENTITY_FIELDS = ("type", "group", "name", "version", "purl", "cpe")


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


def component(value: Any, kind: str) -> tuple[str, tuple]:
    if not isinstance(value, dict):
        invalid(kind, "invalid component")
    # The configured aggregate is flat. Do not silently ignore nested nodes.
    if "components" in value and array(value["components"], kind, "nested components"):
        invalid(kind, "nested components are not supported by the release graph")
    ref = text(value.get("bom-ref"), kind, "component bom-ref")
    identity = tuple(text(value.get(key), kind, key, key not in ("type", "name"))
                     for key in IDENTITY_FIELDS)
    hashes = {}
    for digest in array(value.get("hashes", []), kind, "hashes"):
        if not isinstance(digest, dict):
            invalid(kind, "invalid component hash")
        algorithm = text(digest.get("alg"), kind, "hash algorithm")
        content = text(digest.get("content"), kind, "hash content")
        if algorithm in hashes or not re.fullmatch(r"[0-9a-fA-F]+", content):
            invalid(kind, "duplicate or invalid component hash")
        hashes[algorithm] = content.lower()
    return ref, (identity, tuple(sorted(hashes.items())))


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


def leaf(parent: ET.Element, name: str) -> str | None:
    node = child(parent, name, optional=True)
    if node is None:
        return None
    if elements(node) or node.attrib:
        invalid("XML", f"invalid {name} leaf")
    return node.text or ""


def xml_component(node: ET.Element) -> dict:
    value = {"type": node.get("type"), "bom-ref": node.get("bom-ref")}
    value.update({key: leaf(node, key) for key in IDENTITY_FIELDS if key != "type"})
    nested = child(node, "components", optional=True)
    if nested is not None and elements(nested):
        invalid("XML", "nested components are not supported by the release graph")
    hashes = child(node, "hashes", optional=True)
    if hashes is not None:
        value["hashes"] = []
        for digest in elements(hashes):
            if digest.tag != f"{{{NAMESPACE}}}hash" or elements(digest) or set(digest.attrib) != {"alg"}:
                invalid("XML", "invalid component hash")
            value["hashes"].append({"alg": digest.get("alg"), "content": digest.text})
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


def validate(json_path: str, xml_path: str, group: str, version: str) -> int:
    json_raw = read_bounded(json_path, "JSON")
    xml_raw = read_bounded(xml_path, "XML")
    try:
        document = json.loads(json_raw.decode("utf-8-sig"), object_pairs_hook=no_duplicate_keys,
                              parse_constant=no_nonfinite)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as error:
        invalid("JSON", f"parser error ({type(error).__name__})")
    if not isinstance(document, dict):
        invalid("JSON", "root is not an object")
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
        invalid("XML", "component references, coordinates or hashes differ from JSON")
    if graph(xml_graph(root), refs, "XML") != dependencies:
        invalid("XML", "dependency graph differs from JSON")
    check_contamination(document, root, (json_raw, xml_raw))
    return len(components)


def main(arguments: list[str]) -> int:
    if len(arguments) != 4:
        print("Usage: validate-sbom.py <json> <xml> <group> <version>", file=sys.stderr)
        return 2
    try:
        count = validate(*arguments)
    except (SbomError, OSError) as error:
        print(f"FATAL: {error}", file=sys.stderr)
        return 1
    print(f"RESULT: PASS — CycloneDX 1.6 JSON/XML SBOM contains {count} release components, "
          "a connected four-module root, and no build/sample contamination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
