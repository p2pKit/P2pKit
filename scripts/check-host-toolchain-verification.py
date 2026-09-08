#!/usr/bin/env python3
"""Require reviewed host classifiers, not just the updating machine's artifacts.

This is a completeness/format tripwire, not publisher authentication. Curate
new hashes with review-dependency-verification.sh before admitting them.
"""

import argparse
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


# Independent approval inputs. Review these with the catalog/toolchain update;
# do not infer either the versions or supported hosts from verification XML.
KOTLIN = "2.4.10"
AGP = "9.3.1"
AAPT2 = "9.3.1-15703166"
NATIVE_HOSTS = (
    "linux-x86_64.tar.gz",
    "macos-aarch64.tar.gz",
    "macos-x86_64.tar.gz",
    "windows-x86_64.zip",
)
AAPT2_HOSTS = ("linux", "osx", "windows")
NS = "{https://schema.gradle.org/dependency-verification}"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def catalog_version(text, key):
    sections = re.split(r"(?m)^\[([^\]\n]+)\][ \t]*$", text)
    versions = [sections[i + 1] for i in range(1, len(sections), 2) if sections[i] == "versions"]
    require(len(versions) == 1, "catalog must contain one [versions] section")
    assignments = re.findall(r"(?m)^" + re.escape(key) + r"[ \t]*=(.*)$", versions[0])
    require(len(assignments) == 1, "catalog must contain one versions." + key)
    match = re.fullmatch(r'[ \t]*"([^"\n]+)"[ \t]*(?:#.*)?', assignments[0])
    require(match is not None, "invalid catalog versions." + key)
    return match.group(1)


def check(root):
    catalog = (root / "gradle/libs.versions.toml").read_text(encoding="utf-8")
    require(catalog_version(catalog, "kotlin") == KOTLIN, "review Kotlin host classifiers for the new toolchain")
    require(catalog_version(catalog, "agp") == AGP, "review the AGP/AAPT2 host-classifier pair for the new toolchain")
    metadata = (root / "gradle/verification-metadata.xml").read_bytes()
    require(b"<!DOCTYPE" not in metadata.upper() and b"<!ENTITY" not in metadata.upper(),
            "verification metadata must not contain DTD/entity declarations")
    tree = ET.fromstring(metadata)
    require(tree.tag == NS + "verification-metadata", "unexpected verification metadata namespace/root")
    containers = tree.findall(NS + "components")
    require(len(containers) == 1, "verification metadata must contain one components element")
    components = containers[0].findall(NS + "component")
    expected = (
        ("org.jetbrains.kotlin", "kotlin-native-prebuilt", KOTLIN,
         tuple("kotlin-native-prebuilt-" + KOTLIN + "-" + host for host in NATIVE_HOSTS)),
        ("com.android.tools.build", "aapt2", AAPT2,
         tuple("aapt2-" + AAPT2 + "-" + host + ".jar" for host in AAPT2_HOSTS)),
    )
    checked = 0
    for group, name, version, names in expected:
        label = group + ":" + name + ":" + version
        matches = [c for c in components if
                   (c.get("group"), c.get("name"), c.get("version")) == (group, name, version)]
        require(len(matches) == 1, "expected exactly one component " + label)
        artifacts = matches[0].findall(NS + "artifact")
        artifact_names = [a.get("name") for a in artifacts]
        require(len(set(artifact_names)) == len(artifact_names), "duplicate artifact in " + label)
        for artifact_name in names:
            artifacts_for_host = [a for a in artifacts if a.get("name") == artifact_name]
            require(len(artifacts_for_host) == 1, "missing host-toolchain artifact " + artifact_name)
            hashes = artifacts_for_host[0].findall(NS + "sha256")
            require(len(hashes) == 1 and len(hashes[0]) == 0 and
                    re.fullmatch(r"[0-9a-f]{64}", hashes[0].get("value", "")) is not None,
                    "expected one exact SHA-256 for " + artifact_name)
            checked += 1
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="repository or isolated fixture root")
    args = parser.parse_args()
    try:
        checked = check(args.root)
    except (OSError, UnicodeError, ValueError, ET.ParseError) as error:
        print("FATAL: " + str(error), file=sys.stderr)
        return 1
    print("RESULT: PASS — " + str(checked) + " current Native/AAPT2 host artifacts have exact checksum records; "
          "publisher provenance and host execution are separate gates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
