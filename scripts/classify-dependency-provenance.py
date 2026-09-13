#!/usr/bin/env python3
"""Select remote curation or exact, operator-reviewed base provenance reuse.

This is called only AFTER the supported writer and strict post-write gates. It
does not establish that a base was reviewed, validate artifacts remotely, or
accept a partial writer. REUSE deliberately admits only a project-lock delta:
even the root buildscript/settings locks and all other tracked inputs stay fixed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
METADATA = "gradle/verification-metadata.xml"
MAX_METADATA_BYTES = 16 * 1024 * 1024
NS = "{https://schema.gradle.org/dependency-verification}"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE, timeout=30)


def metadata(raw):
    require(0 < len(raw) <= MAX_METADATA_BYTES, "missing, empty or oversized verification metadata")
    text = raw.decode("utf-8", "strict")
    declaration = re.match(r"\ufeff?<\?xml\s+([^?]*)\?>", text)
    if declaration:
        encoding = re.search(r"\bencoding\s*=\s*(['\"])([^'\"]+)\1", declaration.group(1))
        require(encoding is None or encoding.group(2).lower() == "utf-8",
                "verification metadata declaration must use UTF-8")
    require(b"\0" not in raw and not re.search(br"<!\s*(DOCTYPE|ENTITY)", raw, re.I),
            "verification metadata must not contain DTDs/entities or NUL bytes")
    root = ET.fromstring(text)
    require(root.tag == NS + "verification-metadata", "wrong verification metadata root/namespace")
    schema = "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"
    namespace = NS[1:-1]
    require(set(root.attrib) == {schema} and root.attrib[schema].split() ==
            [namespace, namespace + "/dependency-verification-1.4.xsd"], "wrong verification metadata schema")
    require([node.tag for node in root] == [NS + "configuration", NS + "components"],
            "verification metadata must have exactly one configuration and component list")
    configuration, components = root
    for node in root.iter():
        require(not (node.tail or "").strip(), "unsupported verification metadata tail text")
        if node.tag not in (NS + "verify-metadata", NS + "verify-signatures"):
            require(not (node.text or "").strip(), "unsupported verification metadata container/checksum text")
    require(not components.attrib, "unsupported verification component-list attributes")
    require([(node.tag, (node.text or "").strip()) for node in configuration] ==
            [(NS + "verify-metadata", "true"), (NS + "verify-signatures", "false")] and
            all(not list(node) and not node.attrib for node in configuration) and not configuration.attrib,
            "verification trust policy differs from the reviewed strict policy")
    entries, coordinates = {}, set()
    for component in components:
        require(component.tag == NS + "component" and set(component.attrib) == {"group", "name", "version"},
                "malformed verified component")
        coordinate = tuple(component.attrib[key] for key in ("group", "name", "version"))
        require(all(coordinate) and coordinate not in coordinates and len(component) > 0,
                "empty or duplicate verified component")
        coordinates.add(coordinate)
        for artifact in component:
            require(artifact.tag == NS + "artifact" and set(artifact.attrib) == {"name"} and
                    artifact.attrib["name"] and len(artifact) == 1, "malformed verified artifact")
            checksum = artifact[0]
            value = checksum.attrib.get("value", "")
            require(checksum.tag == NS + "sha256" and re.fullmatch(r"[0-9a-f]{64}", value) and
                    set(checksum.attrib) <= {"value", "origin"} and not list(checksum),
                    "artifact must have exactly one valid SHA-256")
            key = (*coordinate, artifact.attrib["name"])
            require(key not in entries, "duplicate verified artifact")
            entries[key] = value
    require(entries, "verification metadata contains no artifact checksums")
    return entries


def base_files(base):
    result = {}
    for item in git("ls-tree", "-r", "-z", base).split(b"\0"):
        if item:
            fields, name = item.split(b"\t", 1)
            mode, kind, oid = fields.decode("ascii").split()
            result[name.decode("utf-8")] = (mode, kind, oid)
    return result


def reuse_inputs(base, files):
    # The buildscript lock is part of plugin-marker/module provenance; settings
    # is also a tool lock. Neither is a project lock eligible for this lane.
    eligible = {name for name, (mode, kind, _) in files.items()
                if kind == "blob" and mode == "100644" and
                (name == "gradle.lockfile" or re.fullmatch(r"(?:library|samples)/[^/]+/gradle\.lockfile", name))}
    changes = {}
    for flags in ((), ("--cached",)):
        changed = git("diff", "--no-ext-diff", "--no-renames", *flags,
                      "--name-status", "-z", base, "--").split(b"\0")
        require(changed[-1] == b"", "malformed Git change inventory")
        changed.pop()
        require(len(changed) % 2 == 0, "malformed Git change inventory")
        for kind, raw_name in zip(changed[::2], changed[1::2]):
            name = raw_name.decode("utf-8")
            require(kind == b"M" and name in eligible,
                    "unchanged metadata cannot reuse provenance after non-project-lock input changes: " + name)
            changes[name] = kind
    locks = []
    for name in sorted(changes):
        path = ROOT / name
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and not info.st_mode & 0o111,
                "reused project lock changed type or executable mode: " + name)
        locks.append({"path": name, "baseBlob": files[name][2],
                      "candidateSha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    require(not git("ls-files", "--others", "--exclude-standard", "-z"),
            "untracked inputs prevent exact reviewed-base provenance reuse")
    indexed = set()
    for item in git("ls-files", "--stage", "-z").split(b"\0"):
        if not item:
            continue
        fields, raw_name = item.split(b"\t", 1)
        mode, _, stage = fields.decode("ascii").split()
        name = raw_name.decode("utf-8")
        require(name in files and stage == "0" and mode == files[name][0],
                "index mode/type or merge stage differs from base: " + name)
        indexed.add(name)
    require(indexed == files.keys(), "indexed input paths differ from base")
    # Git diff can hide worktree bytes behind filters or assume-unchanged bits.
    # Independently compare the actual regular files with their base blobs;
    # never follow a linked ancestor or normalize bytes into an apparent match.
    directories, bindings = {ROOT}, {}
    pinned = {"buildscript-gradle.lockfile", "settings-gradle.lockfile", "gradle/plugin-provenance-policy.txt"}
    require(pinned <= files.keys(), "base lacks required tool-lock/provenance inputs")
    for name, (mode, kind, oid) in files.items():
        path = ROOT / name
        for parent in reversed(path.parents):
            if parent == ROOT or ROOT in parent.parents:
                if parent not in directories:
                    require(stat.S_ISDIR(parent.lstat().st_mode), "linked or missing source directory: " + name)
                    directories.add(parent)
        info = path.lstat()
        require(kind == "blob" and mode in ("100644", "100755") and stat.S_ISREG(info.st_mode) and
                bool(info.st_mode & 0o111) == (mode == "100755"), "source input type/mode differs: " + name)
        if name in eligible:
            continue
        blob = hashlib.sha1() if len(oid) == 40 else hashlib.sha256()
        blob.update(b"blob " + str(info.st_size).encode("ascii") + b"\0")
        sha = hashlib.sha256()
        with path.open("rb") as stream:
            for data in iter(lambda: stream.read(1024 * 1024), b""):
                blob.update(data)
                sha.update(data)
        require(blob.hexdigest() == oid, "non-project-lock input bytes differ from base: " + name)
        if name in pinned or name.startswith("gradle/") or name in (
                "scripts/prepare-dependency-update.sh", "scripts/classify-dependency-provenance.py",
                "scripts/check-dependency-verification.sh", "scripts/review-dependency-verification.sh"):
            bindings[name] = sha.hexdigest()
    return locks, bindings, len(files) - len(eligible)


def main():
    require(len(sys.argv) == 3, "usage: classify-dependency-provenance.py <base-commit> <source-commit>")
    base, source = sys.argv[1:]
    for value in (base, source):
        require(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value), "an exact commit identity is required")
        require(git("cat-file", "-t", value).strip() == b"commit", "base/source is not an available commit")
    require(git("rev-parse", "HEAD").decode().strip() == source, "source changed during dependency update")
    git("merge-base", "--is-ancestor", base, source)
    files = base_files(base)
    require(files.get(METADATA, ())[:2] == ("100644", "blob"), "base metadata is missing or not a regular blob")
    require(0 < int(git("cat-file", "-s", files[METADATA][2])) <= MAX_METADATA_BYTES,
            "base metadata is empty or oversized")
    before = git("cat-file", "blob", files[METADATA][2])
    path = ROOT / METADATA
    require(stat.S_ISREG(path.lstat().st_mode) and 0 < path.stat().st_size <= MAX_METADATA_BYTES,
            "current metadata is missing, linked, empty or oversized")
    with path.open("rb") as stream:
        after = stream.read(MAX_METADATA_BYTES + 1)
    old, current = metadata(before), metadata(after)
    require(all(current.get(key) == value for key, value in old.items()),
            "dependency update removed verified history or changed an existing SHA-256")
    added = current.keys() - old.keys()
    record = {"baseCommit": base, "baseTree": git("rev-parse", base + "^{tree}").decode().strip(),
              "sourceCommit": source, "sourceTree": git("rev-parse", source + "^{tree}").decode().strip(),
              "baseMetadataSha256": hashlib.sha256(before).hexdigest(),
              "candidateMetadataSha256": hashlib.sha256(after).hexdigest(),
              "artifactCount": len(current), "addedArtifactCount": len(added)}
    if before == after:
        locks, bindings, checked = reuse_inputs(base, files)
        record.update(mode="REUSE", projectLockChanges=locks, pinnedInputSha256=bindings,
                      exactNonProjectLockInputCount=checked,
                      scope="all tracked non-project-lock inputs equal the operator-reviewed base; no untracked inputs",
                      freshRemoteArtifactReview=False)
    else:
        require(added, "nonidentical metadata without added artifacts cannot reuse provenance")
        record.update(mode="REVIEW", scope="new artifacts require the unchanged remote curator; not yet reviewed")
    print("DEPENDENCY-PROVENANCE " + json.dumps(record, sort_keys=True), file=sys.stderr)
    print(record["mode"])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError, ET.ParseError) as error:
        print("FATAL: dependency provenance classification failed: " + str(error), file=sys.stderr)
        sys.exit(1)
