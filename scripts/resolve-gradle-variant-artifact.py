#!/usr/bin/python3
"""Locate one artifact in already checksum/signature-verified Gradle metadata.

This parser grants no trust and follows no URLs. The caller must verify the
metadata before invoking it, then verify the returned artifact independently.
The default supports only a local file or one sibling-version directory in
the same module. Optional KMP mode requires an independently authenticated root
module, a reciprocal same-group/version publication link, and an exact SHA-256
for local filename aliases. It never follows an artifact URL to another module.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*")
GROUP = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*)*")
SHA256 = re.compile(r"[0-9a-f]{64}")
MAX_METADATA_BYTES = 1024 * 1024


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "variant metadata contains a duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError("variant metadata contains a non-JSON numeric constant")


def coordinates(group: str, module: str, version: str) -> None:
    require(GROUP.fullmatch(group) is not None, "invalid variant group")
    for value in (module, version):
        require(SEGMENT.fullmatch(value) is not None, "invalid variant coordinate or artifact name")


def read_document(path: str) -> dict[str, Any]:
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_METADATA_BYTES + 1)
    require(0 < len(raw) <= MAX_METADATA_BYTES, "variant metadata exceeds its nonempty 1 MiB limit")
    document = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    require(isinstance(document, dict), "variant metadata root is not an object")
    require(document.get("formatVersion") == "1.1", "unsupported variant metadata format")
    component = document.get("component")
    require(isinstance(component, dict), "variant metadata has no component identity")
    variants = document.get("variants")
    require(isinstance(variants, list) and bool(variants), "variant metadata has no variants")
    require(all(isinstance(variant, dict) for variant in variants), "variant record is not an object")
    return document


def kmp_root_module(document: dict[str, Any], group: str, module: str, version: str) -> str:
    """Return a safe coordinate, NOT a trusted URL, from an already authenticated locator."""
    component = document["component"]
    root = component.get("module")
    require(isinstance(root, str) and SEGMENT.fullmatch(root) is not None, "invalid KMP root module")
    require(component.get("group") == group and component.get("version") == version,
            "KMP root must retain the exact group and version")
    if "url" in component:
        require(root != module and component["url"] == f"../../{root}/{version}/{root}-{version}.module",
                "KMP root URL is not the exact same-group/version publication")
    else:
        require(root == module, "variant metadata component identity mismatch")
    require(any(isinstance(v.get("attributes"), dict) and
                v["attributes"].get("org.jetbrains.kotlin.platform.type") in ("common", "native", "jvm")
                for v in document["variants"]), "locator is not supported KMP metadata")
    return root


def root_coordinate(arguments: list[str]) -> str:
    require(len(arguments) == 4, "usage: --kmp-root <module-json> <group> <module> <version>")
    path, group, module, version = arguments
    coordinates(group, module, version)
    return kmp_root_module(read_document(path), group, module, version)


def kmp_publication_attributes(
    document: dict[str, Any], root_path: str, group: str, module: str, version: str,
) -> list[dict[str, Any]]:
    root_module = kmp_root_module(document, group, module, version)
    root = read_document(root_path)
    component = root["component"]
    require(all(component.get(k) == v for k, v in
                (("group", group), ("module", root_module), ("version", version))) and "url" not in component,
            "authenticated KMP root identity mismatch or redirect")
    if root_module == module:
        require(root == document, "KMP self-root must be the same authenticated metadata")
        return [v["attributes"] for v in root["variants"] if isinstance(v.get("attributes"), dict) and
                v["attributes"].get("org.jetbrains.kotlin.platform.type") == "common"]
    attributes = []
    for variant in root["variants"]:
        target = variant.get("available-at")
        if not isinstance(target, dict) or target.get("module") != module:
            continue
        require(target == {"group": group, "module": module, "version": version,
                           "url": f"../../{module}/{version}/{module}-{version}.module"},
                "KMP root does not reciprocate the exact child publication")
        require(isinstance(variant.get("attributes"), dict), "KMP root publication has no attributes")
        attributes.append(variant["attributes"])
    require(bool(attributes), "KMP root does not name the child publication")
    return attributes


def artifact_path(arguments: list[str]) -> str:
    require(len(arguments) in (6, 7),
            "usage: <module-json> <group> <module> <version> <artifact> <sha256> [<verified-kmp-root-json>]")
    path, group, module, version, artifact, expected_sha = arguments[:6]
    coordinates(group, module, version)
    require(SEGMENT.fullmatch(artifact) is not None, "invalid variant coordinate or artifact name")
    require(SHA256.fullmatch(expected_sha) is not None, "invalid variant artifact SHA-256")
    document = read_document(path)
    component = document["component"]
    kmp_attributes = None
    if len(arguments) == 7:
        kmp_attributes = kmp_publication_attributes(document, arguments[6], group, module, version)
    else:
        require("url" not in component, "variant metadata component redirects are unsupported")
    require(
        kmp_attributes is not None or all(component.get(key) == value for key, value in
                                          (("group", group), ("module", module), ("version", version))),
        "variant metadata component identity mismatch",
    )

    paths: set[str] = set()
    for variant in document["variants"]:
        files = variant.get("files", [])
        require(isinstance(files, list), "variant files is not an array")
        for entry in files:
            require(isinstance(entry, dict), "variant file is not an object")
            if entry.get("name") != artifact:
                continue
            require("available-at" not in variant, "artifact variant also declares an unsupported redirect")
            if kmp_attributes is not None:
                require(variant.get("attributes") in kmp_attributes,
                        "KMP artifact attributes are not bound by the authenticated root")
            url = entry.get("url")
            require(isinstance(url, str), "variant artifact URL is missing")
            if "sha256" in entry:
                require(entry["sha256"] == expected_sha, "variant file SHA-256 disagrees with verification metadata")
            # Reject schemes, absolute paths, encoded escapes, query/fragment
            # data, extra traversal and changed basenames by construction.
            parts = url.split("/")
            located_artifact = artifact
            if parts == [artifact]:
                located_version = version
            elif kmp_attributes is not None and len(parts) == 1 and SEGMENT.fullmatch(url) is not None:
                require(entry.get("sha256") == expected_sha, "KMP filename alias requires its exact SHA-256")
                require(Path(url).suffix == Path(artifact).suffix and Path(url).suffix in (".jar", ".klib"),
                        "unsupported KMP filename alias artifact type")
                located_version = version
                located_artifact = url
            else:
                require(
                    len(parts) == 3 and parts[0] == ".." and
                    SEGMENT.fullmatch(parts[1]) is not None and parts[2] == artifact,
                    "variant artifact URL is not a same-module local or sibling-version file",
                )
                located_version = parts[1]
            paths.add(f"{group.replace('.', '/')}/{module}/{located_version}/{located_artifact}")

    require(bool(paths), "variant metadata does not name the requested artifact")
    require(len(paths) == 1, "variant metadata has ambiguous artifact locations")
    return next(iter(paths))


if __name__ == "__main__":
    try:
        if sys.argv[1:2] == ["--kmp-root"]:
            print(root_coordinate(sys.argv[2:]))
        else:
            print(artifact_path(sys.argv[1:]))
    except (OSError, ValueError, RecursionError) as error:
        print(f"FATAL: {error}", file=sys.stderr)
        sys.exit(1)
