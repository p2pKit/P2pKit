#!/usr/bin/python3
"""Locate one artifact in already checksum/signature-verified Gradle metadata.

This parser grants no trust and follows no URLs. The caller must verify the
metadata before invoking it, then verify the returned artifact independently.
Only a local file or one sibling-version directory in the same module is
supported; available-at redirects and cross-repository/module files are not.
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


def artifact_path(arguments: list[str]) -> str:
    require(len(arguments) == 6, "usage: <module-json> <group> <module> <version> <artifact> <sha256>")
    path, group, module, version, artifact, expected_sha = arguments
    require(GROUP.fullmatch(group) is not None, "invalid variant group")
    for value in (module, version, artifact):
        require(SEGMENT.fullmatch(value) is not None, "invalid variant coordinate or artifact name")
    require(SHA256.fullmatch(expected_sha) is not None, "invalid variant artifact SHA-256")

    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_METADATA_BYTES + 1)
    require(0 < len(raw) <= MAX_METADATA_BYTES, "variant metadata exceeds its nonempty 1 MiB limit")
    document = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    require(isinstance(document, dict), "variant metadata root is not an object")
    require(document.get("formatVersion") == "1.1", "unsupported variant metadata format")
    component = document.get("component")
    require(isinstance(component, dict), "variant metadata has no component identity")
    require(
        all(component.get(key) == value for key, value in (("group", group), ("module", module), ("version", version))),
        "variant metadata component identity mismatch",
    )
    require("url" not in component, "variant metadata component redirects are unsupported")
    variants = document.get("variants")
    require(isinstance(variants, list) and bool(variants), "variant metadata has no variants")

    paths: set[str] = set()
    for variant in variants:
        require(isinstance(variant, dict), "variant record is not an object")
        files = variant.get("files", [])
        require(isinstance(files, list), "variant files is not an array")
        for entry in files:
            require(isinstance(entry, dict), "variant file is not an object")
            if entry.get("name") != artifact:
                continue
            require("available-at" not in variant, "artifact variant also declares an unsupported redirect")
            url = entry.get("url")
            require(isinstance(url, str), "variant artifact URL is missing")
            if "sha256" in entry:
                require(entry["sha256"] == expected_sha, "variant file SHA-256 disagrees with verification metadata")
            # Reject schemes, absolute paths, encoded escapes, query/fragment
            # data, extra traversal and changed basenames by construction.
            parts = url.split("/")
            if parts == [artifact]:
                located_version = version
            else:
                require(
                    len(parts) == 3 and parts[0] == ".." and
                    SEGMENT.fullmatch(parts[1]) is not None and parts[2] == artifact,
                    "variant artifact URL is not a same-module local or sibling-version file",
                )
                located_version = parts[1]
            paths.add(f"{group.replace('.', '/')}/{module}/{located_version}/{artifact}")

    require(bool(paths), "variant metadata does not name the requested artifact")
    require(len(paths) == 1, "variant metadata has ambiguous artifact locations")
    return next(iter(paths))


if __name__ == "__main__":
    try:
        print(artifact_path(sys.argv[1:]))
    except (OSError, ValueError, RecursionError) as error:
        print(f"FATAL: {error}", file=sys.stderr)
        sys.exit(1)
