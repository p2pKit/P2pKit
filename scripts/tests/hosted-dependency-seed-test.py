#!/usr/bin/env python3
"""Offline allowlist grammar tests, not native/cache/resolver qualification."""

from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hosted_dependency_seed", ROOT / "scripts/hosted_dependency_seed.py")
SEED = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SEED
SPEC.loader.exec_module(SEED)

SHA = "0123456789abcdef" * 4
CONFIGURATION = "<configuration><verify-metadata>true</verify-metadata>" \
    "<verify-signatures>false</verify-signatures></configuration>"
HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n' \
    '<verification-metadata xmlns="' + SEED.NAMESPACE + '" ' \
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="' + SEED.SCHEMA_LOCATION + '">'


def artifact(name="sample.jar", value=SHA, origin=None):
    annotation = '' if origin is None else ' origin="' + origin + '"'
    return '<artifact name="' + name + '"><sha256 value="' + value + '"' + annotation + '/></artifact>'


def component(group="org.sample", module="sample", version="1.0", artifacts=None):
    return '<component group="' + group + '" name="' + module + '" version="' + version + '">' + \
        (artifact() if artifacts is None else artifacts) + '</component>'


def document(components=None, configuration=CONFIGURATION):
    return (HEADER + configuration + '<components>' + (component() if components is None else components) +
            '</components></verification-metadata>').encode("utf-8")


class AllowlistTests(unittest.TestCase):
    def reject(self, raw, code=None):
        with self.assertRaises(SEED.AllowlistError) as failure:
            SEED.parse_allowlist(raw)
        if code is not None:
            self.assertEqual(str(failure.exception), code)
        self.assertRegex(str(failure.exception), r"^[A-Z][A-Z0-9_]*$")

    def test_current_metadata_exact_complete_inventory(self):
        raw = (ROOT / "gradle/verification-metadata.xml").read_bytes()
        result = SEED.parse_allowlist(raw)
        # Independent XML inventory, not copied committed output or a lock subset.
        ns = "{" + SEED.NAMESPACE + "}"
        tree = ElementTree.fromstring(raw)
        components = tree.find(ns + "components")
        expected = tuple(sorted(
            SEED.Artifact(item.attrib["group"], item.attrib["name"], item.attrib["version"],
                          child.attrib["name"], child.find(ns + "sha256").attrib["value"])
            for item in components for child in item
        ))
        self.assertEqual(result.artifacts, expected)
        self.assertEqual((result.component_count, len(result.artifacts)), (1420, 2991))
        self.assertEqual(result.source_sha256, hashlib.sha256(raw).hexdigest())
        names = {row.name for row in result.artifacts}
        self.assertIn("FastInfoset-1.2.16.jar", names)
        self.assertEqual(max(map(len, names)), 104)
        self.assertTrue(any("ios" in name.lower() and any(c.isupper() for c in name) for name in names))
        self.assertTrue(any(row.group == "org.jetbrains.kotlin" for row in result.artifacts))

    def test_immutable_rows_and_result(self):
        result = SEED.parse_allowlist(document())
        self.assertIsInstance(result.artifacts, tuple)
        with self.assertRaises(FrozenInstanceError):
            result.source_sha256 = "changed"
        with self.assertRaises(AttributeError):
            result.artifacts[0].name = "changed"

    def test_deterministic_semantics_and_independent_raw_binding(self):
        a = artifact("one.pom") + artifact("two.module")
        b = artifact("Native.tar.gz")
        first = document(component(module="a", artifacts=a) + component(module="b", artifacts=b))
        second = document(component(module="b", artifacts=b) + component(
            module="a", artifacts=artifact("two.module", origin="informational") + artifact("one.pom")
        )).replace(b'group="org.sample" name="a"', b'name="a" group="org.sample"')
        second = second.replace(b"<components>", b"<components>\n<!-- not authority -->\n")
        left, right = SEED.parse_allowlist(first), SEED.parse_allowlist(second)
        self.assertEqual(left.artifacts, right.artifacts)
        self.assertEqual(left.authority_sha256, right.authority_sha256)
        self.assertNotEqual(left.source_sha256, right.source_sha256)
        canonical = b'P2PKIT_DEPENDENCY_ALLOWLIST_V1\n' + \
            b'[["org.sample","a","1.0","one.pom","' + SHA.encode() + b'"],' + \
            b'["org.sample","a","1.0","two.module","' + SHA.encode() + b'"],' + \
            b'["org.sample","b","1.0","Native.tar.gz","' + SHA.encode() + b'"]]\n'
        self.assertEqual(left.authority_sha256, hashlib.sha256(canonical).hexdigest())

    def test_exact_coordinate_name_and_sha_are_all_required(self):
        result = SEED.parse_allowlist(document())
        original = result.artifacts[0]
        for field in range(5):
            values = list(original)
            values[field] = "b" * 64 if field == 4 else "different"
            with self.subTest(field=field):
                self.assertNotIn(SEED.Artifact(*values), result.artifacts)
        changed = SEED.parse_allowlist(document(component(artifacts=artifact(value="b" * 64))))
        self.assertNotEqual(changed.authority_sha256, result.authority_sha256)

    def test_eligibility_has_no_extension_filter_or_lock_intersection(self):
        names = ("sample.pom", "sample.module", "Native.tar.gz", "sample.zip", "sample.klib", "other.raw")
        raw = document(component(artifacts="".join(artifact(name) for name in names)))
        self.assertEqual({row.name for row in SEED.parse_allowlist(raw).artifacts}, set(names))
        # Directory inputs are not a supported metadata policy or copy instruction.
        self.reject(b"caches/modules-2/metadata-2.107")
        self.reject(document().replace(b'<components>', b'<components source="cache-manifest.json">'))

    def test_wrong_root_namespace_and_schema(self):
        raw = document()
        cases = (
            raw.replace(('xmlns="' + SEED.NAMESPACE + '"').encode(), b''),
            raw.replace(('xmlns="' + SEED.NAMESPACE + '"').encode(), b'xmlns="urn:wrong"'),
            raw.replace(b'<verification-metadata ', b'<components ').replace(
                b'</verification-metadata>', b'</components>'),
            raw.replace((' xsi:schemaLocation="' + SEED.SCHEMA_LOCATION + '"').encode(), b''),
            raw.replace(b'dependency-verification-1.4.xsd', b'dependency-verification-1.5.xsd'),
            raw.replace(b'xsi:schemaLocation=', b'schemaLocation='),
            raw.replace(b'<components>', b'<components xmlns="urn:wrong">'),
        )
        for value in cases:
            with self.subTest(raw=value):
                self.reject(value)

    def test_wrong_or_additional_containers(self):
        raw = document()
        for value in (
            document(configuration=''), document(components=''),
            document(configuration=CONFIGURATION * 2),
            raw.replace(b'</components>', b'</components><components/>'),
            document(component(artifacts='')),
            raw.replace(b'<components>', b'<configuration><components>').replace(
                b'</components>', b'</components></configuration>'),
        ):
            with self.subTest(raw=value):
                self.reject(value)

    def test_root_child_order_is_closed(self):
        raw = (HEADER + '<components>' + component() + '</components>' + CONFIGURATION +
               '</verification-metadata>').encode()
        self.reject(raw, "XML_CHILDREN")

    def test_configuration_values_are_literal(self):
        for text in ('false', 'TRUE', 'True', '1', 'yes', 'tr ue', 'true false', ''):
            with self.subTest(text=text):
                self.reject(document(configuration=CONFIGURATION.replace('>true<', '>' + text + '<')))
        for text in ('true', 'FALSE', '0', 'fal se', ''):
            with self.subTest(text=text):
                self.reject(document(configuration=CONFIGURATION.replace('>false<', '>' + text + '<')))

    def test_boolean_outer_whitespace_comments_and_character_references(self):
        raw = document(configuration=CONFIGURATION.replace('>true<', '> \ntr<!-- split -->u&#101;\t<').replace(
            '>false<', '>\tfalse \n<'))
        self.assertEqual(SEED.parse_allowlist(raw).artifacts, SEED.parse_allowlist(document()).artifacts)
        self.reject(document(configuration=CONFIGURATION.replace('>true<', '>tr<!-- split --> ue<')))

    def test_unknown_attributes_and_configuration_children(self):
        raw = document()
        for element in ('verification-metadata', 'configuration', 'verify-metadata', 'verify-signatures',
                        'components', 'component', 'artifact', 'sha256'):
            with self.subTest(element=element):
                value = re.sub(('<' + element).encode() + rb'(?=[\s>])',
                               ('<' + element + ' unsafe="yes"').encode(), raw, count=1)
                self.reject(value, "XML_ATTRIBUTES")
        self.reject(document(configuration=CONFIGURATION.replace('<verify-signatures>', '<verify-metadata>').replace(
            '</verify-signatures>', '</verify-metadata>')))
        self.reject(document(configuration=CONFIGURATION.replace('>true<', '><sha256 value="' + SHA + '"/>true<')))

    def test_trust_policy_and_weak_or_multiple_checksums_are_refused(self):
        raw = document()
        for tag in ('trusted-artifacts', 'ignored-keys', 'key-servers', 'trusted-keys', 'pgp', 'also-trust', 'sha1', 'md5'):
            with self.subTest(tag=tag):
                self.reject(raw.replace(b'</configuration>', ('<' + tag + '/></configuration>').encode()))
        self.reject(raw.replace(b'<sha256', b'<sha1'))
        checksum = ('<sha256 value="' + SHA + '"/>').encode()
        self.reject(raw.replace(checksum, checksum * 2), "XML_CHILDREN")
        self.reject(raw.replace(checksum, b''), "XML_CHILDREN")
        self.reject(raw.replace(checksum, checksum.replace(b'/>', b'><also-trust value="x"/></sha256>')))

    def test_sha256_and_origin_bounds(self):
        for value in ('', 'a' * 63, 'a' * 65, 'A' * 64, 'g' * 64, ' ' + SHA, SHA + ' '):
            with self.subTest(value=value):
                self.reject(document(component(artifacts=artifact(value=value))), "XML_SHA256")
        exact = "a" * (SEED.MAX_ORIGIN_BYTES - 3) + "éx"
        self.assertEqual(len(exact.encode()), SEED.MAX_ORIGIN_BYTES)
        SEED.parse_allowlist(document(component(artifacts=artifact(origin=exact))))
        self.reject(document(component(artifacts=artifact(origin=exact + "a"))), "XML_ORIGIN_LIMIT")
        self.reject(document().replace(b'<sha256 value=', b'<sha256 missing='), "XML_ATTRIBUTES")

    def test_nonstructural_text_is_whitespace_only(self):
        raw = document()
        for marker in (b'<components>', b'<configuration>', b'</component>', b'</artifact>', b'</components>'):
            with self.subTest(marker=marker):
                self.reject(raw.replace(marker, marker + b'not-whitespace'), "XML_MIXED_TEXT")
        self.reject(raw.replace(b'/></artifact>', b'>content</sha256></artifact>'), "XML_MIXED_TEXT")

    def test_processing_instructions_and_doctypes_never_gain_authority(self):
        raw = document()
        declaration_end = raw.index(b'?>') + 2
        for markup in (
            b'<?probe untrusted?>', b'<?xml-stylesheet href="https://invalid.example/schema"?>',
            b'<!DOCTYPE verification-metadata SYSTEM "https://invalid.example/data">',
            b'<!DOCTYPE verification-metadata [<!ENTITY x SYSTEM "file:///never-open">]>',
            b'<!DOCTYPE verification-metadata [<!ENTITY a "many"><!ENTITY b "&a;&a;">]>',
            b'<!DOCTYPE verification-metadata [<!ENTITY % p SYSTEM "https://invalid.example/p">%p;]>',
        ):
            with self.subTest(markup=markup):
                self.reject(raw[:declaration_end] + markup + raw[declaration_end:], "XML_UNSUPPORTED_DECLARATION")
        self.reject(raw + b'<?probe after?>', "XML_UNSUPPORTED_DECLARATION")
        self.reject(raw.replace(b'<components>', b'<components><?probe inside?>'), "XML_UNSUPPORTED_DECLARATION")
        # A comment is inert text, not a DTD to reject with an overbroad regex.
        allowed = raw.replace(b'<components>', b'<components><!-- <!DOCTYPE text> -->')
        self.assertEqual(SEED.parse_allowlist(allowed).artifacts, SEED.parse_allowlist(raw).artifacts)

    def test_encoding_declaration_and_malformed_inputs(self):
        raw = document()
        for value in (
            b'', b'\xff', raw.decode().encode('utf-16'), raw + b'\x00', raw[:-5], raw + raw,
            raw.replace(b'encoding="UTF-8"', b'encoding="ISO-8859-1"'),
            raw.replace(b'version="1.0"', b'version="1.1"'),
            raw.replace(b'encoding="UTF-8"', b'encoding="UTF-8" standalone="yes"'),
            raw.replace(b'<components>', b'<components> &undefined;'),
            raw.replace(b'group="org.sample"', b'group="org.sample" group="duplicate"'),
        ):
            with self.subTest(raw=value):
                self.reject(value)
        for value in (raw.decode(), bytearray(raw), memoryview(raw), None, True):
            with self.subTest(type=type(value)):
                self.reject(value, "XML_BYTE_LIMIT")
        self.assertEqual(SEED.parse_allowlist(raw).artifacts, SEED.parse_allowlist(b'\xef\xbb\xbf' + raw).artifacts)
        self.assertEqual(SEED.parse_allowlist(raw).artifacts, SEED.parse_allowlist(raw.split(b'?>', 1)[1]).artifacts)

    def test_unsafe_names_in_every_coordinate_and_filename(self):
        names = ('', '.', '..', '.hidden', '../x', 'x/y', 'x\\y', 'a:b', 'space name', 'x.', 'é', 'а',
                 'CON', 'con.txt', 'PRN', 'NUL.jar', 'AUX', 'COM1', 'lPt9.log', 'CONIN$', 'CONOUT$')
        for name in names:
            for field in ('group', 'module', 'version', 'artifact'):
                with self.subTest(name=name, field=field):
                    options = {'artifacts': artifact(name)} if field == 'artifact' else {field: name}
                    self.reject(document(component(**options)))

    def test_legitimate_mixed_case_and_long_names(self):
        for name in ('FastInfoset-1.2.16.jar', 'org.jetbrains.kotlin', 'Something_iosSimulatorArm64.klib',
                     'a' * 128, 'x+y-1_2', 'COM10.jar', 'console.jar'):
            for field in ('group', 'module', 'version', 'artifact'):
                with self.subTest(name=name, field=field):
                    options = {'artifacts': artifact(name)} if field == 'artifact' else {field: name}
                    SEED.parse_allowlist(document(component(**options)))
        for field in ('group', 'module', 'version', 'artifact'):
            options = {'artifacts': artifact('x' * 129)} if field == 'artifact' else {field: 'x' * 129}
            self.reject(document(component(**options)), "SEED_BASENAME")

    def test_duplicate_components_and_casefolded_aliases(self):
        for other in (component(), component(group='ORG.SAMPLE'), component(module='SAMPLE'), component(version='1.0')):
            self.reject(document(component() + other), "XML_DUPLICATE_COMPONENT")
        for other in (component(group='ORG.SAMPLE', module='other'),
                      component(module='SAMPLE', version='2.0')):
            self.reject(document(component() + other), "XML_COMPONENT_PREFIX_ALIAS")
        SEED.parse_allowlist(document(component() + component(version='2.0')))

    def test_duplicate_artifacts_even_with_another_checksum(self):
        for other in (artifact(), artifact('SAMPLE.jar'), artifact(value='a' * 64)):
            self.reject(document(component(artifacts=artifact() + other)), "XML_DUPLICATE_ARTIFACT")

    def test_exact_and_one_over_relative_path_limit(self):
        fields = {'group': 'g' * 128, 'module': 'm' * 128, 'version': 'v' * 128}
        prefix = '/'.join((SEED.FILESTORE_PREFIX, *fields.values(), '0' * 40, ''))
        size = SEED.MAX_RELATIVE_BYTES - len(prefix)
        self.assertTrue(0 < size < 128)
        SEED.parse_allowlist(document(component(**fields, artifacts=artifact('f' * size))))
        self.reject(document(component(**fields, artifacts=artifact('f' * (size + 1)))), "SEED_RELATIVE_LIMIT")

    def test_exact_and_one_over_xml_byte_limit(self):
        raw = document()
        padded = raw + b' ' * (SEED.MAX_XML_BYTES - len(raw))
        SEED.parse_allowlist(padded)
        self.reject(padded + b' ', "XML_BYTE_LIMIT")

    def test_exact_and_one_over_component_limit(self):
        body = ''.join(component(module='m' + str(i)) for i in range(SEED.MAX_COMPONENTS))
        self.assertEqual(SEED.parse_allowlist(document(body)).component_count, SEED.MAX_COMPONENTS)
        self.reject(document(body + component(module='one-more')), "XML_COMPONENT_LIMIT")

    def test_exact_and_one_over_artifact_limit(self):
        body = ''.join(artifact('f' + str(i)) for i in range(SEED.MAX_ARTIFACTS))
        raw = document(component(artifacts=body))
        self.assertEqual(len(SEED.parse_allowlist(raw).artifacts), SEED.MAX_ARTIFACTS)
        self.reject(document(component(artifacts=body + artifact('one-more'))), "XML_ARTIFACT_LIMIT")

    def test_exact_and_one_over_element_limit(self):
        # Five fixed elements + C components + 2*A artifact/checksum elements.
        count = SEED.MAX_ELEMENTS - 5 - 2 * SEED.MAX_ARTIFACTS
        self.assertTrue(0 < count < SEED.MAX_COMPONENTS)
        def fixture(components):
            extra = SEED.MAX_ARTIFACTS - components
            first = component(module='m0', artifacts=''.join(artifact('f' + str(i)) for i in range(extra + 1)))
            return document(first + ''.join(component(module='m' + str(i)) for i in range(1, components)))
        self.assertEqual(SEED.parse_allowlist(fixture(count)).element_count, SEED.MAX_ELEMENTS)
        self.reject(fixture(count + 1), "XML_ELEMENT_LIMIT")

    def test_depth_is_bounded_before_tree_validation(self):
        raw = (HEADER + '<components>' * 6 + '</components>' * 6 + '</verification-metadata>').encode()
        self.reject(raw, "XML_DEPTH_LIMIT")

    def test_unknown_namespace_refuses_before_attribute_expansion(self):
        original = SEED._Document.start
        observed = []
        def start(instance, name, attributes):
            observed.append(sum(map(len, attributes)))
            return original(instance, name, attributes)
        # Small, bounded reproduction: a raw-byte cap alone does not bound
        # arbitrary URI expansion repeated in every Expat attribute key.
        for uri in ('urn:' + 'a' * 16384, 'urn:unsupported', ''):
            raw = document().replace(
                b'<verification-metadata ',
                ('<verification-metadata xmlns:wide="' + uri + '" ' +
                 ' '.join('wide:a' + str(i) + '="x"' for i in range(128)) + ' ').encode(), 1
            )
            observed.clear()
            with self.subTest(uri_bytes=len(uri)), patch.object(SEED._Document, 'start', start):
                error = None
                try:
                    SEED.parse_allowlist(raw)
                except SEED.AllowlistError as failure:
                    error = str(failure)
                self.assertEqual(observed, [])
                # XML forbids an empty prefixed binding; Expat may reject it
                # before delivering the namespace callback itself.
                self.assertIn(error, ('XML_NAMESPACE_DECLARATION', 'XML_MALFORMED') if not uri else
                              ('XML_NAMESPACE_DECLARATION',))

    def test_bomless_utf16_cannot_reinterpret_utf8_valid_nul_bytes(self):
        raw = document().split(b'?>', 1)[1].strip().decode('ascii')
        for encoding in ('utf-16-le', 'utf-16-be'):
            with self.subTest(encoding=encoding):
                candidate = raw.encode(encoding)
                candidate.decode('utf-8')  # This alone is not encoding admission.
                self.reject(candidate, "XML_ENCODING")

    def test_known_namespace_prefix_aliases_preserve_semantics(self):
        raw = document()
        alias = raw.replace(b'xmlns:xsi=', b'xmlns:schema=').replace(b'xsi:schemaLocation=', b'schema:schemaLocation=')
        alias = alias.replace(b'<components>', ('<d:components xmlns:d="' + SEED.NAMESPACE + '">').encode())
        alias = alias.replace(b'</components>', b'</d:components>')
        left, right = SEED.parse_allowlist(raw), SEED.parse_allowlist(alias)
        self.assertEqual(left.artifacts, right.artifacts)
        self.assertEqual(left.authority_sha256, right.authority_sha256)
        self.assertNotEqual(left.source_sha256, right.source_sha256)


if __name__ == "__main__":
    unittest.main(verbosity=2)
