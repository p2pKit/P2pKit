"""Compile the data-only, exact-artifact authority for a future dependency seed.

This module performs no I/O and is not wired into a workflow or controller. It
does not restore/copy a cache, extract an archive, run Gradle or authorize a
dependency resolution. A later caller must bind the input bytes to its admitted
source; existing strict dependency locking/verification remains authoritative.
"""

from dataclasses import dataclass
import hashlib
import json
import re
from typing import NamedTuple, Tuple
from xml.parsers import expat


MAX_XML_BYTES = 1024 * 1024
MAX_COMPONENTS = 2048
MAX_ARTIFACTS = 4096
MAX_ELEMENTS = 10000
MAX_BASENAME_BYTES = 128
MAX_RELATIVE_BYTES = 512
MAX_ORIGIN_BYTES = 256

NAMESPACE = "https://schema.gradle.org/dependency-verification"
SCHEMA_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = NAMESPACE + " " + NAMESPACE + "/dependency-verification-1.4.xsd"
SCHEMA_ATTRIBUTE = SCHEMA_NAMESPACE + "}schemaLocation"
FILESTORE_PREFIX = "caches/modules-2/files-2.1"
_XML_SPACE = " \t\r\n"
_BASENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}\Z", re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_DEVICES = frozenset(("CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$")) | frozenset(
    prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)
)
_BOOLEAN_TEXT = {"verify-metadata": "true", "verify-signatures": "false"}
_TAGS = frozenset(("verification-metadata", "configuration", "components", "component", "artifact", "sha256"))
_TAGS = _TAGS | _BOOLEAN_TEXT.keys()


class AllowlistError(ValueError):
    """Finite policy refusal; never include untrusted XML values in the error."""


class Artifact(NamedTuple):
    group: str
    module: str
    version: str
    name: str
    sha256: str


@dataclass(frozen=True)
class Allowlist:
    """Immutable semantic rows plus separate raw-source and v1 authority hashes."""

    artifacts: Tuple[Artifact, ...]
    source_sha256: str
    authority_sha256: str
    component_count: int
    element_count: int


def _require(condition, code):
    if not condition:
        raise AllowlistError(code)


def _basename(value):
    # Deliberately separate from hosted_test_query's smaller private-path grammar.
    _require(isinstance(value, str) and _BASENAME.fullmatch(value) is not None, "SEED_BASENAME")
    _require(len(value) <= MAX_BASENAME_BYTES and not value.endswith("."), "SEED_BASENAME")
    _require(value.split(".", 1)[0].upper() not in _DEVICES, "SEED_DEVICE_NAME")
    return value


class _Node:
    __slots__ = ("tag", "attributes", "children", "boolean_position")

    def __init__(self, tag, attributes):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.boolean_position = 0


class _Document:
    """Bound the tree during parsing, before constructing any artifact authority."""

    def __init__(self):
        self.stack = []
        self.root = None
        self.elements = self.components = self.artifacts = 0

    def start(self, qualified, attributes):
        prefix = NAMESPACE + "}"
        _require(qualified.startswith(prefix), "XML_NAMESPACE")
        tag = qualified[len(prefix):]
        _require(tag in _TAGS, "XML_ELEMENT")
        self.elements += 1
        self.components += tag == "component"
        self.artifacts += tag == "artifact"
        _require(self.elements <= MAX_ELEMENTS, "XML_ELEMENT_LIMIT")
        _require(self.components <= MAX_COMPONENTS, "XML_COMPONENT_LIMIT")
        _require(self.artifacts <= MAX_ARTIFACTS, "XML_ARTIFACT_LIMIT")
        _require(len(self.stack) < 5, "XML_DEPTH_LIMIT")
        node = _Node(tag, attributes)
        if self.stack:
            self.stack[-1].children.append(node)
        else:
            _require(self.root is None, "XML_ROOT")
            self.root = node
        self.stack.append(node)

    def end(self, qualified):
        node = self.stack.pop()
        _require(qualified == NAMESPACE + "}" + node.tag, "XML_NESTING")
        if node.tag in _BOOLEAN_TEXT:
            _require(node.boolean_position == len(_BOOLEAN_TEXT[node.tag]), "XML_CONFIGURATION")

    def text(self, value):
        if not self.stack or self.stack[-1].tag not in _BOOLEAN_TEXT:
            _require(not value.strip(_XML_SPACE), "XML_MIXED_TEXT")
            return
        node = self.stack[-1]
        expected = _BOOLEAN_TEXT[node.tag]
        # Accept outer whitespace without buffering it. Internal whitespace is
        # not a boolean spelling, even across comment/entity callback boundaries.
        for character in value:
            position = node.boolean_position
            if character in _XML_SPACE and position in (0, len(expected)):
                continue
            _require(position < len(expected) and character == expected[position], "XML_CONFIGURATION")
            node.boolean_position += 1


def _forbidden(*_arguments):
    raise AllowlistError("XML_UNSUPPORTED_DECLARATION")


def _declaration(version, encoding, standalone):
    _require(version == "1.0" and (encoding is None or encoding.upper() == "UTF-8")
             and standalone == -1, "XML_DECLARATION")


def _namespace(_prefix, uri):
    # Expat expands a URI into every qualified attribute name before delivering
    # an element. Refuse arbitrary URIs here, before that memory amplification;
    # equivalent prefix aliases of these two fixed namespaces remain harmless.
    _require(uri in (NAMESPACE, SCHEMA_NAMESPACE), "XML_NAMESPACE_DECLARATION")


def _attributes(node, required, optional=()):
    actual = set(node.attributes)
    _require(set(required) <= actual <= set(required) | set(optional), "XML_ATTRIBUTES")


def _children(node, tags):
    _require([child.tag for child in node.children] == list(tags), "XML_CHILDREN")


def parse_allowlist(raw):
    """Return all exact coordinate/name/SHA256 rows in the supported v1 grammar.

    Comments, attribute order and informational origin do not choose authority.
    The independent source hash still changes when any original XML byte changes.
    Schema location is checked literally; no schema/network lookup is performed.
    """
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_XML_BYTES, "XML_BYTE_LIMIT")
    # NUL is UTF-8-decodable but illegal XML1.0. Expat otherwise autodetects
    # BOM-less UTF-16 despite an explicit UTF-8 encoding hint.
    _require(b"\x00" not in raw, "XML_ENCODING")
    try:
        raw.decode("utf-8", "strict")
    except UnicodeError:
        raise AllowlistError("XML_ENCODING") from None

    document = _Document()
    parser = expat.ParserCreate(encoding="UTF-8", namespace_separator="}")
    parser.StartElementHandler = document.start
    parser.EndElementHandler = document.end
    parser.CharacterDataHandler = document.text
    parser.XmlDeclHandler = _declaration
    parser.StartNamespaceDeclHandler = _namespace
    parser.StartDoctypeDeclHandler = _forbidden
    parser.EntityDeclHandler = _forbidden
    parser.ExternalEntityRefHandler = _forbidden
    parser.ProcessingInstructionHandler = _forbidden
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        parser.Parse(raw, True)
    except expat.ExpatError:
        raise AllowlistError("XML_MALFORMED") from None

    root = document.root
    _require(root is not None and root.tag == "verification-metadata" and not document.stack, "XML_ROOT")
    _attributes(root, (SCHEMA_ATTRIBUTE,))
    _require(root.attributes[SCHEMA_ATTRIBUTE] == SCHEMA_LOCATION, "XML_SCHEMA_LOCATION")
    _children(root, ("configuration", "components"))
    configuration, components = root.children
    _attributes(configuration, ())
    _children(configuration, ("verify-metadata", "verify-signatures"))
    for child in configuration.children:
        _attributes(child, ())
        _children(child, ())
    _attributes(components, ())
    _require(bool(components.children), "XML_EMPTY_COMPONENTS")

    rows, component_keys, artifact_keys, prefixes = [], set(), set(), {}
    for component in components.children:
        _require(component.tag == "component", "XML_COMPONENT")
        _attributes(component, ("group", "name", "version"))
        coordinate = tuple(_basename(component.attributes[key]) for key in ("group", "name", "version"))
        folded = tuple(part.casefold() for part in coordinate)
        _require(folded not in component_keys, "XML_DUPLICATE_COMPONENT")
        component_keys.add(folded)
        # Also reject a directory-prefix alias across otherwise distinct keys:
        # Group:a:1 and group:b:2 must not share a Windows seed directory.
        for length in (1, 2, 3):
            previous = prefixes.setdefault(folded[:length], coordinate[:length])
            _require(previous == coordinate[:length], "XML_COMPONENT_PREFIX_ALIAS")
        _require(bool(component.children), "XML_EMPTY_COMPONENT")
        for artifact in component.children:
            _require(artifact.tag == "artifact", "XML_ARTIFACT")
            _attributes(artifact, ("name",))
            name = _basename(artifact.attributes["name"])
            key = (*folded, name.casefold())
            _require(key not in artifact_keys, "XML_DUPLICATE_ARTIFACT")
            artifact_keys.add(key)
            # The future SHA1 directory is a fixed-width layout address only;
            # a SHA1, extension or filename alone never grants byte authority.
            relative = "/".join((FILESTORE_PREFIX, *coordinate, "0" * 40, name))
            _require(len(relative) <= MAX_RELATIVE_BYTES, "SEED_RELATIVE_LIMIT")
            _children(artifact, ("sha256",))
            checksum = artifact.children[0]
            _attributes(checksum, ("value",), ("origin",))
            _children(checksum, ())
            value = checksum.attributes["value"]
            _require(_SHA256.fullmatch(value) is not None, "XML_SHA256")
            _require(len(checksum.attributes.get("origin", "").encode("utf-8")) <= MAX_ORIGIN_BYTES,
                     "XML_ORIGIN_LIMIT")
            rows.append(Artifact(*coordinate, name, value))

    artifacts = tuple(sorted(rows))
    canonical = b"P2PKIT_DEPENDENCY_ALLOWLIST_V1\n" + json.dumps(
        artifacts, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    ).encode("ascii") + b"\n"
    return Allowlist(artifacts, hashlib.sha256(raw).hexdigest(), hashlib.sha256(canonical).hexdigest(),
                     document.components, document.elements)
