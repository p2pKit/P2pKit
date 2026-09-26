#!/usr/bin/env python3
"""Fixed manual dependency curation; never ordinary admission or qualification.

The canonical controller stays immutable. The maintained full generator changes
only a separate candidate's tracked locks/verification metadata. Raw output is
private; only a returned, separately guarded encrypted export may be uploaded.
Known-closed failed products have diagnostics, never a generated candidate PASS.
No cache, signing, publication, private-key, or initial-recipient bypass exists.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "p2pKit/P2pKit"
WORKFLOW = ".github/workflows/dependency-update-candidate.yml"
OWNER, OWNER_ID = "Apdelrahman1911", "104788132"
SCOPE = "MANUAL_DEPENDENCY_GENERATION_ONLY_V1"
FAILED_SCOPE = "MANUAL_DEPENDENCY_FAILED_PRODUCT_DIAGNOSTICS_V1"
REQUEST_KEYS = {"controller_sha", "controller_tree", "candidate_sha", "candidate_tree", "dependency_base_sha"}
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
NUMBER = re.compile(r"[1-9][0-9]{0,19}\Z")
POLICY_PATH = ".github/test-evidence-recipient.json"
# Independent owner decision, not trust acquired from the mutable candidate.
# Renew/rotate through a separately reviewed owner decision, never via inputs.
POLICY_SHA256 = "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521"
KEY_SHA256 = "5dcb108725ffb2a9c99f4e61e35c3473d34776530effca7385282faf62b86aaf"
FINGERPRINT = "0A996D2BC19518FB50071A95D3FDADA57CFB7E1F"
ENCRYPTION_FINGERPRINT = "4D7CF63A16AFC0BDDC82F3E686D7D3D9A7B44350"
KEY_EXPIRES = 1821484800
JOB_SECONDS, PRODUCT_SECONDS, STOP_SECONDS = 12600, 7200, 120
PREREQUISITES_SECONDS, NATIVE_HEADROOM = 900, 180
FINALIZE_SECONDS, EXPORT_SECONDS, UPLOAD_SECONDS = 300, 120, 1320
FINAL_RESERVE = FINALIZE_SECONDS + EXPORT_SECONDS + UPLOAD_SECONDS
WRITER_RESERVE = PRODUCT_SECONDS + STOP_SECONDS + NATIVE_HEADROOM + FINAL_RESERVE
ENTRY_RESERVE = PREREQUISITES_SECONDS + STOP_SECONDS + NATIVE_HEADROOM + WRITER_RESERVE
MIB = 1024 * 1024
FILE_LIMIT, PATCH_LIMIT, SOURCE_LIMIT, FILE_COUNT = 32 * MIB, 64 * MIB, 128 * MIB, 20000
PUBLIC_FILES = ("generated-dependencies.patch", "generated-dependencies.json")
ENCRYPTED_FILES = ("evidence.tar.gz.gpg", "manifest.json")
MAINTAINED_HELPERS = (
    "gradlew", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties",
    "scripts/prepare-dependency-update.sh", "scripts/check-gradle-wrapper.sh",
    "scripts/check-dependency-verification.sh", "scripts/review-dependency-verification.sh",
    "scripts/validate-gradle-plugin-marker.sh", "scripts/validate-gradle-plugin-metadata.py",
    "scripts/resolve-gradle-variant-artifact.py",
    "gradle/plugin-provenance-policy.txt",
)
NATIVE_OWNER_ENV = ("P2PKIT_AUDIT_JOB_ID", "P2PKIT_AUDIT_OWNERSHIP_CHAIN",
                    "P2PKIT_AUDIT_OWNERSHIP_DOMAINS", "P2PKIT_AUDIT_STATE_DIR", "GRADLE_USER_HOME")
IDENTITY_ENV = (
    "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_REF", "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA",
    "GITHUB_JOB", "GITHUB_ACTOR", "GITHUB_ACTOR_ID", "GITHUB_TRIGGERING_ACTOR", "RUNNER_ENVIRONMENT",
)
TOOL_ENV = ("PATH", "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "DEVELOPER_DIR", "ANDROID_HOME")


class UpdateError(RuntimeError):
    """Only fixed non-secret reason codes may reach the runner log."""


class ClosedProductFailure(UpdateError):
    """Raised only after the actual canonical call and original receipt agree."""

    def __init__(self, code, receipt, receipt_hash):
        super().__init__("FAILED_PRODUCT")
        self.code, self.receipt, self.receipt_hash = code, receipt, receipt_hash


def require(value, code):
    if not value:
        raise UpdateError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode("ascii")


def parsed(raw, limit=FILE_LIMIT):
    require(type(raw) is bytes and 0 < len(raw) <= limit, "JSON_BOUND")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "JSON_DUPLICATE")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: require(False, "JSON_NONFINITE"))
    except (ValueError, UnicodeError, RecursionError):
        raise UpdateError("JSON_FORMAT") from None


def request_data(request, env):
    """Validate supplied DATA against genuine caller environment; no authority object."""
    require(type(request) is dict and set(request) == REQUEST_KEYS and
            all(type(value) is str and SHA.fullmatch(value) for value in request.values()), "REQUEST_FIELDS")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPOSITORY and
            env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            env.get("GITHUB_JOB") == "generate" and env.get("GITHUB_ACTOR") == OWNER and
            env.get("GITHUB_ACTOR_ID") == OWNER_ID and env.get("GITHUB_TRIGGERING_ACTOR") == OWNER, "MANUAL_IDENTITY")
    ref = env.get("GITHUB_REF", "")
    require(type(ref) is str and (ref == "refs/heads/main" or
            re.fullmatch(r"refs/heads/work/release-foundation-[A-Za-z0-9-]+", ref)),
            "CONTROLLER_REF")
    require(env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA") == request["controller_sha"] and
            env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@" + ref, "CONTROLLER_IDENTITY")
    require(all(type(env.get(key)) is str and NUMBER.fullmatch(env[key])
                for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")), "RUN_IDENTITY")
    return {"repository": REPOSITORY, "ref": ref, "runId": env["GITHUB_RUN_ID"],
            "runAttempt": env["GITHUB_RUN_ATTEMPT"], "workflow": WORKFLOW}


def policy_data(raw, now, reserve):
    require(type(raw) is bytes, "OWNER_POLICY_BYTES")
    require(type(now) in (int, float) and math.isfinite(now) and
            type(reserve) is int and 0 <= reserve <= JOB_SECONDS, "POLICY_TIME")
    require(digest(raw) == POLICY_SHA256, "OWNER_POLICY_PIN")
    value = parsed(raw, 96 * 1024)
    require(type(value) is dict and set(value) == {"schema", "repository", "purpose", "retrievalOwner",
            "retentionDays", "notBefore", "expiresAt", "recipient"} and type(value["schema"]) is int and
            value["schema"] == 1 and value["repository"] == REPOSITORY and
            value["purpose"] == "P2PKIT_TEST_TRANSCRIPTS" and value["retrievalOwner"] == OWNER and
            type(value["retentionDays"]) is int and value["retentionDays"] == 14, "OWNER_POLICY_SHAPE")
    require(type(value["notBefore"]) is int and type(value["expiresAt"]) is int and
            value["expiresAt"] - value["notBefore"] == 14 * 86400 and
            value["notBefore"] <= now and now + reserve < value["expiresAt"], "OWNER_POLICY_EXPIRY")
    key = value["recipient"]
    require(type(key) is dict and set(key) == {"publicKey", "fingerprint", "sha256"} and
            type(key["publicKey"]) is str and key["fingerprint"] == FINGERPRINT and key["sha256"] == KEY_SHA256 and
            digest(key["publicKey"].encode("ascii")) == KEY_SHA256, "OWNER_KEY_PIN")
    return value


def delta_data(before, after, *, staged, untracked):
    """Closed tracked-content change policy; metadata is retained separately."""
    require(type(before) is dict and type(after) is dict and set(before) == set(after) and
            not staged and not untracked, "CANDIDATE_ROSTER_CHANGED")
    allowed = {name for name in before if name.endswith("lockfile")} | {"gradle/verification-metadata.xml"}
    changed = []
    for name, old in before.items():
        new = after[name]
        require(old["gitMode"] == new["gitMode"] and old["mode"] == new["mode"] and
                old["gitBlob"] == new["gitBlob"] and old["uid"] == new["uid"], "CANDIDATE_TYPE_OR_MODE_CHANGED")
        if old["sha256"] != new["sha256"]:
            require(name in allowed, "CANDIDATE_NON_GENERATED_CHANGE")
            changed.append(name)
    require(changed and "gradle/verification-metadata.xml" in changed, "NO_VERIFICATION_CANDIDATE")
    return sorted(changed)


def child_environment(env, parent):
    """No wildcard inheritance, credentials, runner command files or user configs."""
    result = {key: env[key] for key in (*IDENTITY_ENV, *TOOL_ENV) if key in env}
    result.update(HOME=str(parent / "home"), TMPDIR=str(parent / "tmp"),
        XDG_CONFIG_HOME=str(parent / "home/config"), XDG_CACHE_HOME=str(parent / "home/cache"),
        GNUPGHOME=str(parent / "home/gnupg"), GH_CONFIG_DIR=str(parent / "home/gh"),
        KONAN_DATA_DIR=str(parent / "konan"), ANDROID_USER_HOME=str(parent / "android-user"),
        PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0", LC_ALL="C", TZ="UTC")
    return result


COMPONENT = r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,199}"
REPOSITORIES = {"https://repo.maven.apache.org/maven2", "https://plugins.gradle.org/m2",
                "https://dl.google.com/dl/android/maven2"}
REVIEW_LINE = re.compile(r"REVIEWED (" + COMPONENT + r"):(" + COMPONENT + r"):(" + COMPONENT + r") (" +
    COMPONENT + r") sha256=([0-9a-f]{64}) signer=([A-Za-z0-9_.@/+-]{1,512}) "
    r"evidence=([A-Za-z0-9+-]{1,80}) repository=(https://[A-Za-z0-9./-]{1,100})\Z")
REVIEW_END = re.compile(r"RESULT: PASS — reviewed ([1-9][0-9]{0,5}) newly admitted artifacts by exact SHA-256 and "
    r"publisher provenance; unsigned Gradle metadata is structurally bound to a trusted implementation JAR\Z")
VERIFICATION_NAMESPACE = "https://schema.gradle.org/dependency-verification"
XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
VERIFICATION_SCHEMA = VERIFICATION_NAMESPACE + " " + VERIFICATION_NAMESPACE + "/dependency-verification-1.4.xsd"


def verification_entries(raw):
    """DATA only: select the maintained reviewer's exact component/artifact/hash keys."""
    require(type(raw) is bytes and 0 < len(raw) <= FILE_LIMIT and
            not re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", raw, re.I), "VERIFICATION_DATA_BOUND")
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError, RecursionError):
        raise UpdateError("VERIFICATION_DATA_XML") from None
    ns = "{" + VERIFICATION_NAMESPACE + "}"
    require(root.tag == ns + "verification-metadata" and root.attrib == {
        "{" + XSI_NAMESPACE + "}schemaLocation": VERIFICATION_SCHEMA}, "VERIFICATION_DATA_ROOT")
    # ElementTree expands the real default namespace. Never strip arbitrary
    # namespaces or silently skip a mixed/unqualified subtree. This is only the
    # maintained SHA-256 structure, not an alternative writer/checker/schema.
    for count, element in enumerate(root.iter(), start=1):
        require(count <= 5 * FILE_COUNT + 5 and type(element.tag) is str and element.tag.startswith(ns),
                "VERIFICATION_ELEMENT_NAMESPACE")
        require(not (element.tail or "").strip(), "VERIFICATION_ELEMENT_TEXT")
    require([item.tag for item in root] == [ns + "configuration", ns + "components"] and
            not (root.text or "").strip(), "VERIFICATION_STRUCTURE")
    configuration, components = root
    require(not configuration.attrib and not components.attrib and not (configuration.text or "").strip() and
            not (components.text or "").strip() and [item.tag for item in configuration] ==
            [ns + "verify-metadata", ns + "verify-signatures"], "VERIFICATION_CONFIGURATION")
    require(all(not item.attrib and len(item) == 0 and item.text == value
                for item, value in zip(configuration, ("true", "false"))), "VERIFICATION_CONFIGURATION")
    entries, coordinates = set(), set()
    for component in components:
        require(component.tag == ns + "component" and set(component.attrib) == {"group", "name", "version"} and
                not (component.text or "").strip(), "VERIFICATION_COMPONENT")
        parts = tuple(component.get(name, "") for name in ("group", "name", "version"))
        require(all(re.fullmatch(COMPONENT, part) for part in parts) and parts not in coordinates and len(component) > 0,
                "VERIFICATION_COMPONENT")
        coordinates.add(parts)
        names = set()
        for artifact in component:
            require(artifact.tag == ns + "artifact" and set(artifact.attrib) == {"name"} and
                    not (artifact.text or "").strip(), "VERIFICATION_ARTIFACT")
            name = artifact.get("name", "")
            require(re.fullmatch(COMPONENT, name) and name not in names and len(artifact) == 1, "VERIFICATION_ARTIFACT")
            names.add(name)
            checksum = artifact[0]
            require(checksum.tag == ns + "sha256" and {"value"} <= set(checksum.attrib) <= {"value", "origin", "reason"} and
                    len(checksum) == 0 and not (checksum.text or "").strip(), "VERIFICATION_CHECKSUM")
            value = checksum.get("value", "")
            require(HASH.fullmatch(value), "VERIFICATION_CHECKSUM")
            entries.add((*parts, name, value))
            require(len(entries) <= FILE_COUNT, "VERIFICATION_ENTRY_BOUND")
    require(entries, "VERIFICATION_ENTRIES_MISSING")
    return entries


def provenance_data(raw, before_xml, after_xml):
    """Extract public fields, never raw logs. A record is NOT publisher-key approval.

    Every record must match a newly admitted XML entry and the maintained
    reviewer's complete terminal roster. Actual signature execution is bound by
    the original successful command receipt, not by these data controls.
    """
    require(type(raw) is bytes and 0 < len(raw) <= 256 * MIB, "PROVENANCE_LOG_BOUND")
    expected = verification_entries(after_xml) - verification_entries(before_xml)
    require(expected, "PROVENANCE_NO_NEW_ENTRIES")
    records, terminal = {}, []
    for line in raw.splitlines():
        if line.startswith(b"REVIEWED "):
            try:
                match = REVIEW_LINE.fullmatch(line.decode("ascii"))
            except UnicodeError:
                raise UpdateError("PROVENANCE_PUBLIC_FIELDS") from None
            require(match is not None, "PROVENANCE_PUBLIC_FIELDS")
            group, name, version, artifact, checksum, signer, evidence, repository = match.groups()
            key = group, name, version, artifact, checksum
            require(key in expected and key not in records and repository in REPOSITORIES, "PROVENANCE_ROSTER")
            if evidence in ("signature-bound-bytes", "sha256-sidecar+signature"):
                require(re.fullmatch(r"[A-F0-9]{40}|[A-F0-9]{64}", signer), "PROVENANCE_SIGNER")
            elif evidence in ("semantic-marker+trusted-implementation-pending", "semantic-module+attested-jar-pending"):
                require(signer == "none", "PROVENANCE_METADATA_SIGNER")
            elif evidence == "github-slsa-provenance":
                require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml"
                                     r"@refs/tags/[A-Za-z0-9._/-]+", signer), "PROVENANCE_WORKFLOW_SIGNER")
            else:
                raise UpdateError("PROVENANCE_METHOD")
            records[key] = {"group": group, "module": name, "version": version, "artifact": artifact,
                "sha256": checksum, "signer": signer, "method": evidence, "repository": repository}
        elif line.startswith("RESULT: PASS — reviewed ".encode("utf-8")):
            try:
                match = REVIEW_END.fullmatch(line.decode("utf-8"))
            except UnicodeError:
                raise UpdateError("PROVENANCE_TERMINAL") from None
            require(match is not None, "PROVENANCE_TERMINAL")
            terminal.append(int(match.group(1)))
    require(set(records) == expected and terminal == [len(expected)], "PROVENANCE_INCOMPLETE")
    return {"sourceLogSha256": digest(raw), "records": [records[key] for key in sorted(records)],
            "publisherKeyAttribution": "INDEPENDENT_REVIEW_REQUIRED"}


@contextlib.contextmanager
def environment(values):
    original = dict(os.environ)
    os.environ.clear()
    os.environ.update(values)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def physical(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "ABSOLUTE_PATH")
    for item in (path, *path.parents):
        require(not item.is_symlink(), "PATH_SYMLINK")
    return path


def read_file(path, limit=FILE_LIMIT):
    path = physical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid() and
                not before.st_mode & 0o022 and 0 <= before.st_size <= limit, "FILE_TYPE_OR_BOUND")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        fields = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_nlink,
                                value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        require(len(raw) == before.st_size and fields(before) == fields(after) == fields(path.lstat()),
                "FILE_CHANGED")
    return raw, {"identity": [before.st_dev, before.st_ino], "mode": stat.S_IMODE(before.st_mode),
                 "uid": before.st_uid, "size": len(raw), "sha256": digest(raw),
                 "mtimeNs": before.st_mtime_ns, "ctimeNs": before.st_ctime_ns}


def write_new(path, raw):
    require(type(raw) is bytes, "WRITE_BYTES")
    path = physical(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        require(stream.write(raw) == len(raw), "WRITE_SHORT")
        stream.flush()
        os.fsync(stream.fileno())
    require(read_file(path, max(FILE_LIMIT, len(raw)))[0] == raw, "WRITE_READBACK")


def module(name, relative):
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def operation():
    require(os.name == "posix" and platform.system() == "Darwin" and platform.machine() == "arm64", "NATIVE_HOST")
    # This fixed manual entry is not nested in another native owner. Do not erase
    # an actual enclosing domain to obtain the public exporter's direct mode.
    require(not any(name in os.environ for name in NATIVE_OWNER_ENV), "UNEXPECTED_ENCLOSING_OWNER")
    parent = physical(os.environ["P2PKIT_DEPENDENCY_OPERATION"])
    temporary = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    info = parent.lstat()
    require(parent.parent == temporary and parent.name.startswith("p2pkit-dependency-update-") and
            stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
            "OPERATION_DIRECTORY")
    allocation = parsed(read_file(parent / "allocation.json", 8192)[0])
    require(set(allocation) == {"schema", "source", "runId", "runAttempt", "startedMonotonicNs", "startedEpochNs"} and
            type(allocation["schema"]) is int and allocation["schema"] == 1 and
            allocation["source"] == os.environ["GITHUB_SHA"] and allocation["runId"] == os.environ["GITHUB_RUN_ID"] and
            allocation["runAttempt"] == os.environ["GITHUB_RUN_ATTEMPT"], "ALLOCATION_IDENTITY")
    for key in ("startedMonotonicNs", "startedEpochNs"):
        require(type(allocation[key]) is int and allocation[key] > 0, "ALLOCATION_TIME")
    return parent, allocation


def budget(allocation, reserve):
    elapsed = (time.monotonic_ns() - allocation["startedMonotonicNs"]) / 1e9
    wall = time.time()
    require(0 <= elapsed and elapsed + reserve < JOB_SECONDS and
            abs(wall - allocation["startedEpochNs"] / 1e9 - elapsed) <= 60, "OPERATION_DEADLINE")
    policy_data(read_file(ROOT / POLICY_PATH, 96 * 1024)[0], wall, reserve)


def source_roster(runner, root):
    raw = runner.git(root, "ls-files", "--stage", "-z")
    result, total = {}, 0
    for row in raw.split(b"\0"):
        if not row:
            continue
        header, path_raw = row.split(b"\t", 1)
        mode, blob, stage = header.decode("ascii").split(" ")
        name = path_raw.decode("utf-8")
        require(mode in ("100644", "100755") and stage == "0" and SHA.fullmatch(blob) and
                name not in result and not name.startswith("/") and ".." not in Path(name).parts and
                len(name.encode("utf-8")) <= 1024 and all(ord(char) >= 32 and ord(char) != 127 for char in name),
                "TRACKED_SOURCE_ROSTER")
        data, info = read_file(root / name)
        require(info["mode"] == (0o755 if mode == "100755" else 0o644), "TRACKED_SOURCE_MODE")
        total += len(data)
        require(len(result) < FILE_COUNT and total <= SOURCE_LIMIT, "TRACKED_SOURCE_BOUND")
        result[name] = {**info, "gitMode": mode, "gitBlob": blob}
    require(result, "EMPTY_SOURCE")
    return result


def clean_source(runner, root, sha, tree):
    current = runner.source_snapshot(root)
    require(current == {"commit": sha, "tree": tree, "status": "", "diffSha256": digest(b"")}, "CLEAN_SOURCE")
    require(runner.git(root, "remote", "get-url", "origin").strip() in
            (b"https://github.com/p2pKit/P2pKit", b"https://github.com/p2pKit/P2pKit.git"), "SOURCE_ORIGIN")
    config = runner.git(root, "config", "--local", "--list").lower()
    require(b"extraheader=" not in config and b"credential." not in config, "PERSISTED_CREDENTIALS")
    return current


def ignored_outputs(runner, root):
    prefixes = [path.relative_to(root).as_posix() + "/" for path in runner.disposable_roots(root)]
    modules = [root, root / "buildSrc", *[path.parent for path in runner.output_roots(root)]]
    prefixes += [(path / suffix).relative_to(root).as_posix() + "/" for path in modules
                 for suffix in (".gradle", ".kotlin")]
    rows = []
    for raw in runner.git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z").split(b"\0"):
        if raw:
            name = raw.decode("utf-8")
            require(any(name.startswith(prefix) for prefix in prefixes), "UNEXPECTED_IGNORED_OUTPUT")
            info = (root / name).lstat()
            rows.append({"path": name, "mode": info.st_mode, "bytes": info.st_size})
            require(len(rows) <= 250000, "OUTPUT_ROSTER_BOUND")
    return rows


def command_return_data(code, receipt, context, invocation, purpose, argv):
    """Closed-result DATA checks, not proof of an executed/native owner by itself.

    Only owned_command calls this with the genuine execute return and original
    receipt. Canonical errors include timeouts, stream completion, source,
    signal/lease restoration and handle-close failures before that return.
    Reserve125, conventional timeout124 and signal-style codes are deliberately
    ineligible even if supplied JSON claims otherwise.
    """
    require(type(code) is int and 0 <= code <= 123 and type(receipt) is dict, "ORIGINAL_COMMAND_FAILED")
    require(type(receipt.get("schema")) is int and receipt["schema"] == 1 and
            receipt.get("id") == invocation and receipt.get("jobId") == context["id"] and
            receipt.get("kind") == "command" and receipt.get("purpose") == purpose and
            receipt.get("requestedArgv") == argv and receipt.get("sourceBefore") == receipt.get("sourceAfter") ==
            context["source"] and receipt.get("sourceUnchanged") is True and
            all(type(receipt.get(name)) is int for name in ("productExitCode", "stopExitCode", "finalExitCode")) and
            receipt["productExitCode"] == receipt["finalExitCode"] == code and receipt["stopExitCode"] == 0 and
            receipt.get("ownedSurvivors") == [] and receipt.get("errors") == [] and
            type(receipt.get("ownership")) is dict and receipt["ownership"].get("discoveryErrors") == [] and
            not receipt.get("cancelledSignals") and not receipt.get("cancelRequested"), "ORIGINAL_COMMAND_FAILED")
    return "SUCCESS" if code == 0 else "FAILED_PRODUCT"


def owned_command(runner, parent, context, purpose, argv, seconds):
    invocation = uuid.uuid4().hex
    args = argparse.Namespace(cwd=str(ROOT), wrapper=str(ROOT / "gradlew"), id=invocation,
        purpose=purpose, kind="command", argv=argv, timeout=seconds, stop_timeout=STOP_SECONDS, receipt=None)
    # The state selector belongs to execute's controller call only. execute
    # creates complete original owner markers for its children and retires them
    # before return. The separate manual public-key API receives no partial or
    # fabricated native ownership domain.
    with environment({**os.environ, "P2PKIT_AUDIT_STATE_DIR": str(parent / "state")}):
        code = runner.execute(args)
    raw = read_file(parent / "state/evidence" / invocation / "receipt.json", 4 * MIB)[0]
    receipt = parsed(raw)
    result = command_return_data(code, receipt, context, invocation, purpose, argv)
    if result == "FAILED_PRODUCT":
        raise ClosedProductFailure(code, receipt, digest(raw))
    return receipt, digest(raw)


def prerequisites():
    """Only invoked as the fixed child inside the canonical native owner."""
    require(platform.system() == "Darwin" and platform.machine() == "arm64" and
            os.environ.get("P2PKIT_AUDIT_STATE_DIR"), "PREREQUISITE_OWNER")
    for name in ("git", "gpg", "gpgconf", "gh", "curl", "awk", "comm", "sort", "shasum", "xcodebuild", "xcrun"):
        require(shutil.which(name) is not None, "MISSING_INSTALLED_TOOL")
    require(os.environ.get("DEVELOPER_DIR") == "/Applications/Xcode_26.5.app/Contents/Developer", "XCODE_SELECTION")
    queries = {"java17": [os.environ["JAVA_HOME"] + "/bin/java", "-version"],
               "java21": [os.environ["P2PKIT_AUDIT_JDK21"] + "/bin/java", "-version"],
               "xcode": ["xcodebuild", "-version"],
               "sdk": ["xcrun", "--show-sdk-version", "--sdk", "iphonesimulator"]}
    results = {}
    for name, argv in queries.items():
        process = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=45, check=False)
        require(process.returncode == 0 and len(process.stdout) + len(process.stderr) <= 65536, "TOOL_QUERY_FAILED")
        results[name] = {"argv": argv, "stdout": process.stdout.decode("utf-8"), "stderr": process.stderr.decode("utf-8")}
    for name, major in (("java17", "17"), ("java21", "21")):
        require('version "' + major + "." in results[name]["stdout"] + results[name]["stderr"], "JAVA_SELECTION")
    require(results["xcode"]["stdout"].splitlines()[0] == "Xcode 26.5", "XCODE_VERSION")
    sdk = Path(os.environ["ANDROID_HOME"]).resolve(strict=True)
    missing = [name for name in ("android-36", "android-37.0") if not (sdk / "platforms" / name / "source.properties").exists()]
    if missing:
        manager = (sdk / "cmdline-tools/latest/bin/sdkmanager").resolve(strict=True)
        require(manager.is_file() and os.access(manager, os.X_OK), "SDK_MANAGER_MISSING")
        code = subprocess.call([str(manager), "--sdk_root=" + str(sdk),
                                *["platforms;" + name for name in missing]], stdin=subprocess.DEVNULL, timeout=600)
        require(code == 0, "SDK_INSTALL_FAILED")
    for name, api in (("android-36", "36"), ("android-37.0", "37.0")):
        raw = (sdk / "platforms" / name / "source.properties").read_bytes()
        require(len(raw) <= 65536 and re.search(r"^AndroidVersion\.ApiLevel\s*=\s*" + re.escape(api) + r"\s*$",
                                               raw.decode("utf-8"), re.M), "SDK_METADATA")
        results[name] = {"sha256": digest(raw), "metadata": raw.decode("utf-8"), "installedByThisInvocation": name in missing}
    print(encoded(results).decode("ascii"), end="")  # Captured privately by the original native command.


def generate():
    parent, allocation = operation()
    request = parsed(os.environ["P2PKIT_MAINTENANCE_REQUEST"].encode("utf-8"), 8192)
    github = request_data(request, os.environ)
    budget(allocation, ENTRY_RESERVE)
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
    candidate = physical(workspace / "candidate")
    require(ROOT == workspace / "controller" and not parent.is_relative_to(workspace), "CHECKOUT_TOPOLOGY")
    for name in ("home", "tmp", "konan", "android-user", "crypto", "outputs"):
        (parent / name).mkdir(mode=0o700)
    for name in ("config", "cache", "gnupg", "gh"):
        (parent / "home" / name).mkdir(mode=0o700)
    safe_environment = child_environment(os.environ, parent)
    output_file = physical(os.environ["GITHUB_OUTPUT"])
    with environment(safe_environment):
        runner = module("dependency_update_executor", "scripts/run-audit-command.py")
        exporter = module("hosted_evidence", "scripts/hosted_evidence.py")
        # Includes initialization diagnostics; no traceback or product stream escapes.
        with (parent / "controller.stdout").open("x", encoding="utf-8") as out, \
                (parent / "controller.stderr").open("x", encoding="utf-8") as err, \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            controller_source = clean_source(runner, ROOT, request["controller_sha"], request["controller_tree"])
            candidate_source = clean_source(runner, candidate, request["candidate_sha"], request["candidate_tree"])
            main = runner.git(ROOT, "rev-parse", "refs/remotes/origin/main").decode("ascii").strip()
            require(SHA.fullmatch(main), "MAIN_REFERENCE")
            for source in (request["controller_sha"], request["candidate_sha"], request["dependency_base_sha"]):
                runner.git(ROOT, "merge-base", "--is-ancestor", main, source)
            runner.git(candidate, "merge-base", "--is-ancestor", request["dependency_base_sha"], request["candidate_sha"])
            before = source_roster(runner, candidate)
            controller_roster = source_roster(runner, ROOT)
            require(not ignored_outputs(runner, candidate) and not ignored_outputs(runner, ROOT), "FRESH_CHECKOUT_OUTPUTS")
            for name in MAINTAINED_HELPERS:
                require(before[name]["sha256"] == controller_roster[name]["sha256"], "MAINTAINED_GENERATOR_CHANGED")
            for name in before:
                if name.endswith("lockfile") or name == "gradle/verification-metadata.xml":
                    require(digest(runner.git(candidate, "show", request["dependency_base_sha"] + ":" + name)) ==
                            before[name]["sha256"], "DEPENDENCY_BASE_ALREADY_CHANGED")
            policy_raw = read_file(ROOT / POLICY_PATH, 96 * 1024)[0]
            policy = policy_data(policy_raw, time.time(), ENTRY_RESERVE)
            key_path = parent / "recipient-public.asc"
            write_new(key_path, policy["recipient"]["publicKey"].encode("ascii"))
            recipient = exporter.validate_recipient(key_path, FINGERPRINT, parent / "crypto")
            require(recipient.fingerprint == FINGERPRINT and recipient.encryption_fingerprint == ENCRYPTION_FINGERPRINT and
                    recipient.key_sha256 == KEY_SHA256 and recipient.expires_at == KEY_EXPIRES, "VALIDATED_PUBLIC_RECIPIENT")
            # No SDK or dependency acquisition precedes that actual public validation.
            runner.initialize(argparse.Namespace(root=str(ROOT), state=str(parent / "state"),
                              expected_commit=request["controller_sha"], host="macos-arm64"))
            state, context = runner.context_at(str(parent / "state"))
            evidence = state / "evidence"
            records = evidence / "maintenance"
            records.mkdir(mode=0o700)
            write_new(records / "request.json", encoded({"scope": SCOPE, "request": request, "github": github,
                "mainCommit": main, "allocation": allocation, "recipientPolicySha256": POLICY_SHA256,
                "candidateBefore": candidate_source, "controllerBefore": controller_source}))
            write_new(records / "controller-inputs.json", encoded(controller_roster))
            write_new(records / "candidate-inputs-before.json", encoded(before))
            write_new(records / "canonical-context.json", read_file(state / "context.json")[0])
            write_new(records / "gradle-resource-policy.properties", read_file(state / "gradle-home/gradle.properties")[0])
            write_new(records / "recipient-policy.json", policy_raw)
            failed = None
            try:
                budget(allocation, ENTRY_RESERVE)
                prerequisites_receipt, prerequisites_hash = owned_command(runner, parent, context, "dependency-maintenance-prerequisites",
                    [str(Path(sys.executable).resolve()), "-I", "-B", "-S", str(ROOT / "scripts/run-hosted-dependency-update.py"),
                     "_prerequisites"], PREREQUISITES_SECONDS)
                budget(allocation, WRITER_RESERVE)
                receipt, receipt_hash = owned_command(runner, parent, context, "dependency-maintenance-generator",
                    [str(candidate / "scripts/prepare-dependency-update.sh"), request["dependency_base_sha"]], PRODUCT_SECONDS)
                budget(allocation, FINAL_RESERVE)
                require(runner.git(candidate, "rev-parse", "HEAD").decode("ascii").strip() == request["candidate_sha"] and
                        runner.git(candidate, "rev-parse", "HEAD^{tree}").decode("ascii").strip() == request["candidate_tree"],
                        "CANDIDATE_REVISION_CHANGED")
                after = source_roster(runner, candidate)
                changed = delta_data(before, after, staged=runner.git(candidate, "diff", "--cached", "--binary"),
                                     untracked=runner.git(candidate, "ls-files", "--others", "--exclude-standard", "-z"))
                generated_outputs = ignored_outputs(runner, candidate)
                require(source_roster(runner, ROOT) == controller_roster and
                        clean_source(runner, ROOT, request["controller_sha"], request["controller_tree"]) == controller_source,
                        "CONTROLLER_CHANGED")
                patch = runner.git(candidate, "diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", "HEAD")
                require(0 < len(patch) <= PATCH_LIMIT, "PATCH_BOUND")
                runner.git(candidate, "diff", "--check")
                provenance = provenance_data(
                    read_file(evidence / receipt["id"] / "product.stdout.log", 256 * MIB)[0],
                    runner.git(candidate, "show", request["dependency_base_sha"] + ":gradle/verification-metadata.xml"),
                    read_file(candidate / "gradle/verification-metadata.xml")[0])
                write_new(records / "candidate-inputs-after.json", encoded(after))
                write_new(records / "ignored-output-roster.json", encoded(generated_outputs))
                summary = {"schema": 1, "scope": SCOPE, "github": github, "request": request, "mainCommit": main,
                    "patch": {"name": PUBLIC_FILES[0], "sha256": digest(patch), "bytes": len(patch)}, "changedPaths": changed,
                    "candidateBeforeSha256": digest(encoded(before)), "candidateAfterSha256": digest(encoded(after)),
                    "controllerInputsSha256": digest(encoded(controller_roster)), "prerequisitesReceiptSha256": prerequisites_hash,
                    "generatorReceiptSha256": receipt_hash, "recipientPolicySha256": POLICY_SHA256,
                    "recipientFingerprint": FINGERPRINT, "recipientPublicKeySha256": KEY_SHA256,
                    "retentionDays": 14, "ordinaryQualification": "NOT_PERFORMED", "publisherIdentityReview": "REQUIRED",
                    "provenance": provenance, "originalLogs": "ENCRYPTED_ONLY",
                    "remoteReviewBuffers": "REMOVED_BY_MAINTAINED_REVIEWER"}
                write_new(records / "generated-summary.json", encoded(summary))
                write_new(records / "generated-dependencies.patch", patch)
            except ClosedProductFailure as original:
                # Only an actual nonzero product with successful stop/native/
                # stream/receipt closure reaches this branch. No generic failure,
                # timeout, UNKNOWN, cancellation or partially returned scope can.
                failed = original
                budget(allocation, FINAL_RESERVE)
                require(source_roster(runner, ROOT) == controller_roster and
                        clean_source(runner, ROOT, request["controller_sha"], request["controller_tree"]) == controller_source,
                        "FAILED_CONTROLLER_CHANGED")
                write_new(records / "failed-product.json", encoded({"schema": 1, "scope": FAILED_SCOPE,
                    "request": request, "github": github, "result": "FAILED_PRODUCT", "productExitCode": failed.code,
                    "purpose": failed.receipt["purpose"], "receiptSha256": failed.receipt_hash,
                    "candidateAcceptance": "NOT_ACCEPTED", "policySha256": POLICY_SHA256}))
            for stream in (out, err):
                stream.flush()
                os.fsync(stream.fileno())
        # Both capture files and all real command streams/scopes are now known closed.
        for name in ("controller.stdout", "controller.stderr"):
            write_new(records / name, read_file(parent / name, 256 * MIB)[0])
        budget(allocation, EXPORT_SECONDS + UPLOAD_SECONDS)
        encrypted_group = "failed-encrypted" if failed is not None else "encrypted"
        encrypted = parent / "outputs" / encrypted_group
        manifest = exporter.export_encrypted(evidence, encrypted, recipient,
            source_commit=request["controller_sha"], source_tree=request["controller_tree"],
            run_id=github["runId"], run_attempt=github["runAttempt"], timeout_seconds=EXPORT_SECONDS)
        # Only after SUCCESSFUL exporter return; cleanup failure cannot reach here.
        require(manifest == parsed(read_file(encrypted / "manifest.json", MIB)[0]), "EXPORT_MANIFEST_CHANGED")
        budget(allocation, UPLOAD_SECONDS)
        if failed is None:
            public = parent / "outputs/public"
            public.mkdir(mode=0o700)
            write_new(public / PUBLIC_FILES[0], patch)
            summary["encryptedEvidence"] = {"manifestSha256": digest(encoded(manifest)),
                "ciphertextSha256": manifest["artifact"]["sha256"], "bytes": manifest["artifact"]["size"]}
            write_new(public / PUBLIC_FILES[1], encoded(summary))
        else:
            require(set(path.name for path in (parent / "outputs").iterdir()) == {encrypted_group} and
                    not os.path.lexists(parent / "generator-success.json"), "FAILED_OUTPUT_NOT_EXCLUSIVE")
        files = {}
        groups = (("public", PUBLIC_FILES), ("encrypted", ENCRYPTED_FILES)) if failed is None else (
            (encrypted_group, ENCRYPTED_FILES),)
        for group, names in groups:
            require(set(path.name for path in (parent / "outputs" / group).iterdir()) == set(names), "OUTPUT_ROSTER")
            for name in names:
                raw, info = read_file(parent / "outputs" / group / name, 576 * MIB)
                files[group + "/" + name] = info
        returned = {"schema": 1, "scope": SCOPE if failed is None else FAILED_SCOPE,
            "request": request, "github": github, "files": files,
            "policySha256": POLICY_SHA256, "exportManifestSha256": digest(encoded(manifest)),
            "producerReturn": "SUCCESS_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN" if failed is None else
                              "FAILED_PRODUCT_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN"}
        if failed is not None:
            returned.update(productExitCode=failed.code, purpose=failed.receipt["purpose"], receiptSha256=failed.receipt_hash)
        returned_raw = encoded(returned)
        write_new(parent / ("generator-success.json" if failed is None else "generator-failed-product.json"), returned_raw)
    # Later Steps require the corresponding ACTUAL generator outcome as well as
    # this original export-return hash. Failed products never emit successSha256.
    with output_file.open("a", encoding="ascii") as stream:
        stream.write(("successSha256=" if failed is None else "failedProductSha256=") + digest(returned_raw) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    if failed is not None:
        print("RESULT: FAIL — FAILED_PRODUCT; " + failed.receipt["purpose"] + "; exit=" + str(failed.code) +
              "; encrypted diagnostics only; no candidate acceptance or retry", file=sys.stderr)
        return failed.code
    return 0


def guard_upload(*, after=False):
    parent, allocation = operation()
    require(os.environ.get("P2PKIT_DEPENDENCY_GENERATOR_OUTCOME") == "success", "GENERATOR_STEP_NOT_SUCCESSFUL")
    expected = os.environ.get("P2PKIT_DEPENDENCY_SUCCESS_SHA256", "")
    require(HASH.fullmatch(expected), "SUCCESS_HASH")
    raw = read_file(parent / "generator-success.json", MIB)[0]
    require(digest(raw) == expected, "SUCCESS_RECORD_CHANGED")
    success = parsed(raw)
    github = request_data(success["request"], os.environ)
    require(success["schema"] == 1 and success["scope"] == SCOPE and success["github"] == github and
            success["policySha256"] == POLICY_SHA256 and success["producerReturn"] ==
            "SUCCESS_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN", "SUCCESS_BINDING")
    budget(allocation, 0 if after else UPLOAD_SECONDS)
    with environment(child_environment(os.environ, parent)):
        runner = module("dependency_update_executor", "scripts/run-audit-command.py")
        clean_source(runner, ROOT, success["request"]["controller_sha"], success["request"]["controller_tree"])
    expected_names = {"public/" + name for name in PUBLIC_FILES} | {"encrypted/" + name for name in ENCRYPTED_FILES}
    require(set(success["files"]) == expected_names, "SUCCESS_FILE_ROSTER")
    for group, names in (("public", PUBLIC_FILES), ("encrypted", ENCRYPTED_FILES)):
        require(set(path.name for path in (parent / "outputs" / group).iterdir()) == set(names), "UPLOAD_FILE_ROSTER")
        for name in names:
            require(read_file(parent / "outputs" / group / name, 576 * MIB)[1] == success["files"][group + "/" + name],
                    "UPLOAD_BYTES_CHANGED")
    if after:
        for group in ("PUBLIC", "ENCRYPTED"):
            require(os.environ.get("P2PKIT_" + group + "_OUTCOME") == "success" and
                    NUMBER.fullmatch(os.environ.get("P2PKIT_" + group + "_ARTIFACT_ID", "")) and
                    HASH.fullmatch(os.environ.get("P2PKIT_" + group + "_ARTIFACT_DIGEST", "")), "UPLOAD_RETURN")
        print("RESULT: PASS — manual dependency candidate delivered; independent publisher/source review still required")
    else:
        print("RESULT: PASS — original manual export returned; exact public and encrypted objects admitted for upload")


def failed_return_data(value, env):
    """Validate failure-diagnostic DATA; never turn it into candidate success."""
    require(env.get("P2PKIT_DEPENDENCY_GENERATOR_OUTCOME") == "failure" and
            not env.get("P2PKIT_DEPENDENCY_SUCCESS_SHA256"), "FAILED_GENERATOR_STEP_REQUIRED")
    require(type(value) is dict and set(value) == {"schema", "scope", "request", "github", "files", "policySha256",
            "exportManifestSha256", "producerReturn", "productExitCode", "purpose", "receiptSha256"} and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == FAILED_SCOPE and
            value["github"] == request_data(value["request"], env) and value["policySha256"] == POLICY_SHA256 and
            value["producerReturn"] == "FAILED_PRODUCT_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN" and
            type(value["productExitCode"]) is int and 1 <= value["productExitCode"] <= 123 and
            value["purpose"] in ("dependency-maintenance-prerequisites", "dependency-maintenance-generator") and
            all(type(value[name]) is str and HASH.fullmatch(value[name])
                for name in ("exportManifestSha256", "receiptSha256")) and type(value["files"]) is dict and
            set(value["files"]) == {"failed-encrypted/" + name for name in ENCRYPTED_FILES}, "FAILED_RETURN_BINDING")
    return value


def guard_failed_upload(*, after=False):
    parent, allocation = operation()
    expected = os.environ.get("P2PKIT_DEPENDENCY_FAILED_SHA256", "")
    require(HASH.fullmatch(expected), "FAILED_RETURN_HASH")
    raw = read_file(parent / "generator-failed-product.json", MIB)[0]
    require(digest(raw) == expected, "FAILED_RETURN_CHANGED")
    failed = failed_return_data(parsed(raw), os.environ)
    budget(allocation, 0 if after else UPLOAD_SECONDS)
    with environment(child_environment(os.environ, parent)):
        runner = module("dependency_update_executor", "scripts/run-audit-command.py")
        clean_source(runner, ROOT, failed["request"]["controller_sha"], failed["request"]["controller_tree"])
    require(not os.path.lexists(parent / "generator-success.json") and
            set(path.name for path in (parent / "outputs").iterdir()) == {"failed-encrypted"}, "FAILED_OUTPUT_NOT_EXCLUSIVE")
    encrypted = parent / "outputs/failed-encrypted"
    require(set(path.name for path in encrypted.iterdir()) == set(ENCRYPTED_FILES), "FAILED_FILE_ROSTER")
    for name in ENCRYPTED_FILES:
        require(read_file(encrypted / name, 576 * MIB)[1] == failed["files"]["failed-encrypted/" + name],
                "FAILED_UPLOAD_BYTES_CHANGED")
    require(digest(read_file(encrypted / "manifest.json", MIB)[0]) == failed["exportManifestSha256"],
            "FAILED_MANIFEST_CHANGED")
    if after:
        require(os.environ.get("P2PKIT_FAILED_ENCRYPTED_OUTCOME") == "success" and
                NUMBER.fullmatch(os.environ.get("P2PKIT_FAILED_ENCRYPTED_ARTIFACT_ID", "")) and
                HASH.fullmatch(os.environ.get("P2PKIT_FAILED_ENCRYPTED_ARTIFACT_DIGEST", "")), "FAILED_UPLOAD_RETURN")
        print("DIAGNOSTICS: encrypted failed-product originals delivered; generator and job remain FAILED")
    else:
        print("DIAGNOSTICS: exact failed-product ciphertext admitted; no generated candidate or acceptance")


def main():
    os.umask(0o077)
    try:
        require(len(sys.argv) == 2 and sys.argv[1] in ("generate", "before-upload", "after-upload", "_prerequisites",
                                                    "before-failed-upload", "after-failed-upload"),
                "FIXED_COMMAND")
        if sys.argv[1] == "generate":
            return generate()
        elif sys.argv[1] == "_prerequisites":
            prerequisites()
        elif sys.argv[1] in ("before-failed-upload", "after-failed-upload"):
            guard_failed_upload(after=sys.argv[1] == "after-failed-upload")
        else:
            guard_upload(after=sys.argv[1] == "after-upload")
        return 0
    except BaseException as error:
        # No tracebacks, private paths, raw child output or arbitrary exception text.
        reason = str(error) if type(error) is UpdateError and re.fullmatch(r"[A-Z0-9_]{1,80}", str(error)) else "PRIVATE_FAILURE"
        print("RESULT: FAIL — " + reason + "; preserve private runner originals; no retry or partial acceptance", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
