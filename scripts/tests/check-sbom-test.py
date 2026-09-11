#!/usr/bin/python3
"""Real-parser, file-boundary and CLI regressions for paired release SBOMs."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sbom_validator", ROOT / "scripts/validate-sbom.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
NS = "{http://cyclonedx.org/schema/bom/1.6}"
GROUP = "example.release"
VERSION = "1.2.3"


def vendor_fixture(root: Path) -> tuple[dict, dict]:
    """Controlled source/producer bytes for validator tests, not native build evidence."""
    vendor = root / VALIDATOR.VENDOR_RELATIVE
    sources = []
    for index in range(59):
        filename = f"Fixture{index:02}.java"
        original = f"package javax.jmdns; class Fixture{index:02} {{}}\n".encode()
        modified = original.replace(b"javax.jmdns", VALIDATOR.PRIVATE_NAMESPACE.encode())
        relative = f"src/main/java/{VALIDATOR.PRIVATE_PATH}/{filename}"
        path = vendor / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(modified)
        sources.append({
            "path": relative, "upstreamPath": f"src/main/java/javax/jmdns/{filename}",
            "upstreamSha256": hashlib.sha256(original).hexdigest(),
            "relocatedSha256": hashlib.sha256(modified).hexdigest(),
            "sha256": hashlib.sha256(modified).hexdigest(),
        })
    resources = []
    for relative, entry in sorted(VALIDATOR.RESOURCE_ENTRIES.items()):
        path = vendor / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("controlled fixture resource\n")
        resources.append({"path": relative, "entry": entry, "sha256": VALIDATOR.file_sha256(path)})
    patch = vendor / VALIDATOR.PATCH_PATH
    patch.parent.mkdir(parents=True, exist_ok=True)
    patch.write_text("controlled fixture lifecycle patch\n")
    followups = []
    for relative in VALIDATOR.FOLLOWUP_PATCH_PATHS:
        followup = vendor / relative
        followup.write_text(f"controlled fixture followup patch: {relative}\n")
        followups.append({"path": relative, "sha256": VALIDATOR.file_sha256(followup)})
    manifest = {
        "schema": 2, "component": copy.deepcopy(VALIDATOR.EMBEDDED_IDENTITY),
        "upstream": copy.deepcopy(VALIDATOR.UPSTREAM),
        "normalization": copy.deepcopy(VALIDATOR.NORMALIZATION),
        "relocation": {"from": "javax.jmdns", "to": VALIDATOR.PRIVATE_NAMESPACE},
        "sources": sources, "resources": resources,
        "lifecyclePatch": {"path": VALIDATOR.PATCH_PATH, "sha256": VALIDATOR.file_sha256(patch)},
        "followupPatches": followups,
        "manifestEntry": f"{VALIDATOR.NOTICE_PATH}/PROVENANCE.json",
    }
    manifest_path = vendor / "PROVENANCE.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    manifest_hash = VALIDATOR.file_sha256(manifest_path)
    producer = root / VALIDATOR.PRODUCER_RELATIVE
    producer.parent.mkdir(parents=True, exist_ok=True)
    producer.write_bytes(b"controlled private producer bytes, not a compiled JAR\n")
    (vendor / "upstream.cdx.json").write_text(json.dumps(VALIDATOR.upstream_inventory(manifest_hash)) + "\n")
    return manifest, VALIDATOR.embedded_component(manifest, manifest_hash, VALIDATOR.file_sha256(producer))


def fixture(embedded: dict) -> dict:
    components = []
    for name in sorted(VALIDATOR.REQUIRED):
        if name == "jmdns":
            components.append(copy.deepcopy(embedded))
            continue
        group = GROUP if name in VALIDATOR.MODULES else "example.dependency"
        version = VERSION
        if name == "slf4j-api":
            group, version = "org.slf4j", "2.0.7"
        components.append({
            "bom-ref": name, "type": "library", "group": group, "name": name, "version": version,
            "purl": f"pkg:maven/{group}/{name}@{version}",
            "hashes": [{"alg": "SHA-256", "content": "a" * 64}],
        })
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
        "metadata": {"component": {"bom-ref": "root", "type": "library", "group": GROUP,
                                   "name": "p2pkit", "version": VERSION}},
        "components": components,
        "dependencies": [
            {"ref": "root", "dependsOn": sorted(VALIDATOR.MODULES)},
            {"ref": "p2p-core", "dependsOn": sorted(VALIDATOR.REQUIRED - VALIDATOR.MODULES - {"jmdns", "slf4j-api"})},
            {"ref": "p2p-transport-lan", "dependsOn": [embedded["bom-ref"], "p2p-core"]},
            {"ref": embedded["bom-ref"], "dependsOn": ["slf4j-api"]},
        ],
    }


def xml_fixture(document: dict) -> ET.Element:
    def component(parent, value):
        node = ET.SubElement(parent, NS + "component", {"type": value["type"], "bom-ref": value["bom-ref"]})
        for name in VALIDATOR.IDENTITY_FIELDS:
            if name != "type" and value.get(name) is not None:
                ET.SubElement(node, NS + name).text = value[name]
        if value.get("hashes"):
            hashes = ET.SubElement(node, NS + "hashes")
            for digest in value["hashes"]:
                ET.SubElement(hashes, NS + "hash", {"alg": digest["alg"]}).text = digest["content"]
        if "modified" in value:
            ET.SubElement(node, NS + "modified").text = str(value["modified"]).lower()
        if "pedigree" in value:
            pedigree = ET.SubElement(node, NS + "pedigree")
            ancestors = ET.SubElement(pedigree, NS + "ancestors")
            for ancestor in value["pedigree"]["ancestors"]:
                component(ancestors, ancestor)
            patches = ET.SubElement(pedigree, NS + "patches")
            for patch in value["pedigree"]["patches"]:
                item = ET.SubElement(patches, NS + "patch", {"type": patch["type"]})
                ET.SubElement(ET.SubElement(item, NS + "diff"), NS + "url").text = patch["diff"]["url"]
        if "externalReferences" in value:
            references = ET.SubElement(node, NS + "externalReferences")
            for reference in value["externalReferences"]:
                entry = ET.SubElement(references, NS + "reference", {"type": reference["type"]})
                ET.SubElement(entry, NS + "url").text = reference["url"]
                if reference.get("hashes"):
                    hashes = ET.SubElement(entry, NS + "hashes")
                    for digest in reference["hashes"]:
                        ET.SubElement(hashes, NS + "hash", {"alg": digest["alg"]}).text = digest["content"]
        if "properties" in value:
            properties = ET.SubElement(node, NS + "properties")
            for entry in value["properties"]:
                ET.SubElement(properties, NS + "property", {"name": entry["name"]}).text = entry["value"]
        return node

    root = ET.Element(NS + "bom", {"version": str(document["version"])})
    component(ET.SubElement(root, NS + "metadata"), document["metadata"]["component"])
    container = ET.SubElement(root, NS + "components")
    for value in document["components"]:
        component(container, value)
    dependencies = ET.SubElement(root, NS + "dependencies")
    for entry in document["dependencies"]:
        node = ET.SubElement(dependencies, NS + "dependency", {"ref": entry["ref"]})
        for ref in entry.get("dependsOn", []):
            ET.SubElement(node, NS + "dependency", {"ref": ref})
    return root


def root_component(root):
    return root.find(NS + "metadata/" + NS + "component")


def component_node(root):
    return root.find(NS + "components/" + NS + "component")


def dependencies(root):
    return root.find(NS + "dependencies")


XML_MUTATIONS = {
    "missing metadata": lambda r: r.remove(r.find(NS + "metadata")),
    "missing components": lambda r: r.remove(r.find(NS + "components")),
    "wrong namespace": lambda r: setattr(r, "tag", "{urn:wrong}bom"),
    "wrong document revision": lambda r: r.set("version", "2"),
    "wrong serial number": lambda r: r.set("serialNumber", "different"),
    "duplicate metadata": lambda r: r.append(copy.deepcopy(r.find(NS + "metadata"))),
    "duplicate components container": lambda r: r.append(copy.deepcopy(r.find(NS + "components"))),
    "wrong root bom-ref": lambda r: root_component(r).set("bom-ref", "wrong"),
    "wrong root type": lambda r: root_component(r).set("type", "application"),
    "missing component": lambda r: r.find(NS + "components").remove(component_node(r)),
    "duplicate component": lambda r: r.find(NS + "components").append(copy.deepcopy(component_node(r))),
    "component collides with root": lambda r: component_node(r).set("bom-ref", "root"),
    "wrong component namespace": lambda r: setattr(component_node(r), "tag", "{urn:wrong}component"),
    "missing component name": lambda r: component_node(r).remove(component_node(r).find(NS + "name")),
    "duplicate component name": lambda r: component_node(r).append(copy.deepcopy(component_node(r).find(NS + "name"))),
    "wrong component version": lambda r: setattr(component_node(r).find(NS + "version"), "text", "9.9.9"),
    "wrong component purl": lambda r: setattr(component_node(r).find(NS + "purl"), "text", "pkg:generic/wrong"),
    "wrong component hash": lambda r: setattr(component_node(r).find(NS + "hashes/" + NS + "hash"), "text", "b" * 64),
    "duplicate hash": lambda r: component_node(r).find(NS + "hashes").append(
        copy.deepcopy(component_node(r).find(NS + "hashes/" + NS + "hash"))),
    "missing dependencies": lambda r: r.remove(dependencies(r)),
    "duplicate dependency node": lambda r: dependencies(r).append(copy.deepcopy(dependencies(r)[0])),
    "duplicate dependency target": lambda r: dependencies(r)[0].append(copy.deepcopy(dependencies(r)[0][0])),
    "unknown dependency node": lambda r: dependencies(r)[0].set("ref", "unknown"),
    "unknown dependency target": lambda r: dependencies(r)[0][0].set("ref", "unknown"),
    "missing transitive edge": lambda r: dependencies(r)[1].remove(dependencies(r)[1][0]),
    "changed known edge": lambda r: dependencies(r)[1][0].set("ref", "p2p-transport-lan"),
}
for field in ("group", "name", "version"):
    XML_MUTATIONS["wrong root " + field] = (
        lambda r, field=field: setattr(root_component(r).find(NS + field), "text", "wrong"))


class SbomTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="p2pkit-sbom-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.json_path = self.directory / "bom.json"
        self.xml_path = self.directory / "bom.xml"
        self.vendor_directory = self.directory / VALIDATOR.VENDOR_RELATIVE
        self.producer_path = self.directory / VALIDATOR.PRODUCER_RELATIVE
        self.manifest, self.embedded = vendor_fixture(self.directory)
        self.document = fixture(self.embedded)
        self.xml = xml_fixture(self.document)

    def write(self):
        self.json_path.write_text(json.dumps(self.document), encoding="utf-8")
        ET.ElementTree(self.xml).write(self.xml_path, encoding="utf-8", xml_declaration=True)

    def validate(self):
        return VALIDATOR.validate(str(self.json_path), str(self.xml_path), GROUP, VERSION,
                                  self.vendor_directory, self.producer_path)

    def test_valid_pair(self):
        self.write()
        self.assertEqual(self.validate(), 11)

    def test_embedded_claims_must_match_vendor_truth_even_when_both_formats_agree(self):
        mutations = {
            "false upstream identity": lambda c: c.update(purl=VALIDATOR.UPSTREAM["purl"]),
            "upstream hash on modified bytes": lambda c: c["hashes"][0].update(
                content=VALIDATOR.UPSTREAM["binarySha256"]),
            "missing modification": lambda c: c.pop("modified"),
            "wrong ancestor": lambda c: c["pedigree"]["ancestors"][0].update(version="3.6.2"),
            "wrong source/patch provenance": lambda c: next(
                p for p in c["properties"] if p["name"].endswith("source-manifest-sha256")).update(value="b" * 64),
            "duplicate provenance": lambda c: c["properties"].append(copy.deepcopy(c["properties"][0])),
            "wrong patch": lambda c: c["pedigree"]["patches"][0]["diff"].update(url="different.patch"),
            "explicit null patch text": lambda c: c["pedigree"]["patches"][0]["diff"].update(text=None),
            "omitted followup patch": lambda c: c["pedigree"]["patches"].pop(),
            "duplicate patch": lambda c: c["pedigree"]["patches"].__setitem__(
                1, copy.deepcopy(c["pedigree"]["patches"][0])),
            "reordered patches": lambda c: c["pedigree"]["patches"].reverse(),
            "wrong followup hash": lambda c: next(
                p for p in c["properties"] if "followup-patch-sha256:" in p["name"]).update(value="b" * 64),
            "wrong followup URL": lambda c: c["pedigree"]["patches"][-1]["diff"].update(url="different.patch"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                self.document = fixture(self.embedded)
                mutate(next(c for c in self.document["components"] if c["name"] == "jmdns"))
                self.xml = xml_fixture(self.document)
                self.write()
                with self.assertRaises(VALIDATOR.SbomError):
                    self.validate()

    def test_embedded_xml_provenance_is_not_ignored(self):
        patch_path = NS + "pedigree/" + NS + "patches"

        def reverse_patches(component):
            patches = component.find(patch_path)
            patches[:] = list(reversed(patches))

        mutations = {
            "missing properties": lambda c: c.remove(c.find(NS + "properties")),
            "duplicate property": lambda c: c.find(NS + "properties").append(
                copy.deepcopy(c.find(NS + "properties")[0])),
            "changed property": lambda c: setattr(c.find(NS + "properties")[0], "text", "wrong"),
            "wrong ancestor hash": lambda c: setattr(
                c.find(NS + "pedigree/" + NS + "ancestors/" + NS + "component/" + NS + "hashes/" + NS + "hash"),
                "text", "b" * 64),
            "wrong patch URL": lambda c: setattr(
                c.find(NS + "pedigree/" + NS + "patches/" + NS + "patch/" + NS + "diff/" + NS + "url"),
                "text", "different.patch"),
            "omitted followup patch": lambda c: c.find(patch_path).remove(c.find(patch_path)[-1]),
            "duplicate patch": lambda c: c.find(patch_path).__setitem__(
                1, copy.deepcopy(c.find(patch_path)[0])),
            "reordered patches": reverse_patches,
            "duplicate pedigree": lambda c: c.append(copy.deepcopy(c.find(NS + "pedigree"))),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                self.xml = xml_fixture(self.document)
                embedded = next(c for c in self.xml.find(NS + "components")
                                if c.find(NS + "name").text == "jmdns")
                mutate(embedded)
                self.write()
                with self.assertRaisesRegex(VALIDATOR.SbomError, "XML SBOM content gate failed"):
                    self.validate()

    def test_embedded_runtime_edges_cannot_be_missing_in_both_formats(self):
        for ref in ("p2p-transport-lan", self.embedded["bom-ref"]):
            with self.subTest(ref=ref):
                self.document = fixture(self.embedded)
                next(edge for edge in self.document["dependencies"] if edge["ref"] == ref)["dependsOn"] = []
                self.xml = xml_fixture(self.document)
                self.write()
                with self.assertRaisesRegex(VALIDATOR.SbomError, "LAN -> embedded JmDNS"):
                    self.validate()

    def test_vendor_metadata_and_actual_inputs_are_bound(self):
        mutations = {
            "unsafe source": lambda m: m["sources"][0].update(path="../outside.java"),
            "non-normalized source": lambda m: m["sources"][0].update(path="src/./main/java/X.java"),
            "duplicate source": lambda m: m["sources"].append(copy.deepcopy(m["sources"][0])),
            "mixed helper provenance": lambda m: m["sources"][0].update(upstreamPath=None),
            "false source hash": lambda m: m["sources"][0].update(sha256="a" * 64),
            "wrong resource entry": lambda m: m["resources"][0].update(entry="different/LICENSE"),
            "false patch hash": lambda m: m["lifecyclePatch"].update(sha256="a" * 64),
            "missing followup roster": lambda m: m.pop("followupPatches"),
            "omitted followup": lambda m: m["followupPatches"].clear(),
            "duplicate followup": lambda m: m["followupPatches"].append(copy.deepcopy(m["followupPatches"][0])),
            "reordered followups": lambda m: m["followupPatches"].reverse(),
            "unsafe followup path": lambda m: m["followupPatches"][0].update(path="../outside.patch"),
            "false followup hash": lambda m: m["followupPatches"][0].update(sha256="a" * 64),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                manifest = copy.deepcopy(self.manifest)
                mutate(manifest)
                (self.vendor_directory / "PROVENANCE.json").write_text(json.dumps(manifest))
                with self.assertRaises(VALIDATOR.SbomError):
                    VALIDATOR.load_vendor_manifest(self.vendor_directory)
        self.manifest, self.embedded = vendor_fixture(self.directory)
        self.write()
        for path in (self.vendor_directory / self.manifest["sources"][0]["path"],
                     self.vendor_directory / VALIDATOR.PATCH_PATH,
                     *(self.vendor_directory / path for path in VALIDATOR.FOLLOWUP_PATCH_PATHS),
                     self.producer_path):
            with self.subTest(changed_input=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b"changed\n")
                with self.assertRaises(VALIDATOR.SbomError):
                    self.validate()
                path.write_bytes(original)
        followup = self.vendor_directory / VALIDATOR.FOLLOWUP_PATCH_PATHS[0]
        original = followup.read_bytes()
        followup.unlink()
        with self.assertRaisesRegex(VALIDATOR.SbomError, "missing file"):
            VALIDATOR.load_vendor_manifest(self.vendor_directory)
        followup.write_bytes(original)
        undeclared = self.vendor_directory / "patches/unlisted.patch"
        undeclared.write_text("not part of the declared patch sequence\n")
        with self.assertRaisesRegex(VALIDATOR.SbomError, "patch roster"):
            VALIDATOR.load_vendor_manifest(self.vendor_directory)

    def test_upstream_inventory_is_not_a_modified_runtime_identity_or_stale_copy(self):
        path = self.vendor_directory / "upstream.cdx.json"
        VALIDATOR.validate_upstream_inventory(path, self.vendor_directory)
        original = json.loads(path.read_text())
        for mode in ("modified identity", "stale manifest"):
            with self.subTest(mode=mode):
                document = copy.deepcopy(original)
                if mode == "modified identity":
                    document["components"][0]["purl"] = self.embedded["purl"]
                else:
                    document["metadata"]["properties"][1]["value"] = "b" * 64
                path.write_text(json.dumps(document))
                with self.assertRaisesRegex(VALIDATOR.SbomError, "wrong upstream identity or stale"):
                    VALIDATOR.validate_upstream_inventory(path, self.vendor_directory)

    def test_manifest_cannot_claim_normalization_for_non_normalized_bytes(self):
        source = self.manifest["sources"][0]
        path = self.vendor_directory / source["path"]
        path.write_bytes(path.read_bytes().replace(b"\n", b" \r\n"))
        source["sha256"] = VALIDATOR.file_sha256(path)
        (self.vendor_directory / "PROVENANCE.json").write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(VALIDATOR.SbomError, "normalization differs"):
            VALIDATOR.load_vendor_manifest(self.vendor_directory)

    def test_xml_regressions(self):
        for name, mutate in XML_MUTATIONS.items():
            with self.subTest(name=name):
                self.xml = xml_fixture(self.document)
                mutate(self.xml)
                self.write()
                with self.assertRaisesRegex(VALIDATOR.SbomError, "XML SBOM content gate failed"):
                    self.validate()

    def test_json_regressions_are_preserved(self):
        mutations = {
            "format": lambda d: d.update(bomFormat="wrong"),
            "spec": lambda d: d.update(specVersion="1.5"),
            "boolean revision": lambda d: d.update(version=True),
            "missing provider": lambda d: d["components"].pop(0),
            "wrong release": lambda d: d["metadata"]["component"].update(version="wrong"),
            "duplicate component": lambda d: d["components"].append(copy.deepcopy(d["components"][0])),
            "duplicate dependency": lambda d: d["dependencies"].append(copy.deepcopy(d["dependencies"][0])),
            "duplicate edge": lambda d: d["dependencies"][0]["dependsOn"].append("p2p-core"),
            "unknown edge": lambda d: d["dependencies"][0]["dependsOn"].append("unknown"),
            "disconnected root": lambda d: d["dependencies"][0].update(dependsOn=[]),
            "nested component": lambda d: d["components"][0].update(components=[d["components"][1]]),
            "malformed nested list": lambda d: d["components"][0].update(components={}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                self.document = fixture(self.embedded)
                mutate(self.document)
                self.write()
                with self.assertRaisesRegex(VALIDATOR.SbomError, "JSON SBOM content gate failed"):
                    self.validate()

    def test_reordering_prefixes_and_absent_leaf_entries(self):
        self.document["dependencies"].append({"ref": "slf4j-api", "dependsOn": []})
        self.xml = xml_fixture(self.document)
        for container in (self.xml.find(NS + "components"), dependencies(self.xml)):
            container[:] = list(reversed(container))
        dependencies(self.xml).remove(next(n for n in dependencies(self.xml) if n.get("ref") == "slf4j-api"))
        for node in dependencies(self.xml):
            node[:] = list(reversed(node))
        self.xml.set("version", "+01")
        self.write()  # ElementTree uses a namespace prefix, not the generator's default namespace.
        self.assertEqual(self.validate(), 11)

    def test_equivalent_hash_case(self):
        component_node(self.xml).find(NS + "hashes/" + NS + "hash").text = "A" * 64
        self.write()
        self.assertEqual(self.validate(), 11)

    def test_equivalent_empty_nested_component_containers(self):
        self.document["metadata"]["component"]["components"] = []
        self.document["components"][0]["components"] = []
        ET.SubElement(root_component(self.xml), NS + "components")
        ET.SubElement(component_node(self.xml), NS + "components")
        self.write()
        self.assertEqual(self.validate(), 11)

        ET.SubElement(component_node(self.xml).find(NS + "components"), NS + "component")
        self.write()
        with self.assertRaisesRegex(VALIDATOR.SbomError, "nested components are not supported"):
            self.validate()

    def check_xml_simple_content(self, equivalent):
        targets = {
            "release version": lambda r: root_component(r).find(NS + "version"),
            "component version": lambda r: component_node(r).find(NS + "version"),
            "purl": lambda r: component_node(r).find(NS + "purl"),
            "hash": lambda r: component_node(r).find(NS + "hashes/" + NS + "hash"),
        }
        markers = {
            "comment": lambda: ET.Comment("not part of the value"),
            "processing instruction": lambda: ET.ProcessingInstruction("split", "not-part-of-the-value"),
        }
        for name, target in targets.items():
            for kind, marker in markers.items():
                with self.subTest(target=name, marker=kind, equivalent=equivalent):
                    self.xml = xml_fixture(self.document)
                    node = target(self.xml)
                    addition = marker()
                    if equivalent:
                        offset = len(node.text) // 2
                        addition.tail = node.text[offset:]
                        node.text = node.text[:offset]
                    else:
                        addition.tail = "b"  # Also remains syntactically valid hexadecimal in a hash.
                    node.append(addition)
                    self.write()
                    if equivalent:
                        self.assertEqual(self.validate(), 11)
                    else:
                        with self.assertRaisesRegex(VALIDATOR.SbomError, "XML SBOM content gate failed"):
                            self.validate()

    def test_equivalent_comment_and_processing_instruction_splits(self):
        self.check_xml_simple_content(equivalent=True)

    def test_comment_and_processing_instruction_tails_cannot_hide_differences(self):
        self.check_xml_simple_content(equivalent=False)

    def test_multiple_boundary_splits_preserve_text_but_nested_elements_fail(self):
        for target in (lambda r: root_component(r).find(NS + "version"),
                       lambda r: component_node(r).find(NS + "hashes/" + NS + "hash")):
            self.xml = xml_fixture(self.document)
            node = target(self.xml)
            value = node.text
            node.text = None
            first = ET.Comment("before")
            first.tail = value[:1]
            middle = ET.ProcessingInstruction("split", "ignored")
            middle.tail = value[1:]
            node.extend([first, middle, ET.Comment("after")])
            self.write()
            self.assertEqual(self.validate(), 11)

            ET.SubElement(node, NS + "unexpected")
            self.write()
            with self.assertRaisesRegex(VALIDATOR.SbomError, "XML SBOM content gate failed"):
                self.validate()

    def test_dtd_declarations_rejected_in_utf8_and_utf16(self):
        self.write()
        for declaration in ('<!DOCTYPE bom [<!ENTITY x "expanded">]>',
                            '<!DOCTYPE bom SYSTEM "file:///nonexistent-p2pkit-test.dtd">'):
            for encoding in ("utf-8", "utf-16"):
                with self.subTest(declaration=declaration, encoding=encoding):
                    text = f'<?xml version="1.0" encoding="{encoding}"?>' + declaration + ET.tostring(self.xml, encoding="unicode")
                    self.xml_path.write_bytes(text.encode(encoding))
                    with self.assertRaisesRegex(VALIDATOR.SbomError, "DTD/entity declarations are forbidden"):
                        self.validate()

    def test_json_duplicates_nonfinite_and_invalid_utf8_rejected(self):
        self.write()
        for raw in (b'{"components":[],"components":[]}', b'{"number":NaN}', b'{"text":"\xff"}'):
            with self.subTest(raw=raw):
                self.json_path.write_bytes(raw)
                with self.assertRaisesRegex(VALIDATOR.SbomError, "JSON SBOM content gate failed"):
                    self.validate()

    def test_contamination_in_json_and_xml_including_escapes(self):
        for token in VALIDATOR.CONTAMINATION:
            for kind in ("json", "escaped-json", "xml"):
                with self.subTest(token=token, kind=kind):
                    self.document = fixture(self.embedded)
                    self.xml = xml_fixture(self.document)
                    if kind != "xml":
                        self.document["metadata"]["note"] = token
                    else:
                        ET.SubElement(self.xml.find(NS + "metadata"), NS + "note").text = token
                    self.write()
                    if kind == "escaped-json":
                        raw = self.json_path.read_text().replace(token, "".join(f"\\u{ord(c):04x}" for c in token))
                        self.json_path.write_text(raw)
                    with self.assertRaisesRegex(VALIDATOR.SbomError, "workstation path or includes sample/build"):
                        self.validate()

    def test_empty_exact_and_oversized_real_files(self):
        self.assertEqual(VALIDATOR.MAX_BYTES, 16 * 1024 * 1024)
        for size in (0, VALIDATOR.MAX_BYTES, VALIDATOR.MAX_BYTES + 1):
            with self.subTest(size=size):
                with self.json_path.open("wb") as stream:
                    stream.truncate(size)
                if size == VALIDATOR.MAX_BYTES:
                    self.assertEqual(len(VALIDATOR.read_bounded(str(self.json_path), "JSON")), size)
                else:
                    with self.assertRaisesRegex(VALIDATOR.SbomError, "input must contain"):
                        VALIDATOR.read_bounded(str(self.json_path), "JSON")

    def test_each_oversized_input_rejected_before_parsing(self):
        for path in (self.json_path, self.xml_path):
            with self.subTest(path=path.name):
                self.write()
                with path.open("wb") as stream:
                    stream.truncate(VALIDATOR.MAX_BYTES + 1)
                with mock.patch.object(VALIDATOR.json, "loads") as parser, \
                        mock.patch.object(VALIDATOR.ET, "fromstring") as xml_parser:
                    with self.assertRaisesRegex(VALIDATOR.SbomError, "input must contain"):
                        self.validate()
                parser.assert_not_called()
                xml_parser.assert_not_called()

    def test_read_is_bounded_when_file_grows_after_open(self):
        self.json_path.write_bytes(b"x")
        stream = self.json_path.open("rb")
        self.addCleanup(stream.close)
        requests = []

        class Reader:
            def __enter__(reader):
                return reader

            def __exit__(reader, *errors):
                stream.close()

            def read(reader, size=-1):
                requests.append(size)
                self.assertEqual(size, VALIDATOR.MAX_BYTES + 1)
                # Use built-in open to avoid the Path.open observation patch.
                with open(self.json_path, "r+b") as growing:
                    growing.truncate(VALIDATOR.MAX_BYTES + 2)
                return stream.read(size)

        with mock.patch.object(Path, "open", return_value=Reader()):
            with self.assertRaisesRegex(VALIDATOR.SbomError, "input must contain"):
                VALIDATOR.read_bounded(str(self.json_path), "JSON")
        self.assertEqual(requests, [VALIDATOR.MAX_BYTES + 1])
        self.assertTrue(stream.closed)

    def test_cli_modes_and_failure_propagation(self):
        scripts = self.directory / "scripts"
        scripts.mkdir()
        for name in ("check-sbom.sh", "validate-sbom.py"):
            shutil.copy2(ROOT / "scripts" / name, scripts / name)
        (self.directory / "gradle.properties").write_text(f"GROUP={GROUP}\nVERSION_NAME={VERSION}\n")
        wrapper = self.directory / "gradlew"
        wrapper.write_text(
            '#!/usr/bin/env bash\nset -euo pipefail\n'
            'printf "%s\\n" "$*" >> gradle-calls\n'
            'mkdir -p build/reports/cyclonedx\n'
            'cp bom.json build/reports/cyclonedx/bom.json\n'
            'cp bom.xml build/reports/cyclonedx/bom.xml\n'
        )
        wrapper.chmod(0o755)
        self.write()
        for arguments in ([], [str(self.json_path)], [str(self.json_path), str(self.xml_path)]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(["bash", str(scripts / "check-sbom.sh"), *arguments],
                                        cwd=self.directory, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("contains 11 release components", result.stdout)
        self.assertEqual((self.directory / "gradle-calls").read_text(), "cyclonedxBom --console=plain\n")
        self.xml.remove(self.xml.find(NS + "components"))
        self.write()
        result = subprocess.run(["bash", str(scripts / "check-sbom.sh"), str(self.json_path), str(self.xml_path)],
                                cwd=self.directory, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FATAL: XML SBOM content gate failed", result.stderr)
        self.assertNotIn("RESULT: PASS", result.stdout)


if __name__ == "__main__":
    print(f"SBOM XML mutation subcases: {len(XML_MUTATIONS)}", flush=True)
    unittest.main(verbosity=2)
