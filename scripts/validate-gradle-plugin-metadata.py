#!/usr/bin/python3
"""Fail-closed validation for unsigned Gradle plugin publication metadata."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


MAVEN_NAMESPACE = "http://maven.apache.org/POM/4.0.0"
XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
COORDINATE = re.compile(r"[A-Za-z0-9_.-]+")
SHA256 = re.compile(r"[0-9a-f]{64}")
SHA512 = re.compile(r"[0-9a-f]{128}")
SHA1 = re.compile(r"[0-9a-f]{40}")
MD5 = re.compile(r"[0-9a-f]{32}")


def fail(message: str) -> "NoReturn":
    raise ValueError(message)


def read_bounded(path: str, maximum: int, label: str) -> bytes:
    data = Path(path).read_bytes()
    if not data or len(data) > maximum:
        fail(f"{label} must contain between 1 and {maximum} bytes")
    return data


def checked_coordinate(value: Any, label: str) -> str:
    if not isinstance(value, str) or not COORDINATE.fullmatch(value):
        fail(f"invalid {label}")
    return value


def parse_entries(path: str) -> set[tuple[str, str, str, str, str]]:
    result: set[tuple[str, str, str, str, str]] = set()
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        fields = raw.split("|")
        if len(fields) != 5 or not SHA256.fullmatch(fields[4]):
            fail(f"malformed verification-metadata entry at line {number}")
        result.add(tuple(fields))
    return result


def require_locked(path: str, group: str, module: str, version: str) -> None:
    expected = f"{group}:{module}:{version}"
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        coordinate, separator, configurations = raw.partition("=")
        if coordinate == expected and separator and "classpath" in configurations.split(","):
            return
    fail(f"component is absent from the buildscript classpath lock: {expected}")


def local_name(tag: str) -> str:
    if tag.startswith("{"):
        namespace, separator, name = tag[1:].partition("}")
        if not separator or namespace != MAVEN_NAMESPACE:
            fail("plugin marker POM contains an unsupported XML namespace")
        return name
    return tag


def require_whitespace(value: str | None, label: str) -> None:
    if value and value.strip():
        fail(f"plugin marker POM contains unexpected text in {label}")


def leaf_text(element: ET.Element, name: str) -> str:
    if local_name(element.tag) != name or list(element) or element.attrib:
        fail(f"plugin marker POM has malformed {name}")
    value = (element.text or "").strip()
    if not value or value != (element.text or "").strip():
        fail(f"plugin marker POM has an empty {name}")
    require_whitespace(element.tail, name)
    return value


def validate_marker(arguments: list[str]) -> None:
    if len(arguments) != 6:
        fail("marker usage: <pom> <group> <module> <version> <metadata-entries> <buildscript-lock>")
    pom_path, group, module, version, entries_path, lock_path = arguments
    checked_coordinate(group, "marker group")
    checked_coordinate(module, "marker module")
    checked_coordinate(version, "marker version")
    if module != f"{group}.gradle.plugin":
        fail(f"unsigned artifact is not a canonical Gradle plugin marker: {group}:{module}:{version}")

    raw = read_bounded(pom_path, 64 * 1024, "plugin marker POM")
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", raw, re.IGNORECASE):
        fail("plugin marker POM contains a DTD or entity")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        fail(f"plugin marker POM is not well-formed XML: {error}")
    if local_name(root.tag) != "project":
        fail("plugin marker POM root is not project")
    allowed_root_attributes = {f"{{{XSI_NAMESPACE}}}schemaLocation"}
    if set(root.attrib) - allowed_root_attributes:
        fail("plugin marker POM contains unsupported root attributes")
    require_whitespace(root.text, "project")
    require_whitespace(root.tail, "project")

    children = list(root)
    expected = ["modelVersion", "groupId", "artifactId", "version", "packaging", "dependencies"]
    if [local_name(child.tag) for child in children] != expected:
        fail("plugin marker POM contains unsupported elements or ordering")
    if leaf_text(children[0], "modelVersion") != "4.0.0":
        fail("plugin marker POM has an unsupported model version")
    if leaf_text(children[1], "groupId") != group:
        fail("plugin marker POM group does not match its coordinate")
    if leaf_text(children[2], "artifactId") != module:
        fail("plugin marker POM artifact does not match its coordinate")
    if leaf_text(children[3], "version") != version:
        fail("plugin marker POM version does not match its coordinate")
    if leaf_text(children[4], "packaging") != "pom":
        fail("plugin marker POM is not data-only pom packaging")

    dependencies = children[5]
    if dependencies.attrib:
        fail("plugin marker POM dependencies has attributes")
    require_whitespace(dependencies.text, "dependencies")
    require_whitespace(dependencies.tail, "dependencies")
    dependency_children = list(dependencies)
    if len(dependency_children) != 1 or local_name(dependency_children[0].tag) != "dependency":
        fail("plugin marker POM must contain exactly one dependency")
    dependency = dependency_children[0]
    if dependency.attrib:
        fail("plugin marker POM dependency has attributes")
    require_whitespace(dependency.text, "dependency")
    require_whitespace(dependency.tail, "dependency")
    fields = list(dependency)
    if [local_name(child.tag) for child in fields] != ["groupId", "artifactId", "version"]:
        fail("plugin marker POM dependency contains unsupported elements or ordering")

    implementation_group = checked_coordinate(leaf_text(fields[0], "groupId"), "implementation group")
    implementation_module = checked_coordinate(leaf_text(fields[1], "artifactId"), "implementation module")
    implementation_version = checked_coordinate(leaf_text(fields[2], "version"), "implementation version")
    entries = parse_entries(entries_path)
    implementation_jar = f"{implementation_module}-{implementation_version}.jar"
    if not any(
        entry[:4] == (implementation_group, implementation_module, implementation_version, implementation_jar)
        for entry in entries
    ):
        fail(
            "plugin marker implementation JAR is absent from verification metadata: "
            f"{implementation_group}:{implementation_module}:{implementation_version}"
        )
    require_locked(lock_path, implementation_group, implementation_module, implementation_version)
    print(f"{implementation_group}|{implementation_module}|{implementation_version}")


def no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"Gradle module metadata contains duplicate key: {key}")
        result[key] = value
    return result


def exact_keys(value: Any, allowed: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - allowed:
        fail(f"Gradle module metadata has unsupported {label} fields")
    return value


def validate_dependency(
    value: Any,
    entries: set[tuple[str, str, str, str, str]],
    lock_path: str,
) -> None:
    dependency = exact_keys(value, {"group", "module", "version", "excludes"}, "dependency")
    if not {"group", "module", "version"} <= set(dependency):
        fail("Gradle module metadata dependency is incomplete")
    group = checked_coordinate(dependency["group"], "dependency group")
    module = checked_coordinate(dependency["module"], "dependency module")
    version_value = exact_keys(dependency["version"], {"requires"}, "dependency version")
    if set(version_value) != {"requires"}:
        fail("Gradle module metadata dependency must use one exact required version")
    version = checked_coordinate(version_value["requires"], "dependency version")
    excludes = dependency.get("excludes", [])
    if not isinstance(excludes, list):
        fail("Gradle module metadata dependency exclusions are malformed")
    for exclusion_value in excludes:
        exclusion = exact_keys(exclusion_value, {"group", "module"}, "dependency exclusion")
        if set(exclusion) != {"group", "module"}:
            fail("Gradle module metadata dependency exclusion is incomplete")
        checked_coordinate(exclusion["group"], "excluded group")
        checked_coordinate(exclusion["module"], "excluded module")
    if not any(entry[:3] == (group, module, version) for entry in entries):
        fail(f"module dependency is absent from verification metadata: {group}:{module}:{version}")
    require_locked(lock_path, group, module, version)


def validate_file(value: Any, expected_jar: str, expected_sha: str, executable: bool) -> bool:
    artifact = exact_keys(value, {"name", "url", "size", "sha512", "sha256", "sha1", "md5"}, "file")
    required = {"name", "url", "size", "sha512", "sha256", "sha1", "md5"}
    if set(artifact) != required:
        fail("Gradle module metadata file is missing integrity fields")
    name = artifact["name"]
    if not isinstance(name, str) or not name or name != Path(name).name or artifact["url"] != name:
        fail("Gradle module metadata file contains a non-local artifact URL")
    if not isinstance(artifact["size"], int) or isinstance(artifact["size"], bool) or artifact["size"] <= 0:
        fail("Gradle module metadata file size is invalid")
    for key, pattern in (("sha512", SHA512), ("sha256", SHA256), ("sha1", SHA1), ("md5", MD5)):
        if not isinstance(artifact[key], str) or not pattern.fullmatch(artifact[key]):
            fail(f"Gradle module metadata file {key} is invalid")
    if executable and (name != expected_jar or artifact["sha256"] != expected_sha):
        fail("Gradle module metadata executable variant is not bound to the attested implementation JAR")
    return name == expected_jar and artifact["sha256"] == expected_sha


def validate_module(arguments: list[str]) -> None:
    if len(arguments) != 7:
        fail(
            "module usage: <module-json> <group> <module> <version> <jar-sha256> "
            "<metadata-entries> <buildscript-lock>"
        )
    module_path, group, module, version, jar_sha, entries_path, lock_path = arguments
    checked_coordinate(group, "module group")
    checked_coordinate(module, "module name")
    checked_coordinate(version, "module version")
    if not SHA256.fullmatch(jar_sha):
        fail("implementation JAR SHA-256 is invalid")
    raw = read_bounded(module_path, 1024 * 1024, "Gradle module metadata")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicate_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"Gradle module metadata is not strict UTF-8 JSON: {error}")
    root = exact_keys(document, {"formatVersion", "component", "createdBy", "variants"}, "top-level")
    if set(root) != {"formatVersion", "component", "createdBy", "variants"} or root["formatVersion"] != "1.1":
        fail("Gradle module metadata has an unsupported format")

    component = exact_keys(root["component"], {"group", "module", "version", "attributes"}, "component")
    if set(component) != {"group", "module", "version", "attributes"}:
        fail("Gradle module metadata component is incomplete")
    if (component["group"], component["module"], component["version"]) != (group, module, version):
        fail("Gradle module metadata component does not match its coordinate")
    if component["attributes"] != {"org.gradle.status": "release"}:
        fail("Gradle module metadata component attributes are unsupported")

    created_by = exact_keys(root["createdBy"], {"gradle"}, "createdBy")
    gradle = exact_keys(created_by.get("gradle"), {"version"}, "createdBy.gradle")
    if set(gradle) != {"version"} or not isinstance(gradle["version"], str) or not gradle["version"]:
        fail("Gradle module metadata producer version is invalid")

    entries = parse_entries(entries_path)
    expected_jar = f"{module}-{version}.jar"
    if (group, module, version, expected_jar, jar_sha) not in entries:
        fail("attested implementation JAR is absent from verification metadata")
    require_locked(lock_path, group, module, version)

    variants = root["variants"]
    if not isinstance(variants, list) or not variants:
        fail("Gradle module metadata has no variants")
    allowed_names = {"apiElements", "runtimeElements", "javadocElements", "sourcesElements"}
    executable_names = {"apiElements", "runtimeElements"}
    seen: set[str] = set()
    bound_executable: set[str] = set()
    allowed_attributes = {
        "org.gradle.category",
        "org.gradle.dependency.bundling",
        "org.gradle.docstype",
        "org.gradle.jvm.version",
        "org.gradle.libraryelements",
        "org.gradle.usage",
    }
    for variant_value in variants:
        variant = exact_keys(variant_value, {"name", "attributes", "dependencies", "files"}, "variant")
        if not {"name", "attributes", "files"} <= set(variant):
            fail("Gradle module metadata variant is incomplete")
        name = variant["name"]
        if name not in allowed_names or name in seen:
            fail("Gradle module metadata has an unsupported or duplicate variant")
        seen.add(name)
        attributes = exact_keys(variant["attributes"], allowed_attributes, "variant attributes")
        if not attributes or any(
            not isinstance(value, (str, int, bool)) or isinstance(value, float) for value in attributes.values()
        ):
            fail("Gradle module metadata variant attributes are malformed")
        dependencies = variant.get("dependencies", [])
        if not isinstance(dependencies, list) or (name not in executable_names and dependencies):
            fail("Gradle module metadata variant dependencies are malformed")
        for dependency in dependencies:
            validate_dependency(dependency, entries, lock_path)
        files = variant["files"]
        if not isinstance(files, list) or len(files) != 1:
            fail("Gradle module metadata variant must reference exactly one file")
        if validate_file(files[0], expected_jar, jar_sha, name in executable_names):
            bound_executable.add(name)
    if not executable_names <= seen or bound_executable != executable_names:
        fail("Gradle module metadata does not bind both executable variants to the attested JAR")
    print(f"{group}|{module}|{version}")


def validate_attestation(arguments: list[str]) -> None:
    if len(arguments) != 6:
        fail("attestation usage: <json> <sha256> <repo> <workflow> <source-ref> <source-digest>")
    json_path, expected_sha, repo, workflow, source_ref, source_digest = arguments
    if not SHA256.fullmatch(expected_sha):
        fail("attested artifact SHA-256 is invalid")
    raw = read_bounded(json_path, 8 * 1024 * 1024, "attestation result")
    try:
        results = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicate_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"attestation result is not strict UTF-8 JSON: {error}")
    if not isinstance(results, list) or not results:
        fail("attestation verifier returned no results")
    expected_san = f"https://github.com/{workflow}@{source_ref}"
    for result in results:
        if not isinstance(result, dict):
            continue
        verification = result.get("verificationResult")
        if not isinstance(verification, dict):
            continue
        statement = verification.get("statement")
        signature = verification.get("signature")
        certificate = signature.get("certificate") if isinstance(signature, dict) else None
        subjects = statement.get("subject") if isinstance(statement, dict) else None
        timestamps = verification.get("verifiedTimestamps")
        if not isinstance(certificate, dict) or not isinstance(subjects, list) or not timestamps:
            continue
        subject_matches = any(
            isinstance(subject, dict)
            and isinstance(subject.get("digest"), dict)
            and subject["digest"].get("sha256") == expected_sha
            for subject in subjects
        )
        if (
            subject_matches
            and statement.get("predicateType") == "https://slsa.dev/provenance/v1"
            and certificate.get("subjectAlternativeName") == expected_san
            and certificate.get("issuer") == "https://token.actions.githubusercontent.com"
            and certificate.get("githubWorkflowRepository") == repo
            and certificate.get("githubWorkflowRef") == source_ref
            and certificate.get("githubWorkflowSHA") == source_digest
            and certificate.get("sourceRepositoryDigest") == source_digest
            and certificate.get("sourceRepositoryRef") == source_ref
            and certificate.get("runnerEnvironment") == "github-hosted"
        ):
            return
    fail("attestation result does not contain the required artifact and trusted build identity")


def main() -> None:
    if len(sys.argv) < 2:
        fail("usage: validate-gradle-plugin-metadata.py <marker|module|attestation> ...")
    command, arguments = sys.argv[1], sys.argv[2:]
    if command == "marker":
        validate_marker(arguments)
    elif command == "module":
        validate_module(arguments)
    elif command == "attestation":
        validate_attestation(arguments)
    else:
        fail(f"unknown validation command: {command}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"FATAL: {error}", file=sys.stderr)
        raise SystemExit(1)
