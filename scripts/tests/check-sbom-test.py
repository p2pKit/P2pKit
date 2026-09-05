#!/usr/bin/python3
"""Real-parser, file-boundary and CLI regressions for paired release SBOMs."""

from __future__ import annotations

import copy
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


def fixture() -> dict:
    components = []
    for name in sorted(VALIDATOR.REQUIRED):
        group = GROUP if name in VALIDATOR.MODULES else "example.dependency"
        components.append({
            "bom-ref": name, "type": "library", "group": group, "name": name, "version": VERSION,
            "purl": f"pkg:maven/{group}/{name}@{VERSION}",
            "hashes": [{"alg": "SHA-256", "content": "a" * 64}],
        })
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
        "metadata": {"component": {"bom-ref": "root", "type": "library", "group": GROUP,
                                   "name": "p2pkit", "version": VERSION}},
        "components": components,
        "dependencies": [
            {"ref": "root", "dependsOn": sorted(VALIDATOR.MODULES)},
            {"ref": "p2p-core", "dependsOn": sorted(VALIDATOR.REQUIRED - VALIDATOR.MODULES)},
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
        self.document = fixture()
        self.xml = xml_fixture(self.document)

    def write(self):
        self.json_path.write_text(json.dumps(self.document), encoding="utf-8")
        ET.ElementTree(self.xml).write(self.xml_path, encoding="utf-8", xml_declaration=True)

    def validate(self):
        return VALIDATOR.validate(str(self.json_path), str(self.xml_path), GROUP, VERSION)

    def test_valid_pair(self):
        self.write()
        self.assertEqual(self.validate(), 10)

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
                self.document = fixture()
                mutate(self.document)
                self.write()
                with self.assertRaisesRegex(VALIDATOR.SbomError, "JSON SBOM content gate failed"):
                    self.validate()

    def test_reordering_prefixes_and_absent_leaf_entries(self):
        self.document["dependencies"].append({"ref": "jmdns", "dependsOn": []})
        self.xml = xml_fixture(self.document)
        for container in (self.xml.find(NS + "components"), dependencies(self.xml)):
            container[:] = list(reversed(container))
        dependencies(self.xml).remove(next(n for n in dependencies(self.xml) if n.get("ref") == "jmdns"))
        for node in dependencies(self.xml):
            node[:] = list(reversed(node))
        self.xml.set("version", "+01")
        self.write()  # ElementTree uses a namespace prefix, not the generator's default namespace.
        self.assertEqual(self.validate(), 10)

    def test_equivalent_hash_case(self):
        component_node(self.xml).find(NS + "hashes/" + NS + "hash").text = "A" * 64
        self.write()
        self.assertEqual(self.validate(), 10)

    def test_equivalent_empty_nested_component_containers(self):
        self.document["metadata"]["component"]["components"] = []
        self.document["components"][0]["components"] = []
        ET.SubElement(root_component(self.xml), NS + "components")
        ET.SubElement(component_node(self.xml), NS + "components")
        self.write()
        self.assertEqual(self.validate(), 10)

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
                        self.assertEqual(self.validate(), 10)
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
            self.assertEqual(self.validate(), 10)

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
                    self.document = fixture()
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
                self.assertIn("contains 10 release components", result.stdout)
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
