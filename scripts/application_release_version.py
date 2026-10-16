#!/usr/bin/env python3
"""Independent, dependency-free verifier for the application version encoding.

Gradle uses ApplicationReleaseVersion.java. This implementation must agree with
the public vectors, not trust package-supplied version strings or AGP sidecars.
"""

import argparse
import json
from pathlib import Path
import re


VERSION = re.compile(r"(0|[1-9][0-9]?)\.(0|[1-9][0-9]?)\.(0|[1-9][0-9]?)(?:-(SNAPSHOT|(alpha|beta|rc)([1-9][0-9]?)))?")


def version_fields(name):
    match = VERSION.fullmatch(name) if isinstance(name, str) else None
    if match is None:
        raise ValueError("Unsupported canonical VERSION_NAME")
    major, minor, patch = map(int, match.group(1, 2, 3))
    rank = 399 if match[4] is None else 0 if match[4] == "SNAPSHOT" else (
        {"alpha": 0, "beta": 100, "rc": 200}[match[5]] + int(match[6]))
    native = f"{major + 1}.{minor}.{patch * 400 + rank}"
    return {"canonicalVersion": name, "androidVersionCode": 1 + (major * 10000 + minor * 100 + patch) * 400 + rank,
            "nativeVersion": native, "debianVersion": native + "-1"}


def _unescape(value):
    result, position = [], 0
    while position < len(value):
        char = value[position]
        position += 1
        if char == "\\":
            if position == len(value):
                raise ValueError("Truncated properties escape")
            char = value[position]
            position += 1
            if char == "u":
                code = value[position:position + 4]
                if not re.fullmatch(r"[0-9a-fA-F]{4}", code):
                    raise ValueError("Invalid properties Unicode escape")
                char, position = chr(int(code, 16)), position + 4
            else:
                char = {"t": "\t", "r": "\r", "n": "\n", "f": "\f"}.get(char, char)
        result.append(char)
    return "".join(result)


def from_properties(content):
    """Recognize Java properties aliases so a duplicate cannot hide behind an escape."""
    values, pending = [], ""
    # Java Properties/String.lines use CR/LF, not Python's Unicode line separators.
    physical_lines = re.split(r"\r\n|\r|\n", content)
    for physical in physical_lines:
        line = pending + physical.lstrip(" \t\f")
        if not pending and (not line or line[0] in "#!"):
            continue
        slashes = len(line) - len(line.rstrip("\\"))
        if slashes % 2:
            pending = line[:-1]
            continue
        pending = ""
        end = 0
        while end < len(line) and line[end] not in " \t\f:=":
            end += 2 if line[end] == "\\" else 1
        key = _unescape(line[:end])
        if key != "VERSION_NAME":
            continue
        rest = line[end:].lstrip(" \t\f")
        if rest.startswith(("=", ":")):
            rest = rest[1:]
        values.append(_unescape(rest.lstrip(" \t\f")))
    if pending or len(values) != 1 or physical_lines.count("VERSION_NAME=" + values[0]) != 1:
        raise ValueError("VERSION_NAME must be one canonical repository declaration")
    return version_fields(values[0])


def repository_version(root):
    path = Path(root) / "gradle.properties"
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError("Missing/linked/oversized canonical version file")
    return from_properties(path.read_text(encoding="utf-8"))


def embedded_identity(version, source):
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("Release application requires an exact source commit")
    return {"schema": 1, "sourceCommit": source, **version_fields(version)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    arguments = parser.parse_args()
    print(json.dumps(repository_version(arguments.root), sort_keys=True))
