#!/usr/bin/env python3
"""Genuine hosted Windows #141 method-preimage witness; never a full library gate.

The ordinary immutable leaf owns every Gradle invocation. This controller owns
only fresh disposable source copies, bridges their distinct ownership domains,
assesses the original red/green evidence, and seals a nonprivate public allowlist.
There is no local-host impersonation, arbitrary command input or publishing path.
"""
from __future__ import annotations

import argparse
import ast
import ctypes
from datetime import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import signal
import stat
import struct
import sys
import tarfile
import time
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import audit_processes as processes


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


audit = module("windows_control_audit", "run-audit-command.py")
receipt_check = module("windows_control_receipt", "check-audit-receipt.py")
require = audit.require
digest = audit.digest
new_json = audit.write_new_json
GIB = 1024 ** 3
OPERATION = "windows-directory-fsync-control"
JOB = "windows-directory-fsync-control"
REPOSITORY = "p2pKit/P2pKit"
WORKFLOW = ".github/workflows/desktop-cross-host.yml"
SOURCE = "library/p2p-core/src/jvmMain/kotlin/dev/p2pkit/core/transfer/FileTransferDestinationJvm.kt"
TEST_SOURCE = "library/p2p-core/src/jvmTest/kotlin/dev/p2pkit/core/transfer/FileTransferJvmTest.kt"
OBSERVER = "gradle/windows-directory-control.init.gradle"
BINDING_FIXTURE = "scripts/tests/fixtures/windows-directory-binding"
BINDING_REPORT = "external/fixtures/directory-binding/build/reports/windows-directory-binding/result.json"
BINDING_CASES = {
    **dict.fromkeys(("root_missing", "root_one_key", "root_two_keys", "root_empty", "root_empty_request",
                    "root_bad_hash", "root_nonstring"), "Missing Windows directory-control request binding"),
    "authority_wrong_root": "Windows directory-control authority root differs from its binding",
    "parentless_buildsrc": "Windows directory-control authority root differs from its binding",
    "foreign_child": "Unexpected included build in Windows directory control",
    "wrong_parent": "Windows directory-control authority root differs from its binding",
    "nested_child": "Windows directory-control authority must be the direct root parent",
    **dict.fromkeys(("child_one_key", "child_two_keys", "child_empty", "child_conflict_root",
                    "child_conflict_request", "child_conflict_hash"),
                   "Conflicting or partial child Windows directory-control binding"),
    **dict.fromkeys(("changed_request_root", "changed_request_child", "child_copy_changed_request"),
                   "Windows control request changed"),
    **dict.fromkeys(("request_wrong_schema", "request_wrong_root", "request_bad_nonce"),
                   "Wrong Windows directory-control request"),
}
CLASS = "dev.p2pkit.core.transfer.FileTransferJvmTest"
METHOD = "durableDestinationPublishesOnlyAfterCommitAndCommitIsIdempotent"
SELECTOR = CLASS + "." + METHOD
# KotlinJvmTest decorates report display labels, not canonical listener names.
JUNIT_SUITE = CLASS.rsplit(".", 1)[-1] + "[jvm]"
JUNIT_CASE = METHOD + "[jvm]"
TASK = ":p2p-core:jvmTest"
TASK_POLICY_MESSAGE = "Extra task, excluded task or dry run in Windows directory control"
TASK_POLICY_INPUTS = {
    "root_exact": {"requestedTasks": [TASK, "--tests", SELECTOR], "accepted": True},
    "buildsrc_empty": {"requestedTasks": [], "buildSrc": True, "accepted": True},
    "buildsrc_internal": {"requestedTasks": ["build"], "buildSrc": True, "accepted": True},
    "root_no_tasks": {"requestedTasks": []},
    "root_task_only": {"requestedTasks": [TASK]},
    "root_no_switch": {"requestedTasks": [TASK, SELECTOR]},
    "root_no_selector": {"requestedTasks": [TASK, "--tests"]},
    "root_other_selector": {"requestedTasks": [TASK, "--tests", "other.Test.method"]},
    "root_class_glob": {"requestedTasks": [TASK, "--tests", CLASS + ".*"]},
    "root_wildcard": {"requestedTasks": [TASK, "--tests", "*"]},
    "root_equals_switch": {"requestedTasks": [TASK, "--tests=" + SELECTOR]},
    "root_duplicate_switch": {"requestedTasks": [TASK, "--tests", "--tests", SELECTOR]},
    "root_repeated_filter": {"requestedTasks": [TASK, "--tests", SELECTOR, "--tests", SELECTOR]},
    "root_abbreviation": {"requestedTasks": [":p2p-core:jT", "--tests", SELECTOR]},
    "root_extra_task": {"requestedTasks": [TASK, "--tests", SELECTOR, ":p2p-core:jvmJar"]},
    "root_extra_task_option": {"requestedTasks": [TASK, "--tests", SELECTOR, "--fail-fast"]},
    "root_reordered": {"requestedTasks": ["--tests", SELECTOR, TASK]},
    "root_dry_run": {"requestedTasks": [TASK, "--tests", SELECTOR], "dryRun": True},
    "root_excluded": {"requestedTasks": [TASK, "--tests", SELECTOR], "excludedTasks": [":p2p-core:compileKotlinJvm"]},
    "buildsrc_dry_run": {"requestedTasks": [], "buildSrc": True, "dryRun": True},
    "buildsrc_excluded": {"requestedTasks": [], "buildSrc": True, "excludedTasks": [":compileJava"]},
}
TEMPORARY_POLICY_MESSAGE = "Test temporary directory is not fresh/physical"
FILE_KEY_MESSAGE = "Invalid optional Test temporary file-key diagnostic"
TEMPORARY_POLICY_INPUTS = {
    "null_key": {"accepted": True},
    "non_null_key": {"fileKey": "MODELED_KEY", "accepted": True},
    "not_directory": {"directory": False},
    "other": {"other": True},
    "symbolic_link": {"symbolicLink": True},
    "nonempty": {"hasEntries": True},
    "empty_key": {"fileKey": "", "message": FILE_KEY_MESSAGE},
    "unbounded_key": {"fileKey": "x" * 1025, "message": FILE_KEY_MESSAGE},
}
FIX = "1df5c0670c90b579de767b6ff568a4beac97ad05"
PRE_FIX = "ba208af23b9ce8e8f6efe1e3f63b0b81b38a4c7a"
CURRENT_METHOD = b"    private fun syncParentDirectory() {\n        if (isWindows(operatingSystemName)) return\n        syncDirectory(parent)\n    }"
OLD_METHOD = b"    private fun syncParentDirectory() {\n        FileChannel.open(parent.toPath(), StandardOpenOption.READ).use { it.force(true) }\n    }"
# Independent reviewed preimages. A future source delta needs a new review, not
# an automatically refreshed expected hash derived from the candidate itself.
CURRENT_SHA = "bf4a51881038c3a8fd58c06d71bb6b1ddf0611d2147fb8e5465801be981f9ba8"
HISTORICAL_SHA = "8c9590680bd9ce7233a4a57ab0416fb6a6674ffcedc829572b4e95a83cab3663"
PREIMAGE_SHA = "3db1aa7770a8028d9fa649c42dc18115afa9ee2883294cc08d3d5afe58f5de7b"
TEST_SHA = "70eeae91dff285e9d59a18c4d1de01d3bb492a6ade2ff8d2333a5c72a8b10401"
TEST_BLOCK_SHA = "9e774bb03e5f80733a26dc6de7964c484234550f10445dd7a2aa4f5cd6ebf233"
CORE_TASKS = {":p2p-core:" + name for name in (
    "kmpPartiallyResolvedDependenciesChecker", "checkKotlinGradlePluginConfigurationErrors", "generateBuildInfo", "generateWireGoldens",
    "compileKotlinJvm", "compileJvmMainJava", "jvmProcessResources", "processJvmMainResources",
    "jvmMainClasses", "jvmJar", "compileTestKotlinJvm", "compileJvmTestJava",
    "jvmTestProcessResources", "processJvmTestResources", "jvmTestClasses", "jvmTest",
)}
REQUIRED_TASKS = {":p2p-core:generateBuildInfo", ":p2p-core:compileKotlinJvm",
                  ":p2p-core:compileTestKotlinJvm", TASK}
LEAF_FILES = {"start.json", "receipt.json", "report-manifest.json", "product.stdout.log",
              "product.stderr.log", "stop.stdout.log", "stop.stderr.log"}
HEX32 = r"[0-9a-f]{32}"
MAX_FILE = 32 * 1024 ** 2
MAX_FILES = 25000
MAX_BYTES = 256 * 1024 ** 2
NATIVE_TEMP_FILES = {"native-temporary-before.json": "before", "native-temporary-after.json": "after"}
NATIVE_TEMP_ENTRIES = 128
NATIVE_TEMP_BYTES = 512 * 1024
NATIVE_TEMP_STEPS = {"path", "root-before", "root-recheck", "entries", "entry-limit", "entry-name",
                     "entry-metadata", "root-after"}
NATIVE_DIRECTORY_POLICY_MARKER = (
    "test_retained_directory_native_acl_precedes_payload_and_accepts_inherited_file/"
    "native-directory-policy/nested/before/marker.txt")
NATIVE_DIRECTORY_POLICY_BYTES = b"SYNTHETIC-NATIVE-ACL-CONTROL\n"
WORKER_NAME = r"gradle-worker-classpath[0-9]{1,20}txt"
WORKER_MAIN = "worker.org.gradle.process.internal.worker.GradleWorkerMain"
WORKER_BYTES = 256 * 1024
WORKER_FILES = {"worker-classpath.json", "worker-classpath-retention.json", "worker-classpath.args"}
WORKER_CAPTURE_REASONS = {"CAPTURE_FAILED", "BINDING_CHANGED", "FILE_SELECTION_FAILED",
                          "FILE_CAPTURE_FAILED", "CONTENT_MISMATCH"}
WORKER_RETENTION_REASONS = {"CAPTURE_INVALID", "CAPTURE_MISSING", "ADMISSION_MISSING", "CAPTURE_REFUSED",
    "LEAF_UNFINALIZED", "EXECUTION_INVALID", "SNAPSHOT_INVALID", "EXPANSION_MISMATCH", "LAUNCH_MISMATCH",
    "ORIGINAL_INVALID", "BOOTSTRAP_INVALID", "PUBLIC_COPY_FAILED"}
WORKER_POLICY_CASES = {
    "render_plain": ("-cp\r\nC:\\\\m\\\\gradle-worker.jar;C:\\\\m\\\\classes\r\n", None),
    "render_space_hash": ('-cp\r\n"C:\\\\m\\\\gradle-worker.jar;C:\\\\m\\\\space #dir"\r\n', None),
    "native_encoding_precedence": ("windows-1252", None),
    "native_encoding_fallback": ("UTF-8", None),
    "native_encoding_default": ("US-ASCII", None),
    "render_full_utf16_refused": (None, "Unsupported worker encoding"),
    "render_lf_refused": (None, "Unsupported worker expansion"),
    "render_empty_refused": (None, "Unsupported worker expansion"),
    **dict.fromkeys(("render_nonascii_refused", "path_semicolon", "path_quote", "path_apostrophe",
                    "path_wildcard", "path_traversal", "logged_whitespace"), (None, "Unsupported worker path")),
    "selected_compiler_decoy": ("gradle-worker-classpath2txt", None),
    **dict.fromkeys(("selected_missing", "selected_stale", "selected_ambiguous"),
                   (None, "Ambiguous or missing selected worker file")),
    **dict.fromkeys(("selected_baseline_disappeared", "selected_wrong_suffix", "selected_duplicate"),
                   (None, "Invalid worker file inventory")),
    "capture_success": ("CAPTURED:null", None),
    "capture_exception": ("REFUSED:CONTENT_MISMATCH", None),
    "writer_exception": ("CAPTURED:false", None),
}


def integer(value, expected=None):
    return type(value) is int and (expected is None or value == expected)


def source_path(name):
    """The same spelling must address one ordinary file on POSIX and Windows."""
    require(type(name) is str and 0 < len(name) <= 1024, "Invalid source pathname")
    path = PurePosixPath(name)
    require(path.as_posix() == name and not path.is_absolute() and len(path.parts) <= 64 and
            all(part.casefold() not in (".", "..", ".git") and not part.endswith((".", " ")) and
                not re.search(r'[\\\x00-\x1f<>:"|?*]', part) and
                not re.fullmatch(r"(?i:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\..*)?", part)
                for part in path.parts), "Unsafe or ambiguous Windows source pathname")
    return path


def tree_entries(raw):
    require(type(raw) is bytes and raw.endswith(b"\0") and len(raw) <= MAX_FILE, "Invalid bounded source tree listing")
    rows, names, total = {}, set(), 0
    for entry in raw[:-1].split(b"\0"):
        header, encoded = entry.split(b"\t", 1)
        mode, kind, blob, size = header.split()
        name = encoded.decode("utf-8", errors="strict")
        source_path(name)
        require(mode in (b"100644", b"100755") and kind == b"blob" and
                re.fullmatch(rb"[0-9a-f]{40}", blob) and re.fullmatch(rb"[0-9]+", size) and
                name.casefold() not in names, "Unsupported/duplicate source entry")
        length = int(size)
        total += length
        names.add(name.casefold())
        require(length <= MAX_FILE and total <= MAX_BYTES and len(names) <= MAX_FILES,
                "Source tree exceeds byte/entry bounds")
        rows[name] = {"mode": mode.decode(), "blob": blob.decode(), "bytes": length}
    require(rows, "Empty source tree")
    # A Windows case-folded directory must not alias a file or another directory.
    spellings = {}
    for name in rows:
        path = PurePosixPath(name)
        for index in range(1, len(path.parts) + 1):
            member = "/".join(path.parts[:index])
            prior = spellings.setdefault(member.casefold(), member)
            require(prior == member and (index == len(path.parts) or member.casefold() not in names),
                    "Source file/directory alias")
    return rows


def blob_matches(raw, row):
    return len(raw) == row["bytes"] and hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == row["blob"]


def export_archive(raw, entries, root):
    """No extractall, filters or trust in archive attributes: every blob is checked.

    `git archive` can omit/substitute files via attributes. Such an archive is
    rejected against ls-tree and each blob hash, never accepted as another tree.
    """
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "Unbounded source archive")
    seen, directories = set(), set()
    ancestors = {parent.as_posix() for name in entries for parent in PurePosixPath(name).parents
                 if parent != PurePosixPath(".")}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for count, item in enumerate(archive, 1):
            require(count <= MAX_FILES * 2, "Archive membership exceeds its bound")
            name = item.name.rstrip("/") if item.isdir() else item.name
            source_path(name)
            if item.isdir():
                require(name in ancestors and name not in directories and item.size == 0, "Unexpected archive directory")
                directories.add(name)
                continue
            require(item.isfile() and name in entries and name not in seen and item.size == entries[name]["bytes"],
                    "Linked, missing, extra, duplicate or oversized archive member")
            source = archive.extractfile(item)
            require(source is not None, "Missing archive blob")
            with source:
                value = source.read(MAX_FILE + 1)
            require(blob_matches(value, entries[name]), "Archive bytes differ from Git blob (including export substitution)")
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            write(destination, value)
            if os.name != "nt" and entries[name]["mode"] == "100755":
                destination.chmod(0o700)
            seen.add(name)
    require(seen == set(entries), "Archive omitted a tracked source (including export-ignore)")


def preserve_finalization_errors(original, failures, phase):
    """Keep secondary failures on the same terminal object, including Python 3.9."""
    pending = [({"phase": phase, "resource": label, "status": "UNKNOWN",
                 "error": processes.format_ownership_error(error)[:512]}, error)
               for label, error in failures if error is not original]
    processes._finish_retirement(pending, original=original)


def regular(path, limit=MAX_FILE):
    audit.reject_symlinks(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
            "Expected bounded ordinary, non-hardlinked control file")
    with path.open("rb") as stream:
        require(os.path.samestat(before, os.fstat(stream.fileno())), "Control file replaced while opening")
        value = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(len(value) == before.st_size and (after.st_size, after.st_mtime_ns) ==
            (before.st_size, before.st_mtime_ns), "Control file changed or exceeded its bound")
    return value


def sdk_tool_snapshot(sdk):
    """Hash only: installed launcher bytes are not approved public evidence."""
    files = {}
    for name in ("cmdline-tools/latest/bin/sdkmanager.bat", "cmdline-tools/latest/source.properties"):
        raw = regular(sdk / name, limit=256 * 1024)
        files[name] = {"bytes": len(raw), "sha256": digest(raw)}
    return {"schema": 1, "files": files}


def read_json(path):
    value = json.loads(regular(path, audit.MAX_JSON_BYTES), object_pairs_hook=audit.unique_object,
                       parse_constant=lambda _: (_ for _ in ()).throw(audit.AuditError("Nonfinite control JSON")))
    require(type(value) is dict, "Control JSON root is not an object")
    return value


def write(path, raw):
    require(len(raw) <= MAX_BYTES, "Control output exceeds its bound")
    with audit.new_file(path) as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def dispatch_identity(env, event, source):
    expected = env.get("P2PKIT_EXPECTED_SHA", "")
    tree = env.get("P2PKIT_EXPECTED_TREE", "")
    require(re.fullmatch(r"[0-9a-f]{40}", expected) and re.fullmatch(r"[0-9a-f]{40}", tree),
            "Control dispatch requires exact reviewed SHA and tree")
    fixed = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
             "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_SERVER_URL": "https://github.com",
             "GITHUB_API_URL": "https://api.github.com", "GITHUB_JOB": JOB,
             "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Windows", "RUNNER_ARCH": "X64",
             "P2PKIT_OPERATION": OPERATION, "GITHUB_SHA": expected, "GITHUB_WORKFLOW_SHA": expected}
    require(all(env.get(key) == value for key, value in fixed.items()), "Wrong genuine hosted dispatch identity")
    ref = env.get("GITHUB_REF", "")
    require(ref.startswith("refs/heads/") and len(ref) <= 256 and
            not any(char in ref for char in "\r\n\0") and ref != "refs/heads/audit/complete-2026-09-04",
            "Control requires an ordinary reviewed branch, not the retired audit ref")
    require(env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@" + ref,
            "Workflow ref differs from the actual source ref")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(re.fullmatch(r"[1-9][0-9]{0,19}", env.get(key, "")), "Missing real run/attempt identity")
    require(type(event) is dict and event.get("repository", {}).get("full_name") == REPOSITORY and
            event.get("ref") in (ref, ref[len("refs/heads/"):]),
            "Original workflow_dispatch event disagrees with controller inputs")
    # GitHub may include the shared workflow's new writer defaults. This
    # witness accepts only empty strings; its source/command authority is intact.
    writer_defaults = {"reviewed_base", "evidence_public_key", "evidence_fingerprint"}
    inputs = {"operation": OPERATION, "expected_sha": expected, "expected_tree": tree}
    provided = event.get("inputs")
    require(type(provided) is dict and
            {key: value for key, value in provided.items() if key not in writer_defaults} == inputs and
            all(type(provided[key]) is str and provided[key] == "" for key in writer_defaults & provided.keys()),
            "Original workflow_dispatch event disagrees with controller inputs")
    require(source == {"commit": expected, "tree": tree, "status": "", "diffSha256": digest(b"")},
            "Control source is wrong, dirty or not the complete reviewed tree")
    return {"repository": REPOSITORY, "event": "workflow_dispatch", "ref": ref,
            "workflowRef": env["GITHUB_WORKFLOW_REF"], "workflowSha": expected,
            "sourceSha": expected, "sourceTree": tree, "runId": env["GITHUB_RUN_ID"],
            "runAttempt": env["GITHUB_RUN_ATTEMPT"], "job": JOB}


def transform(current, historical, test, old_test):
    require(digest(current) == CURRENT_SHA and digest(historical) == HISTORICAL_SHA and
            digest(test) == TEST_SHA and b"\r" not in current + historical + test,
            "Reviewed file/test preimage changed, including checkout line endings")
    require(current.count(CURRENT_METHOD) == historical.count(OLD_METHOD) == 1,
            "Ambiguous reviewed method preimage")
    pattern = rb"    @Test\n    fun " + METHOD.encode() + rb"\(\).*?\n    }\n"
    blocks = re.findall(pattern, test, re.S)
    prior = re.findall(pattern, old_test, re.S)
    require(len(blocks) == len(prior) == 1 and blocks == prior and digest(blocks[0]) == TEST_BLOCK_SHA,
            "Selected historical/current test is not the exact unchanged witness")
    value = current.replace(CURRENT_METHOD, OLD_METHOD, 1)
    require(digest(value) == PREIMAGE_SHA, "Unexpected transformed whole-file bytes")
    return value


def tree_delta(before, after):
    require(set(before) == set(after), "Preimage added/removed another tracked source")
    changed = [name for name in before if before[name] != after[name]]
    require(changed == [SOURCE], "Preimage tree delta is not exactly the single approved method file")
    require(before[SOURCE]["mode"] == after[SOURCE]["mode"] == "100644" and
            before[SOURCE]["sha256"] == CURRENT_SHA and after[SOURCE]["sha256"] == PREIMAGE_SHA,
            "Wrong method-preimage mode or bytes")


def window_path(value):
    require(type(value) is str and 0 < len(value) <= 32768 and not any(c in value for c in "\0\r\n"),
            "Invalid Windows evidence path")
    path = PureWindowsPath(value)
    require(path.is_absolute() and re.fullmatch(r"[A-Za-z]:", path.drive) and ".." not in path.parts and
            all(":" not in part for part in path.parts[1:]), "Nonordinary Windows evidence path")
    return path


def worker_path(value, *, logged=False):
    """Finite, alias-free spelling; deliberately not a generic Java log parser."""
    require(type(value) is str and len(value) <= 4096 and re.fullmatch(r"[A-Za-z]:\\[ -~]+", value) and
            not any(char in value for char in ";\"'") and (not logged or not re.search(r"\s", value)),
            "Unsupported worker path")
    parts = value[3:].split("\\")
    require(len(parts) <= 64 and all(part and part not in (".", "..") and not part.endswith((".", " ")) and
                not re.search(r'[<>:|?*/]', part) and
                not re.fullmatch(r"(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)
                for part in parts), "Unsupported worker path")
    return value


def worker_inventory(value):
    require(type(value) is dict and set(value) == {"exists", "names"} and type(value["exists"]) is bool and
            type(value["names"]) is list and len(value["names"]) <= 64 and
            all(type(name) is str and re.fullmatch(WORKER_NAME, name) for name in value["names"]) and
            value["names"] == sorted(set(value["names"])) and (value["exists"] or not value["names"]),
            "Invalid worker file inventory")
    return value["names"]


def worker_expected(value, request):
    """Independent authority -> exact pinned ArgWriter bytes, never raw -> expected."""
    for key in ("root", "state", "java17", "java21", "testTemporary", "outputDirectory"):
        worker_path(request.get(key), logged=True)
    home = request["state"] + r"\gradle-home"
    require(type(value) is dict and set(value) == {"gradleVersion", "gradleHome", "testIsModule", "modulePath",
            "nativeCharset", "nativeEncodedSha256", "bootstrap", "applicationClasspath", "beforeFiles"} and
            value["gradleVersion"] == "9.7.0" and value["gradleHome"] == home and
            value["testIsModule"] is False and value["modulePath"] == [], "Wrong worker producer/home/modularity")
    worker_inventory(value["beforeFiles"])
    bootstrap = value["bootstrap"]
    require(type(bootstrap) is dict and set(bootstrap) == {"path", "bytes", "sha256"} and
            worker_path(bootstrap["path"]).startswith(home + "\\caches\\") and
            bootstrap["path"].endswith("\\gradle-worker.jar") and
            integer(bootstrap["bytes"]) and 0 < bootstrap["bytes"] <= 4 * 1024 * 1024 and
            type(bootstrap["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", bootstrap["sha256"]),
            "Wrong worker bootstrap authority")
    entries = value["applicationClasspath"]
    require(type(entries) is list and len(entries) <= 512, "Unbounded worker application classpath")
    seen, paths = {bootstrap["path"].casefold()}, [bootstrap["path"]]
    build = request["root"] + "\\library\\p2p-core\\build\\"
    dependencies = home + "\\caches\\modules-2\\files-2.1\\"
    for row in entries:
        require(type(row) is dict and set(row) == {"path", "kind"}, "Invalid worker classpath record")
        path, kind = worker_path(row["path"]), row["kind"]
        require(path.casefold() not in seen and
                (path.startswith(build) and (kind in ("directory", "missing") or kind == "file" and path.endswith(".jar")) or
                 path.startswith(dependencies) and kind == "file" and path.endswith(".jar")),
                "Foreign, duplicate or unsupported worker classpath entry")
        seen.add(path.casefold())
        if kind != "missing":
            paths.append(path)
    require(len(paths) <= 512, "Unbounded effective worker classpath")
    # Gradle 9.7 ArgWriter.javaStyle: escape every backslash/quote, conditionally
    # quote the WHOLE argument, and terminate each argument with Windows CRLF.
    tokens = ["-cp", ";".join(paths)]
    rendered = []
    for token in tokens:
        escaped = token.replace("\\", "\\\\").replace('"', '\\"')
        rendered.append(('"' + escaped + '"' if not escaped or re.search(r"\s|#", escaped) else escaped) + "\r\n")
    text = "".join(rendered)
    expected = text.encode("ascii", errors="strict")
    charset = value["nativeCharset"]
    require(type(charset) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:+-]{0,63}", charset) and
            len(expected) <= WORKER_BYTES, "Unsupported worker encoding/size")
    try:
        encoded = text.encode(charset, errors="strict")
    except (LookupError, UnicodeError) as error:
        raise audit.AuditError("Unsupported worker native charset") from error
    require(encoded == expected and value["nativeEncodedSha256"] == digest(expected),
            "Entire native-encoded worker expansion differs from supported ASCII bytes")
    return expected


def worker_jvm_arguments(arguments, request):
    # Preserve the caller-@/OS/agent checks in assess_execution as well. The
    # expansion exception adds NO general launcher/agent/module option grammar.
    required = {"-Dp2pkit.windowsDirectoryNonce=" + request["nonce"], "-Djava.io.tmpdir=" + request["testTemporary"],
                "-XX:ActiveProcessorCount=2", "-XX:-UsePerfData", "-Xms128m", "-Xmx512m", "-Dfile.encoding=UTF-8", "-ea"}
    locale = (r"-Duser.country(?:=(?:[A-Za-z]{2}|[0-9]{3}))?", r"-Duser.language(?:=[A-Za-z]{2,8})?",
              r"-Duser.variant(?:=[A-Za-z0-9_-]{1,32})?")
    require(type(arguments) is list and len(arguments) == len(required) + len(locale) and
            all(type(item) is str for item in arguments) and
            all(arguments.count(item) == 1 for item in required) and
            all(sum(bool(re.fullmatch(pattern, item)) for item in arguments) == 1 for pattern in locale),
            "Unsupported, duplicate or injected actual worker JVM options")
    return arguments


def assess_worker_capture(value, request, request_hash, admission_hash=None, expansion=None):
    require(type(value) is dict and set(value) == {"schema", "requestSha256", "admissionSha256", "phase",
            "observedMillis", "status", "reason", "afterFiles", "original"} and integer(value["schema"], 1) and
            value["requestSha256"] == request_hash and value["phase"] == "selected-afterTask" and
            integer(value["observedMillis"]) and 0 < value["observedMillis"] < 2 ** 63 and
            (value["admissionSha256"] is None or type(value["admissionSha256"]) is str and
             re.fullmatch(r"[0-9a-f]{64}", value["admissionSha256"])) and
            (admission_hash is None or value["admissionSha256"] == admission_hash) and
            (value["status"] == "CAPTURED" and value["reason"] is None and value["admissionSha256"] is not None or
             value["status"] == "REFUSED" and type(value["reason"]) is str and value["reason"] in WORKER_CAPTURE_REASONS),
            "Invalid worker before-stop capture metadata/binding")
    after = worker_inventory(value["afterFiles"]) if value["afterFiles"] is not None else None
    original = value["original"]
    if original is not None:
        require(type(original) is dict and set(original) == {"path", "bytes", "sha256"} and
                worker_path(original["path"], logged=True).startswith(request["state"] + "\\gradle-home\\.tmp\\") and
                re.fullmatch(WORKER_NAME, original["path"][len(request["state"] + "\\gradle-home\\.tmp\\"):]) and
                integer(original["bytes"]) and 0 < original["bytes"] <= WORKER_BYTES and
                type(original["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", original["sha256"]) and
                after is not None and original["path"].rsplit("\\", 1)[1] in after, "Invalid captured worker file metadata")
    require(value["status"] != "CAPTURED" or original is not None and value["afterFiles"]["exists"],
            "Successful capture lacks the selected original")
    if expansion is not None and original is not None:
        before = worker_inventory(expansion["beforeFiles"])
        require(set(before) <= set(after) and
                [name for name in after if name not in before] == [original["path"].rsplit("\\", 1)[1]],
                "Captured worker is stale, missing, ambiguous or a compiler baseline file")


def worker_observation(execution, envelope, capture, request, request_hash):
    require(type(envelope) is dict and set(envelope) == {"schema", "nonce", "caseName", "requestSha256", "admission"} and
            integer(envelope["schema"], 1) and envelope["nonce"] == request["nonce"] and
            envelope["caseName"] == request["caseName"] and envelope["requestSha256"] == request_hash and
            type(envelope["admission"]) is dict and type(execution) is dict and
            execution.get("admission") == envelope["admission"] and execution.get("scope") == "root" and
            all(execution.get(key) == request[key] for key in ("nonce", "caseName", "source", "identity", "root")) and
            execution.get("requestSha256") == request_hash, "Worker admission/final source binding changed")
    admission = envelope["admission"]
    expected = worker_expected(admission.get("workerExpansion"), request)
    worker_jvm_arguments(admission.get("jvmArgs"), request)
    events = execution.get("events")
    require(type(events) is list and len(events) == 1 and type(events[0]) is dict and
            events[0].get("className") == CLASS and events[0].get("name") == METHOD and
            all(integer(value) for value in (admission.get("observedMillis"), events[0].get("startMillis"),
                events[0].get("endMillis"), execution.get("finishedMillis"))) and
            0 < admission["observedMillis"] <= events[0]["startMillis"] <= events[0]["endMillis"] <=
                capture["observedMillis"] <= execution["finishedMillis"],
            "Worker capture was not between the selected event and root buildFinished")
    return expected


def failure_directory(failure, temporary):
    expected_type = "java.nio.file.AccessDeniedException"
    require(failure.get("type") == expected_type, "Negative control has the wrong exception type")
    stack = failure.text or ""
    first, separator, rest = stack.partition("\n")
    require(separator and first.startswith(expected_type + ": "), "Missing original native failure stack")
    file_name = first[len(expected_type) + 2:].rstrip("\r")
    path, root = window_path(file_name), window_path(temporary)
    require(path.parent == root and re.fullmatch(r"p2pkit-durable-destination-[0-9]+", path.name),
            "AccessDeniedException is not for the owned parent directory (part/target errors do not qualify)")
    require(failure.get("message") in (file_name, expected_type + ": " + file_name),
            "Failure message and original stack disagree about the directory")
    # JDK17 may print its named java.base module or the ordinary app loader.
    # No arbitrary loader/module prefix may conceal a different native frame.
    frames = re.findall(r"^\s+at (?:java\.base/|app//)?([^\s(]+)\([^\r\n]*\)\r?$", rest, re.M)
    required = ["sun.nio.fs.WindowsFileSystemProvider.newFileChannel", "java.nio.channels.FileChannel.open",
                "dev.p2pkit.core.transfer.JvmDurableFileDestination.syncParentDirectory",
                "dev.p2pkit.core.transfer.JvmDurableFileDestination.commit",
                CLASS + "$" + METHOD + "$1.invokeSuspend", CLASS + "." + METHOD]
    position = 0
    for frame in frames:
        if position < len(required) and frame == required[position]:
            position += 1
    require(position == len(required) and "Caused by:" not in rest and "Suppressed:" not in rest,
            "Negative control does not identify the original Windows directory-open/commit/test path")
    return file_name


def assess_xml(raw, request):
    require(type(raw) is bytes and 0 < len(raw) <= 1024 ** 2 and
            not re.search(br"<!\s*(?:DOCTYPE|ENTITY)", raw, re.I), "Invalid bounded control JUnit XML")
    suite = ET.fromstring(raw)
    negative = request["caseName"] == "preimage"
    require(suite.tag == "testsuite" and suite.get("name") == JUNIT_SUITE and suite.get("tests") == "1" and
            suite.get("failures") == str(int(negative)) and suite.get("errors") == suite.get("skipped") == "0",
            "Wrong, empty, skipped or extra control JUnit suite")
    require(all(child.tag in ("properties", "testcase", "system-out", "system-err") for child in suite),
            "Unexpected JUnit suite element")
    cases = suite.findall("testcase")
    require(len(cases) == 1 and cases[0].get("classname") == CLASS and cases[0].get("name") == JUNIT_CASE,
            "Wrong or duplicate selected testcase")
    require(all(child.tag in ("failure", "system-out", "system-err") for child in cases[0]),
            "Skipped/error control testcase is not acceptance")
    failures = cases[0].findall("failure")
    require(len(failures) == int(negative), "Incorrect selected-test failure count")
    return failure_directory(failures[0], request["testTemporary"]) if negative else None


def assess_binding_controls(report, hashes, *, require_pass):
    require(type(report) is dict and set(report) == {"schema", "scope", "gradleVersion", "hashes", "cases",
            "taskPolicyCases", "temporaryPolicyCases", "workerPolicyCases", "workerServiceCases"} and
            integer(report.get("schema"), 5) and
            report.get("scope") == "MODELED_POLICIES_AND_LIVE_GRADLE_SERVICE_LOOKUPS_NOT_NATIVE_PRODUCT" and
            report.get("gradleVersion") == "9.7.0" and report.get("hashes") == hashes and
            type(report.get("cases")) is list and len(report["cases"]) == len(BINDING_CASES),
            "Wrong or stale production-observer model report")
    require([row.get("id") for row in report["cases"] if type(row) is dict] == list(BINDING_CASES),
            "Missing, reordered or duplicate binding-control models")
    for row in report["cases"]:
        expected = BINDING_CASES[row["id"]]
        require(set(row) == {"id", "passed", "expectedMessage", "exceptionType", "message"} and
                row["expectedMessage"] == expected and type(row["passed"]) is bool and
                all(row[key] is None or type(row[key]) is str and len(row[key]) <= 256
                    for key in ("exceptionType", "message")) and
                row["passed"] is (row["exceptionType"] == "org.gradle.api.GradleException" and row["message"] == expected),
                "Binding model has a malformed or falsely passing result")
    require(not require_pass or all(row["passed"] for row in report["cases"]),
            "Actual production-observer negative controls failed")
    rows = report["taskPolicyCases"]
    require(type(rows) is list and len(rows) == len(TASK_POLICY_INPUTS) and
            [row.get("id") for row in rows if type(row) is dict] == list(TASK_POLICY_INPUTS),
            "Missing, reordered or duplicate constructed-StartParameter controls")
    for row in rows:
        expected = {"buildSrc": False, "dryRun": False, "excludedTasks": [], "accepted": False,
                    **TASK_POLICY_INPUTS[row["id"]]}
        require(set(row) == {"id", "passed", "accepted", "exceptionType", "message", "requestedTasks",
                            "excludedTasks", "dryRun", "buildSrc"} and
                all(type(row[key]) is bool for key in ("passed", "accepted", "dryRun", "buildSrc")) and
                all(row[key] == expected[key] for key in ("requestedTasks", "excludedTasks", "dryRun", "buildSrc")) and
                all(row[key] is None or type(row[key]) is str and len(row[key]) <= 256
                    for key in ("exceptionType", "message")) and
                (not row["accepted"] or row["exceptionType"] is None and row["message"] is None),
                "Wrong constructed-StartParameter input or result shape")
        passed = row["accepted"] is expected["accepted"] and (
            row["accepted"] or row["exceptionType"] == "org.gradle.api.GradleException" and row["message"] == TASK_POLICY_MESSAGE)
        require(row["passed"] is passed, "Falsely passing production task-policy control")
    require(not require_pass or all(row["passed"] for row in rows), "Actual production task-policy controls failed")
    rows = report["temporaryPolicyCases"]
    require(type(rows) is list and len(rows) == len(TEMPORARY_POLICY_INPUTS) and
            [row.get("id") for row in rows if type(row) is dict] == list(TEMPORARY_POLICY_INPUTS),
            "Missing, reordered or duplicate temporary-attribute controls")
    for row in rows:
        expected = {"directory": True, "other": False, "symbolicLink": False, "hasEntries": False,
                    "fileKey": None, "accepted": False, "message": TEMPORARY_POLICY_MESSAGE,
                    **TEMPORARY_POLICY_INPUTS[row["id"]]}
        require(set(row) == {"id", "passed", "accepted", "exceptionType", "message", "directory", "other",
                            "symbolicLink", "hasEntries", "fileKey", "observedFileKey"} and
                all(type(row[key]) is bool for key in ("passed", "accepted", "directory", "other", "symbolicLink", "hasEntries")) and
                all(row[key] == expected[key] for key in ("directory", "other", "symbolicLink", "hasEntries", "fileKey")) and
                all(row[key] is None or type(row[key]) is str and len(row[key]) <= 256
                    for key in ("exceptionType", "message")) and
                (row["observedFileKey"] is None or type(row["observedFileKey"]) is str and len(row["observedFileKey"]) <= 1024) and
                (not row["accepted"] or row["exceptionType"] is None and row["message"] is None),
                "Wrong modeled temporary-attribute input or result shape")
        passed = row["accepted"] is expected["accepted"] and (
            row["observedFileKey"] == expected["fileKey"] if row["accepted"] else
            row["observedFileKey"] is None and row["exceptionType"] == "org.gradle.api.GradleException" and
            row["message"] == expected["message"])
        require(row["passed"] is passed, "Falsely passing production temporary-policy control")
    require(not require_pass or all(row["passed"] for row in rows), "Actual production temporary-policy controls failed")
    rows = report["workerPolicyCases"]
    require(type(rows) is list and len(rows) == len(WORKER_POLICY_CASES) and
            [row.get("id") for row in rows if type(row) is dict] == list(WORKER_POLICY_CASES),
            "Missing, reordered or duplicate worker-policy controls")
    for row in rows:
        value, message = WORKER_POLICY_CASES[row["id"]]
        require(set(row) == {"id", "passed", "value", "exceptionType", "message"} and type(row["passed"]) is bool and
                all(row[key] is None or type(row[key]) is str and len(row[key]) <= 256
                    for key in ("value", "exceptionType", "message")), "Wrong worker-policy result shape")
        passed = (row["value"] == value and row["message"] == message and
                  row["exceptionType"] == ("org.gradle.api.GradleException" if message else None))
        require(row["passed"] is passed, "Falsely passing production worker-policy control")
    require(not require_pass or all(row["passed"] for row in rows), "Actual production worker-policy controls failed")
    rows = report["workerServiceCases"]
    require(type(rows) is list and len(rows) == 2 and
            [row.get("id") for row in rows if type(row) is dict] ==
            ["generic_registry_unknown", "concrete_provider_bootstrap"],
            "Missing, reordered or duplicate live Gradle service controls")
    for row in rows:
        require(set(row) == {"id", "passed", "bootstrap", "exceptionType", "message"} and
                type(row["passed"]) is bool and
                all(row[key] is None or type(row[key]) is str and len(row[key]) <= 256
                    for key in ("exceptionType", "message")), "Wrong live Gradle service result shape")
        bootstrap = row["bootstrap"]
        if bootstrap is not None:
            require(row["id"] == "concrete_provider_bootstrap" and type(bootstrap) is dict and
                    set(bootstrap) == {"relativePath", "bytes", "sha256"} and
                    type(bootstrap["relativePath"]) is str and len(bootstrap["relativePath"]) <= 4096 and
                    re.fullmatch(r"caches/(?:[A-Za-z0-9_.-]+/){1,60}gradle-worker[.]jar", bootstrap["relativePath"]) and
                    not {".", ".."}.intersection(bootstrap["relativePath"].split("/")) and
                    integer(bootstrap["bytes"]) and 0 < bootstrap["bytes"] <= 4 * 1024 ** 2 and
                    type(bootstrap["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", bootstrap["sha256"]),
                    "Invalid real bootstrap observation in live service control")
        passed = (bootstrap is None and row["exceptionType"] == "java.lang.IllegalArgumentException" and
                  row["message"] == "unknown classpath 'WORKER_MAIN' requested.") if row["id"] == "generic_registry_unknown" else (
                  bootstrap is not None and row["exceptionType"] is None and row["message"] is None)
        require(row["passed"] is passed, "Falsely passing live Gradle service control")
    require(not require_pass or all(row["passed"] for row in rows), "Actual live Gradle service controls failed")


def assess_execution(report, request, request_hash, scope="root"):
    require(type(report) is dict and integer(report.get("schema"), 1) and report.get("scope") == scope and
            report.get("nonce") == request["nonce"] and report.get("caseName") == request["caseName"] and
            report.get("source") == request["source"] and report.get("identity") == request["identity"] and
            report.get("requestSha256") == request_hash, "Wrong/stale execution nonce, source, case or run")
    binding = report.get("binding")
    expected_properties = {"p2pkit.windowsDirectoryRoot": request["root"],
        "p2pkit.windowsDirectoryRequest": str(window_path(request["outputDirectory"]) / "request.json"),
        "p2pkit.windowsDirectoryRequestSha256": request_hash}
    require(scope in ("root", "buildSrc") and type(binding) is dict and
            set(binding) == {"authority", "parentRoot", "parentHasParent", "localProperties"} and
            binding["authority"] == ("self" if scope == "root" else "direct-root-parent") and
            binding["parentHasParent"] is False and
            binding["parentRoot"] == (None if scope == "root" else request["root"]) and
            type(binding["localProperties"]) is dict and
            (binding["localProperties"] == expected_properties or scope == "buildSrc" and binding["localProperties"] == {}),
            "Missing, partial, conflicting or foreign root/buildSrc request authority")
    host = report.get("host", {})
    require(host.get("os", "").startswith("Windows") and host.get("arch") == "amd64" and
            host.get("javaVersion", "").startswith("21.") and
            window_path(host.get("javaHome")) == window_path(request["java21"]),
            "Execution did not use the actual admitted Windows JDK21 daemon")
    require(report.get("dryRun") is False and report.get("excludedTasks") == [],
            "Dry/excluded task execution is not acceptance")
    graph = report.get("graph")
    tasks = report.get("tasks")
    require(type(graph) is list and 0 < len(graph) <= 32 and type(tasks) is dict,
            "Missing or excessive actual task graph/outcomes")
    paths = [row.get("path") for row in graph if type(row) is dict]
    require(len(paths) == len(graph) and len(set(paths)) == len(paths) and set(tasks) == set(paths),
            "Missing, duplicate or unfinished graph task outcomes")
    negative = request["caseName"] == "preimage" and scope == "root"
    require(report.get("buildFailed") is negative, "Wrong build failure, including setup/compilation failure")
    for name, row in tasks.items():
        expected_failure = negative and name == TASK
        require(type(row) is dict and row.get("outcome") in ("EXECUTED", "NO_SOURCE", "SKIPPED", "FAILED") and
                (row.get("outcome") == "FAILED") is expected_failure and
                bool(row.get("failureType")) is expected_failure, "Unexpected failed, reused or stale task")
    if scope == "buildSrc":
        require(window_path(report.get("root")) == window_path(request["root"]) / "buildSrc" and
                set(paths) <= {":compileJava", ":compileGroovy", ":processResources", ":classes", ":jar"} and
                all(row.get("test") is False for row in graph) and report.get("events") == [],
                "Unexpected buildSrc product/test task")
        require({":compileJava", ":jar"} <= set(paths) and
                all(tasks[name]["outcome"] == "EXECUTED" for name in (":compileJava", ":jar")),
                "buildSrc compiler/JAR did not freshly execute")
        return
    require(window_path(report.get("root")) == window_path(request["root"]) and
            report.get("requestedTasks") == [TASK, "--tests", SELECTOR] and
            set(paths) <= CORE_TASKS and REQUIRED_TASKS <= set(paths) and
            all(row.get("test") is (row["path"] == TASK) for row in graph),
            "Extra product/test task or wrong requested selector")
    for name in REQUIRED_TASKS:
        require(tasks[name]["outcome"] == ("FAILED" if negative and name == TASK else "EXECUTED") and
                tasks[name].get("didWork") is True, "Required task did not freshly execute")
    admission = report.get("admission", {})
    require(admission.get("task") == TASK and admission.get("commandFilters") == [SELECTOR] and
            admission.get("includePatterns") == admission.get("excludePatterns") == [] and
            admission.get("enabled") is True and admission.get("ignoreFailures") is False and
            admission.get("failOnNoMatchingTests") is True and integer(admission.get("maxParallelForks"), 1) and
            integer(admission.get("forkEvery"), 0) and admission.get("temporaryEmpty") is True and
            "temporaryFileKey" in admission and (admission["temporaryFileKey"] is None or
                type(admission["temporaryFileKey"]) is str and 0 < len(admission["temporaryFileKey"]) <= 1024) and
            admission.get("temporaryOwnerSha256") == request["temporaryOwnerSha256"] and
            integer(admission.get("observedMillis")) and integer(report.get("finishedMillis")) and
            window_path(admission.get("temporary")) == window_path(request["testTemporary"]),
            "Wrong test admission/filter/fork/temporary ownership")
    launcher = admission.get("launcher", {})
    require(integer(launcher.get("version"), 17) and window_path(launcher.get("home")) == window_path(request["java17"]) and
            window_path(launcher.get("executable")) == window_path(request["java17"]) / "bin/java.exe",
            "Test launcher is not the admitted native JDK17")
    arguments = admission.get("jvmArgs", [])
    required_args = {"-Djava.io.tmpdir=" + request["testTemporary"],
                     "-Dp2pkit.windowsDirectoryNonce=" + request["nonce"],
                     "-Xmx512m", "-Xms128m", "-XX:ActiveProcessorCount=2", "-XX:-UsePerfData"}
    require(type(arguments) is list and all(type(item) is str for item in arguments) and
            all(arguments.count(item) == 1 for item in required_args) and
            all(sum(item.startswith(prefix) for item in arguments) == 1 for prefix in
                ("-Djava.io.tmpdir=", "-Dp2pkit.windowsDirectoryNonce=", "-Xmx", "-Xms", "-XX:ActiveProcessorCount=")) and
            not any(item.startswith(("-Dos.name=", "-Dos.arch=", "-javaagent:", "@")) for item in arguments),
            "Missing, duplicate or injected worker JVM arguments")
    worker_jvm_arguments(arguments, request)
    worker_expected(admission.get("workerExpansion"), request)
    events = report.get("events")
    require(type(events) is list and len(events) == 1 and type(events[0]) is dict, "Empty or extra test events")
    event = events[0]
    require(event.get("className") == CLASS and event.get("name") == METHOD and
            event.get("result") == ("FAILURE" if negative else "SUCCESS") and integer(event.get("testCount"), 1) and
            integer(event.get("passed"), int(not negative)) and integer(event.get("failed"), int(negative)) and
            integer(event.get("skipped"), 0) and integer(event.get("startMillis")) and
            integer(event.get("endMillis")) and 0 < admission["observedMillis"] <=
            event["startMillis"] <= event["endMillis"] <= report["finishedMillis"],
            "Wrong, skipped, extra or stale selected-test events")


def assess_worker_log(raw, request, admission, argfile):
    text = raw.decode("utf-8", errors="strict")
    launches = re.findall(r"^Starting process 'Gradle Test Executor [^\r\n]+", text, re.M)
    starts = re.findall(r"^Successfully started process 'Gradle Test Executor [^\r\n]+", text, re.M)
    require(len(launches) == len(starts) == 1,
            "Original info log lacks the one actually launched Test worker")
    launch = re.fullmatch(r"Starting process 'Gradle Test Executor ([1-9][0-9]{0,5})'\. Working directory: (.+) Command: (.+)",
                          launches[0])
    require(launch is not None and starts[0] == "Successfully started process 'Gradle Test Executor " + launch[1] + "'",
            "Malformed or mismatched selected worker/start ID")
    worker_path(argfile, logged=True)
    require(launch[2] == worker_path(request["root"], logged=True) + r"\library\p2p-core" and
            argfile.startswith(request["state"] + "\\gradle-home\\.tmp\\") and
            re.fullmatch(WORKER_NAME, argfile[len(request["state"] + "\\gradle-home\\.tmp\\"):]),
            "Actual worker directory/argument file escaped its bound producer")
    arguments = worker_jvm_arguments(admission.get("jvmArgs"), request)
    # Pinned worker builder adds tmpdir to mutable system properties and the
    # options file to extra JVM args, before the immutable heap/property suffix.
    split = arguments.index("-Xms128m")
    options = ["-Dorg.gradle.internal.worker.tmpdir=" + request["root"] + r"\library\p2p-core\build\tmp\jvmTest\work",
               *arguments[:split], "@" + argfile, *arguments[split:]]
    java = worker_path(request["java17"], logged=True) + r"\bin\java.exe"
    expected = " ".join([java, *options, WORKER_MAIN, "'Gradle Test Executor " + launch[1] + "'"])
    require(launch[3] == expected, "Actual worker command differs from its admitted options/one expansion/main")
    return launch[1]


def stop_arguments(root):
    return [str(root / "gradlew.bat"), "--stop", "--console=plain", "--no-parallel", "--max-workers=2",
            "-Dorg.gradle.jvmargs=" + audit.JVM_ARGUMENTS]


def native_receipt(receipt, context, root, arguments, purpose, status, identifier, kind):
    wrapper = root / "gradlew.bat"
    receipt_check.validate(receipt, status, purpose, root, wrapper, arguments)
    require(receipt.get("id") == identifier and re.fullmatch(HEX32, identifier) and
            receipt.get("kind") == kind and kind in ("gradle", "command") and
            receipt.get("jobId") == context["id"] and receipt.get("host") == "windows-x64" and
            receipt.get("gradleHome") == context["gradleHome"] and receipt.get("sourceBefore") == context["source"] and
            not receipt.get("cancelledSignals") and not receipt.get("cancelRequested"),
            "Receipt context/source/cancellation differs")
    evidence = Path(context["gradleHome"]).parent / "evidence" / identifier
    executed = [str(wrapper), *audit.gradle_arguments(arguments)] if kind == "gradle" else arguments
    require(receipt.get("evidenceDirectory") == str(evidence) and receipt.get("stopArgv") == stop_arguments(root) and
            receipt.get("executedArgv") == executed, "Receipt command/stop/evidence binding differs")
    ownership = receipt.get("ownership", {})
    require(ownership.get("backend") == "windows-job-list-suspended" and
            ownership.get("scope") == "kernel-job-no-breakaway-kill-on-close" and
            ownership.get("job") == context["id"] and ownership.get("invocation") == receipt["id"] and
            ownership.get("discoveryErrors") == [], "Native Windows ownership was not retained")
    launches = ownership.get("launches", [])
    require(type(launches) is list and len(launches) == 2, "Unexpected product/stop launches")
    require(integer(receipt.get("productLaunchIndex"), 0) and integer(receipt.get("stopLaunchIndex"), 1),
            "Missing or duplicated product/stop launch indices")
    identities = ownership.get("startedIdentities")
    require(type(identities) is list and all(type(row) is dict and integer(row.get("pid")) and row["pid"] > 0 and
            integer(row.get("creationFileTime")) and row["creationFileTime"] > 0 for row in identities),
            "Missing exact native process identities")
    for index, argv in ((receipt.get("productLaunchIndex"), receipt.get("executedArgv")),
                        (receipt.get("stopLaunchIndex"), receipt.get("stopArgv"))):
        require(type(index) is int and index in (0, 1), "Missing exact launch index")
        launch = launches[index]
        require(launch.get("requestedArgv") == argv and launch.get("cwd") == str(root) and
                integer(launch.get("pid")) and launch["pid"] > 0 and launch.get("created") is True and
                launch.get("resumed") is True and launch.get("jobAssignedBeforeResume") is True and
                launch.get("api") == "CreateProcessW", "Launch lacked before-resume kernel admission")
        require(any(row["pid"] == launch["pid"] and row.get("jobAssignedBeforeResume") is True for row in identities),
                "Launch PID lacks its before-resume creation-time identity")
    require(receipt.get("productPid") == launches[0]["pid"] and integer(receipt.get("productPid")),
            "Product launch PID differs from receipt")
    require(len({(row["pid"], row["creationFileTime"]) for row in identities}) == len(identities),
            "Duplicated native creation-time identity")


def assess_report_manifest(receipt, manifest):
    require(integer(manifest.get("schema"), 1) and type(manifest.get("records")) is list and
            audit.json_bytes(manifest["records"]) == audit.json_bytes(receipt.get("reports")),
            "Retained report manifest and receipt disagree")
    sources = []
    for row in manifest["records"]:
        require(type(row) is dict and type(row.get("source")) is str and integer(row.get("bytes")) and
                0 <= row["bytes"] <= audit.MAX_ARCHIVE_BYTES and type(row.get("sha256")) is str and
                re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) and
                row.get("classification") in ("changed-since-admission", "preexisting-unchanged"),
                "Malformed original report record")
        source_path(row["source"])
        fresh = row["classification"] == "changed-since-admission"
        require(set(row) == {"source", "bytes", "sha256", "classification"} | ({"retained"} if fresh else set()) and
                (not fresh or row["retained"] == "reports/" + row["source"]), "Unsafe retained report path")
        sources.append(row["source"])
    require(sources == sorted(set(sources)), "Duplicate/unsorted report source records")


def prepared_context(state, context, case, env):
    require(state == case["state"] and context.get("root") == str(case["root"]) and
            context.get("gradleHome") == str(state / "gradle-home") and context.get("host") == "windows-x64" and
            context.get("source") == case["before"]["source"] and
            context.get("expectedCommit") == case["before"]["source"]["commit"] and
            context.get("tree") == case["before"]["source"]["tree"] and
            context.get("preexistingOutputPaths") == [] and
            context.get("javaHomes") == [env["JAVA_HOME"], env["P2PKIT_AUDIT_JDK21"]],
            "Fresh context differs from the prepared source, output baseline, home or toolchains")


def require_disposal_evidence(case):
    require(case["initialized"], "Partial allocation retained for inspection; no product/cleanup qualification")
    require(all(row["valid"] for row in case["leaves"]), "Unfinalized leaf prevents source/cache cleanup")
    require(all(row["retained"] for row in case["leaves"]) and not case["retentionErrors"] and
            (not case["productPrepared"] or case["productRetained"] and case.get("testTemporaryRetired") is True) and
            (not case.get("bindingPrepared") or case.get("bindingRetained")) and
            (not case["nativeStarted"] or case["nativeAccepted"]),
            "Required original retention failed; preserve sources, outputs and caches")


def native_temporary_identity(info):
    return {"device": info.st_dev, "inode": info.st_ino, "birthNs": getattr(info, "st_birthtime_ns", None)}


def require_positive_temporary_identity(value):
    require(type(value) is dict and set(value) == {"device", "inode", "birthNs"} and
            all(type(value[key]) is int and 0 < value[key] < 2 ** 128 for key in ("device", "inode")) and
            (value["birthNs"] is None or type(value["birthNs"]) is int and -2 ** 127 <= value["birthNs"] < 2 ** 128),
            "Test temporary directory lacks positive native identity")


def identified_test_temporary(directory):
    """Root-first full lstat, not cached DirEntry fields or Java fileKey."""
    require(directory.is_absolute() and ".." not in directory.parts and len(directory.parts) <= 64 and
            len(str(directory)) <= 1024, "Invalid test temporary path")
    for path in (*reversed(directory.parents), directory):
        info = path.lstat()
        require(native_temporary_kind(info.st_mode, getattr(info, "st_file_attributes", None)) == "directory",
                "Unsafe test temporary directory or ancestor")
    identity = native_temporary_identity(info)
    require_positive_temporary_identity(identity)
    return identity


def native_temporary_kind(mode, attributes):
    if (attributes or 0) & 0x400:
        return "reparse-point"
    if stat.S_ISLNK(mode):
        return "symlink"
    return "directory" if stat.S_ISDIR(mode) else "file" if stat.S_ISREG(mode) else "other"


def native_temporary_metadata(info):
    attributes = getattr(info, "st_file_attributes", None)
    return {**native_temporary_identity(info), "mode": info.st_mode, "links": info.st_nlink,
            "bytes": info.st_size, "modifiedNs": info.st_mtime_ns, "changedNs": info.st_ctime_ns,
            "fileAttributes": attributes, "reparseTag": getattr(info, "st_reparse_tag", None),
            "kind": native_temporary_kind(info.st_mode, attributes)}


def native_temporary_name(name):
    return type(name) is str and 0 < len(name) <= 255 and name not in (".", "..") and not name.endswith((".", " ")) and \
        not re.search(r'[/\\\x00-\x1f<>:"|?*]', name) and \
        not re.fullmatch(r"(?i:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\..*)?", name)


def observe_native_temporary(directory, expected, deadline):
    """Direct-entry metadata only: no contents, readlink, recursion, retry or removal.

    Observe a quiescent controller-owned root before/after the leaf and its stop.
    Top-down lstat guards do not claim atomic containment against a malicious
    concurrent filesystem actor. Count/time bounds share the controller deadline;
    they cannot interrupt a blocking kernel metadata call.
    """
    record = {"directory": str(directory), "expectedRootIdentity": expected, "startedUtc": audit.utc(),
              "rootBefore": None, "rootAfter": None, "entries": [], "errors": [], "complete": False, "empty": None}

    def check_time():
        if time.monotonic() >= deadline:
            raise TimeoutError("Native temporary metadata deadline")

    def root(slot=None):
        check_time()
        require(directory.is_absolute() and ".." not in directory.parts and len(directory.parts) <= 64 and
                len(str(directory)) <= 1024, "Invalid native temporary observation path")
        # lstat itself follows intermediate links: reject ancestors root-first.
        for parent in reversed(directory.parents):
            check_time()
            info = parent.lstat()
            require(native_temporary_kind(info.st_mode, getattr(info, "st_file_attributes", None)) == "directory",
                    "Unsafe native temporary ancestor")
        info = directory.lstat()
        if slot:
            record[slot] = native_temporary_metadata(info)
        require(native_temporary_kind(info.st_mode, getattr(info, "st_file_attributes", None)) == "directory" and
                native_temporary_identity(info) == expected, "Native temporary root is unsafe or replaced")
        check_time()

    def failed(step, error, entry=None):
        def number(value):
            return value if type(value) is int and -(2 ** 31) <= value < 2 ** 32 else None
        name = type(error).__name__
        record["errors"].append({"step": step, "entry": entry,
            "exceptionType": name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name) else "Exception",
            "errno": number(getattr(error, "errno", None)), "winerror": number(getattr(error, "winerror", None))})

    step = "path"
    try:
        require(directory.is_absolute() and ".." not in directory.parts and len(directory.parts) <= 64 and
                len(str(directory)) <= 1024, "Invalid native temporary observation path")
        step = "root-before"
        root("rootBefore")
        step = "entries"
        with os.scandir(directory) as iterator:
            for entry in iterator:
                check_time()
                step = "entry-limit"
                require(len(record["entries"]) < NATIVE_TEMP_ENTRIES, "Native temporary entry bound exceeded")
                step = "entry-name"
                require(native_temporary_name(entry.name), "Unsafe native temporary direct-entry name")
                step = "root-recheck"
                root()
                row = {"name": entry.name, "metadata": None}
                record["entries"].append(row)
                try:
                    # Windows DirEntry inode/device caches are not authoritative.
                    row["metadata"] = native_temporary_metadata((directory / entry.name).lstat())
                    check_time()
                except Exception as error:
                    failed("entry-metadata", error, entry.name)
                step = "entries"
    except Exception as error:
        failed(step, error)
    finally:
        try:
            root("rootAfter")
        except Exception as error:
            failed("root-after", error)
    record["entries"].sort(key=lambda row: row["name"])
    record.update(endedUtc=audit.utc(), complete=not record["errors"])
    record["empty"] = not record["entries"] if record["complete"] else None
    return record


def validate_temporary_metadata(value, name):
    """Shared finite observation body; callers separately bind schema/owner/leaf."""
    require(type(value["directory"]) is str and 0 < len(value["directory"]) <= 1024 and
            not any(char in value["directory"] for char in "\0\r\n") and all(type(value[key]) is str and
                re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?\+00:00", value[key])
                for key in ("startedUtc", "endedUtc")), "Invalid native temporary path/time metadata")
    directory = PureWindowsPath(value["directory"]) if PureWindowsPath(value["directory"]).drive else PurePosixPath(value["directory"])
    require(directory.is_absolute() and ".." not in directory.parts and directory.parts[-2:] == ("fixtures", name),
            "Native temporary metadata names another root")

    def number(item, optional=False, signed=False):
        return optional and item is None or type(item) is int and (-2 ** 127 if signed else 0) <= item < 2 ** 128

    owner = value["expectedRootIdentity"]
    require(type(owner) is dict and set(owner) == {"device", "inode", "birthNs"} and
            all(number(item, key == "birthNs", key == "birthNs") for key, item in owner.items()),
            "Invalid native temporary identity")
    def metadata(item):
        require(type(item) is dict and set(item) == {"device", "inode", "birthNs", "mode", "links", "bytes",
            "modifiedNs", "changedNs", "fileAttributes", "reparseTag", "kind"} and
            all(number(item[key], key in ("birthNs", "fileAttributes", "reparseTag"),
                       key in ("birthNs", "modifiedNs", "changedNs")) for key in item if key != "kind") and
            item["kind"] == native_temporary_kind(item["mode"], item["fileAttributes"]), "Invalid native entry metadata")
    for key in ("rootBefore", "rootAfter"):
        if value[key] is not None:
            metadata(value[key])
    entries, errors = value["entries"], value["errors"]
    require(type(entries) is list and len(entries) <= NATIVE_TEMP_ENTRIES and type(errors) is list and
            len(errors) <= NATIVE_TEMP_ENTRIES + 2, "Native temporary metadata exceeds its entry/error bound")
    names = []
    for row in entries:
        require(type(row) is dict and set(row) == {"name", "metadata"} and native_temporary_name(row["name"]),
                "Invalid native temporary direct entry")
        names.append(row["name"])
        if row["metadata"] is not None:
            metadata(row["metadata"])
    require(names == sorted(set(names)), "Duplicate/unsorted native temporary direct entries")
    for error in errors:
        require(type(error) is dict and set(error) == {"step", "entry", "exceptionType", "errno", "winerror"} and
                type(error["step"]) is str and error["step"] in NATIVE_TEMP_STEPS and
                (error["entry"] is None or native_temporary_name(error["entry"])) and
                type(error["exceptionType"]) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", error["exceptionType"]) and
                all(item is None or type(item) is int and -(2 ** 31) <= item < 2 ** 32
                    for item in (error["errno"], error["winerror"])), "Invalid native metadata observation error")
    require(type(value["complete"]) is bool and value["complete"] == (not errors) and
            (type(value["empty"]) is bool if value["complete"] else value["empty"] is None),
            "Unknown native temporary observation cannot establish emptiness")
    if value["complete"]:
        require(value["empty"] == (not entries) and all(row["metadata"] is not None for row in entries) and
                all(value[key] is not None and value[key]["kind"] == "directory" and
                    {field: value[key][field] for field in owner} == owner for key in ("rootBefore", "rootAfter")),
                "Incomplete/replaced native temporary root cannot be accepted")


def validate_native_temporary(value, identity, phase):
    """The original native-suite metadata schema remains unchanged."""
    require(type(value) is dict and set(value) == {"schema", "kind", "phase", "identity", "source", "caseName",
        "jobId", "leaf", "directory", "expectedRootIdentity", "startedUtc", "endedUtc", "rootBefore", "rootAfter",
        "entries", "errors", "complete", "empty"} and integer(value["schema"], 1) and
        value["kind"] == "windows-native-temporary-metadata" and phase in ("before", "after") and value["phase"] == phase and
        value["identity"] == identity and value["caseName"] == "current" and
        re.fullmatch(HEX32, value["jobId"] if type(value["jobId"]) is str else ""), "Invalid native temporary binding/schema")
    require(value["source"] == {"commit": identity["sourceSha"], "tree": identity["sourceTree"], "status": "",
                                "diffSha256": digest(b"")}, "Native temporary source differs from reviewed current case")
    validate_temporary_metadata(value, "native-tmp")
    leaf = value["leaf"]
    require(phase == "after" or leaf is None, "Before observation cannot claim a completed leaf")
    if leaf is not None:
        require(type(leaf) is dict and set(leaf) == {"id", "purpose", "status", "valid", "retained"} and
                type(leaf["id"]) is str and re.fullmatch(HEX32, leaf["id"]) and leaf["purpose"] == "executor-native-controls" and
                (leaf["status"] is None or type(leaf["status"]) is int) and
                type(leaf["valid"]) is bool and type(leaf["retained"]) is bool, "Invalid native leaf observation binding")
    require(len(audit.json_bytes(value)) <= NATIVE_TEMP_BYTES, "Native temporary metadata exceeds its byte bound")


def validate_test_temporary_owner(owner, identity, case_name):
    require(type(owner) is dict and set(owner) == {"schema", "identity", "source", "caseName", "jobId", "nonce",
            "directory", "createdUtc", "nativeIdentity"} and integer(owner["schema"], 2) and
            owner["identity"] == identity and owner["caseName"] == case_name and case_name in ("current", "preimage") and
            all(type(owner[key]) is str and re.fullmatch(HEX32, owner[key]) for key in ("nonce", "jobId")) and
            type(owner["createdUtc"]) is str and
            re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?\+00:00", owner["createdUtc"]),
            "Wrong test temporary creation binding")
    source = owner["source"]
    require(type(source) is dict and set(source) == {"commit", "tree", "status", "diffSha256"} and
            all(type(source[key]) is str and re.fullmatch(r"[0-9a-f]{40}", source[key]) for key in ("commit", "tree")) and
            source["status"] == "" and source["diffSha256"] == digest(b""), "Unbound test temporary creation source")
    if case_name == "current":
        require(source["commit"] == identity["sourceSha"] and source["tree"] == identity["sourceTree"],
                "Current test temporary creation names another source")
    require(type(owner["directory"]) is str and 0 < len(owner["directory"]) <= 1024 and
            not any(char in owner["directory"] for char in "\0\r\n"), "Invalid test temporary creation path")
    path = PureWindowsPath(owner["directory"]) if PureWindowsPath(owner["directory"]).drive else PurePosixPath(owner["directory"])
    require(path.is_absolute() and ".." not in path.parts and path.parts[-2:] == ("fixtures", "jvm-tmp"),
            "Test temporary owner names another path")
    require_positive_temporary_identity(owner["nativeIdentity"])


def create_test_temporary(case, identity):
    directory = case["state"] / "fixtures/jvm-tmp"
    directory.mkdir(mode=0o700)  # Existing directories are never admitted as fresh.
    owner = {"schema": 2, "identity": identity, "source": case["context"]["source"], "caseName": case["name"],
             "jobId": case["context"]["id"], "nonce": uuid.uuid4().hex, "directory": str(directory),
             "createdUtc": audit.utc(), "nativeIdentity": identified_test_temporary(directory)}
    validate_test_temporary_owner(owner, identity, case["name"])
    path = directory.parent / "jvm-tmp-owner.json"
    new_json(path, owner)
    case.update(testTemporaryOwner=owner, testTemporaryOwnerSha256=digest(regular(path, 65536)))
    copy_public(path, case["public"] / "temporary-owner.json")


def validate_test_temporary(value, owner, owner_hash, phase):
    require(type(value) is dict and set(value) == {"schema", "kind", "phase", "identity", "source", "caseName",
        "jobId", "nonce", "leaf", "directory", "expectedRootIdentity", "startedUtc", "endedUtc", "rootBefore", "rootAfter",
        "entries", "errors", "complete", "empty", "temporaryOwnerSha256", "observedOwnerSha256", "ownerError", "ownerUnchanged"} and
        integer(value["schema"], 2) and value["kind"] == "windows-test-temporary-metadata" and
        phase in ("before", "after") and value["phase"] == phase and
        all(value[key] == owner[key] for key in ("identity", "source", "caseName", "jobId", "nonce", "directory")) and
        value["expectedRootIdentity"] == owner["nativeIdentity"] and value["temporaryOwnerSha256"] == owner_hash and
        owner_hash == digest(audit.json_bytes(owner)), "Wrong test temporary observation binding")
    require_positive_temporary_identity(value["expectedRootIdentity"])
    validate_temporary_metadata(value, "jvm-tmp")
    require((value["observedOwnerSha256"] is None or type(value["observedOwnerSha256"]) is str and
                re.fullmatch(r"[0-9a-f]{64}", value["observedOwnerSha256"])) and
            (value["ownerError"] is None or type(value["ownerError"]) is str and
                re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", value["ownerError"])) and
            (value["observedOwnerSha256"] is None) == (value["ownerError"] is not None) and
            type(value["ownerUnchanged"]) is bool and value["ownerUnchanged"] == (value["observedOwnerSha256"] == owner_hash),
            "Malformed test temporary owner observation")
    leaf = value["leaf"]
    require(phase == "after" or leaf is None, "Before observation cannot claim a completed Test leaf")
    if leaf is not None:
        require(type(leaf) is dict and set(leaf) == {"id", "purpose", "status", "valid", "retained"} and
                type(leaf["id"]) is str and re.fullmatch(HEX32, leaf["id"]) and leaf["purpose"] == "product" and
                (leaf["status"] is None or type(leaf["status"]) is int) and
                type(leaf["valid"]) is bool and type(leaf["retained"]) is bool, "Invalid Test leaf observation")
    require(len(audit.json_bytes(value)) <= NATIVE_TEMP_BYTES, "Test temporary metadata exceeds its byte bound")


def test_temporary_ok(value):
    return value["complete"] is True and value["empty"] is True and value["ownerUnchanged"] is True


def validate_public_test_temporary(directory, identity, case_name, rows):
    names = {row["path"] for row in rows} & {"temporary-owner.json", "temporary-before.json", "temporary-after.json"}
    if not names:
        return
    require(case_name in ("current", "preimage") and "temporary-owner.json" in names,
            "Test temporary observations lack their retained creation owner")
    owner_raw = regular(directory / "temporary-owner.json", 65536)
    owner = read_json(directory / "temporary-owner.json")
    validate_test_temporary_owner(owner, identity, case_name)
    require(owner_raw == audit.json_bytes(owner), "Noncanonical temporary creation owner")
    for phase in ("before", "after"):
        name = "temporary-" + phase + ".json"
        if name in names:
            require(len(regular(directory / name, NATIVE_TEMP_BYTES)) <= NATIVE_TEMP_BYTES, "Unbounded test temporary observation")
            validate_test_temporary(read_json(directory / name), owner, digest(owner_raw), phase)


def native_worker_file(path, limit):
    """Post-stop ordinary-file snapshot, NOT a hostile replace/restore pin."""
    audit.reject_symlinks(path)
    before = path.lstat()
    raw = regular(path, limit)
    audit.reject_symlinks(path)
    after = path.lstat()
    require(os.path.samestat(before, after) and native_temporary_metadata(before) == native_temporary_metadata(after) and
            native_temporary_kind(after.st_mode, getattr(after, "st_file_attributes", None)) == "file" and
            after.st_nlink == 1 and len(raw) > 0, "Worker file changed during native retention")
    return raw, {"path": str(path), "bytes": len(raw), "sha256": digest(raw), "stat": native_temporary_metadata(after)}


def validate_worker_native_record(value, path, limit):
    require(type(value) is dict and set(value) == {"path", "bytes", "sha256", "stat"} and value["path"] == path and
            integer(value["bytes"]) and 0 < value["bytes"] <= limit and type(value["sha256"]) is str and
            re.fullmatch(r"[0-9a-f]{64}", value["sha256"]), "Invalid native worker file binding")
    info = value["stat"]
    require(type(info) is dict and set(info) == {"device", "inode", "birthNs", "mode", "links", "bytes", "modifiedNs",
            "changedNs", "fileAttributes", "reparseTag", "kind"} and
            all(item is None and key in ("birthNs", "fileAttributes", "reparseTag") or
                integer(item) and (-2 ** 127 if key in ("birthNs", "modifiedNs", "changedNs") else 0) <= item < 2 ** 128
                for key, item in info.items() if key != "kind") and
            info["device"] > 0 and info["inode"] > 0 and info["links"] == 1 and info["bytes"] == value["bytes"] and
            info["kind"] == native_temporary_kind(info["mode"], info["fileAttributes"]) == "file" and
            info["reparseTag"] in (None, 0), "Native worker file is linked, nonregular or lacks its identity")


def validate_worker_retention(value, request, request_hash, capture, capture_hash, expansion):
    require(type(value) is dict and set(value) == {"schema", "requestSha256", "captureSha256", "leafId", "phase",
            "observedMillis", "status", "reason", "original", "snapshot", "bootstrap"} and integer(value["schema"], 1) and
            value["requestSha256"] == request_hash and value["captureSha256"] == capture_hash and
            (value["leafId"] is None or type(value["leafId"]) is str and re.fullmatch(HEX32, value["leafId"])) and
            value["phase"] == "controller-after-stop" and integer(value["observedMillis"]) and
            0 < value["observedMillis"] < 2 ** 63 and
            (value["status"] == "QUALIFIED" and value["reason"] is None or
             value["status"] == "REFUSED" and type(value["reason"]) is str and value["reason"] in WORKER_RETENTION_REASONS),
            "Invalid worker post-stop retention witness")
    paths = {"original": capture["original"]["path"] if capture and capture["original"] else None,
             "snapshot": request["outputDirectory"] + "\\worker-classpath.raw",
             "bootstrap": expansion["bootstrap"]["path"] if expansion else None}
    for key, path in paths.items():
        if value[key] is not None:
            require(path is not None, "Native worker record has no admitted original path")
            validate_worker_native_record(value[key], path, 4 * 1024 * 1024 if key == "bootstrap" else WORKER_BYTES)
    if value["status"] == "QUALIFIED":
        require(capture is not None and capture["status"] == "CAPTURED" and value["leafId"] is not None and
                all(value[key] is not None for key in paths) and value["observedMillis"] >= capture["observedMillis"] and
                all(value[key][field] == capture["original"][field] for key in ("original", "snapshot")
                    for field in ("bytes", "sha256")) and
                all(value["bootstrap"][field] == expansion["bootstrap"][field] for field in ("bytes", "sha256")),
                "Qualified worker retention lacks unchanged original/snapshot/bootstrap evidence")


def worker_receipt_time(value):
    require(type(value) is str and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?\+00:00", value),
        "Invalid worker leaf UTC boundary")
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def worker_leaf_binding(receipt, request, retained, envelope, capture, execution):
    require(receipt.get("id") == retained["leafId"] and receipt.get("purpose") == "product" and
            receipt.get("host") == "windows-x64" and receipt.get("sourceBefore") == receipt.get("sourceAfter") == request["source"] and
            receipt.get("sourceUnchanged") is True and integer(receipt.get("stopExitCode"), 0) and
            receipt.get("ownedSurvivors") == receipt.get("errors") == [] and
            worker_receipt_time(receipt.get("productStartedUtc")) <= envelope["admission"]["observedMillis"] <=
            capture["observedMillis"] <= execution["finishedMillis"] <= worker_receipt_time(receipt.get("productEndedUtc")) <=
            worker_receipt_time(receipt.get("stopStartedUtc")) <= worker_receipt_time(receipt.get("stopEndedUtc")) <=
            worker_receipt_time(receipt.get("endedUtc")) <= retained["observedMillis"],
            "Worker capture/native retention do not bracket the original product/stop leaf")


def validate_public_worker_expansion(directory, identity, case_name, rows):
    names = {row["path"] for row in rows}
    envelope = read_json(directory / "test-admission.json") if "test-admission.json" in names else None
    execution = read_json(directory / "execution.json") if "execution.json" in names else None
    extended = any(type(report) is dict and type(report.get("admission")) is dict and
                   "workerExpansion" in report["admission"] for report in (envelope, execution))
    if not names & WORKER_FILES and not extended:
        return
    require(case_name in ("current", "preimage") and "request.json" in names, "Worker evidence lacks its case request")
    request_raw = regular(directory / "request.json")
    request, request_hash = read_json(directory / "request.json"), digest(request_raw)
    require(request.get("identity") == identity and request.get("caseName") == case_name, "Foreign worker evidence request")
    for key in ("root", "state", "java17", "java21", "testTemporary", "outputDirectory"):
        worker_path(request.get(key), logged=True)
    expansion, admission_hash = None, None
    for report in (envelope, execution):
        if type(report) is dict and type(report.get("admission")) is dict and "workerExpansion" in report["admission"]:
            worker_expected(report["admission"]["workerExpansion"], request)  # Safe finite metadata, even on failure.
    if envelope is not None:
        require(type(envelope.get("admission")) is dict, "Malformed retained worker admission")
        admission_hash = digest(regular(directory / "test-admission.json"))
        expansion = envelope.get("admission", {}).get("workerExpansion")
    capture, capture_hash = None, None
    if "worker-classpath.json" in names:
        capture = read_json(directory / "worker-classpath.json")
        assess_worker_capture(capture, request, request_hash, admission_hash, expansion)
        capture_hash = digest(regular(directory / "worker-classpath.json"))
    retained = None
    if "worker-classpath-retention.json" in names:
        retained = read_json(directory / "worker-classpath-retention.json")
        validate_worker_retention(retained, request, request_hash, capture, capture_hash, expansion)
    if "worker-classpath.args" in names or retained is not None and retained["status"] == "QUALIFIED":
        require("worker-classpath.args" in names and retained is not None and retained["status"] == "QUALIFIED" and
                capture is not None and expansion is not None, "Public worker bytes lack qualified native retention")
        expected = worker_observation(execution, envelope, capture, request, request_hash)
        raw = regular(directory / "worker-classpath.args", WORKER_BYTES)
        require(raw == expected and len(raw) == capture["original"]["bytes"] and digest(raw) == capture["original"]["sha256"],
                "Public worker bytes differ from the authorized original expansion")
        assess_worker_log(regular(directory / "product/product.stdout.log"), request, envelope["admission"], capture["original"]["path"])
        receipt = read_json(directory / "product/receipt.json")
        worker_leaf_binding(receipt, request, retained, envelope, capture, execution)


def retain_worker_report(source, destination, request):
    if audit.existing_lstat(source) is not None:
        value = read_json(source)
        admission = value.get("admission")
        require(type(admission) is dict, "Malformed observer admission is not public evidence")
        if "workerExpansion" in admission:
            worker_expected(admission["workerExpansion"], request)
        retain_available(source, destination)


def retain_worker_expansion(output, public, request, request_hash, leaf):
    """Retain safe originals on red/green paths; never upload an unknown raw file.

    Refusal retains source/cache inputs through the existing retention barrier.
    An ephemeral hosted job is not a promise of durable private acquisition.
    """
    envelope = read_json(public / "test-admission.json") if (public / "test-admission.json").exists() else None
    require(envelope is None or type(envelope.get("admission")) is dict, "Malformed retained worker admission")
    expansion = envelope.get("admission", {}).get("workerExpansion") if envelope else None
    if expansion is None and not any(audit.existing_lstat(output / name) is not None for name in
                                     ("worker-classpath.json", "worker-classpath.raw")):
        return  # No admitted selected Test: do not fabricate a capture.
    path = public / "worker-classpath-retention.json"
    if audit.existing_lstat(path) is not None:
        validate_public_worker_expansion(public, request["identity"], request["caseName"], inventory(public))
        record = read_json(path)
        require(record["status"] == "QUALIFIED", "Worker retention was refused; preserve original private inputs")
        for key in ("original", "snapshot", "bootstrap"):
            _, observed = native_worker_file(Path(record[key]["path"]), 4 * 1024 * 1024 if key == "bootstrap" else WORKER_BYTES)
            require(observed == record[key], "Native worker inputs changed after retention")
        return record
    record = {"schema": 1, "requestSha256": request_hash, "captureSha256": None,
              "leafId": leaf["id"] if leaf else None, "phase": "controller-after-stop",
              "observedMillis": int(time.time() * 1000), "status": "REFUSED", "reason": "CAPTURE_MISSING",
              "original": None, "snapshot": None, "bootstrap": None}
    capture = None
    try:
        require(audit.existing_lstat(output / "worker-classpath.json") is not None, "Worker capture absent")
        record["reason"] = "CAPTURE_INVALID"
        candidate = read_json(output / "worker-classpath.json")
        assess_worker_capture(candidate, request, request_hash,
            digest(regular(public / "test-admission.json")) if envelope else None, expansion)
        retain_available(output / "worker-classpath.json", public / "worker-classpath.json")
        capture = candidate
        record["captureSha256"] = digest(regular(public / "worker-classpath.json"))
        record["reason"] = "ADMISSION_MISSING"
        require(expansion is not None, "No worker admission")
        worker_expected(expansion, request)
        record["reason"] = "CAPTURE_REFUSED"
        require(capture["status"] == "CAPTURED", "Worker before-stop capture refused")
        record["reason"] = "LEAF_UNFINALIZED"
        require(leaf is not None and leaf["valid"] and leaf["retained"], "No finalized original product/stop leaf")
        record["reason"] = "EXECUTION_INVALID"
        execution = read_json(public / "execution.json")
        expected = worker_observation(execution, envelope, capture, request, request_hash)
        worker_leaf_binding(read_json(public / "product/receipt.json"), request, record, envelope, capture, execution)
        record["reason"] = "SNAPSHOT_INVALID"
        raw, record["snapshot"] = native_worker_file(output / "worker-classpath.raw", WORKER_BYTES)
        require(all(record["snapshot"][key] == capture["original"][key] for key in ("bytes", "sha256")),
                "Captured snapshot changed")
        record["reason"] = "EXPANSION_MISMATCH"
        require(raw == expected, "Captured worker content differs")
        record["reason"] = "LAUNCH_MISMATCH"
        assess_worker_log(regular(public / "product/product.stdout.log"), request, envelope["admission"], capture["original"]["path"])
        record["reason"] = "ORIGINAL_INVALID"
        original, record["original"] = native_worker_file(Path(capture["original"]["path"]), WORKER_BYTES)
        require(original == raw, "Original worker bytes changed after stop")
        record["reason"] = "BOOTSTRAP_INVALID"
        _, record["bootstrap"] = native_worker_file(Path(expansion["bootstrap"]["path"]), 4 * 1024 * 1024)
        require(all(record["bootstrap"][key] == expansion["bootstrap"][key] for key in ("bytes", "sha256")),
                "Worker bootstrap changed after stop")
        record["reason"] = "PUBLIC_COPY_FAILED"
        # Write the already-read, validated ORIGINAL bytes, not a second unvalidated
        # read and not a rendering substituted for absent original evidence.
        write(public / "worker-classpath.args", raw)
        require(regular(public / "worker-classpath.args", WORKER_BYTES) == raw, "Worker public copy changed")
        record.update(status="QUALIFIED", reason=None)
    except Exception:
        pass  # Finite stage only; original product failure remains primary in product.finally.
    validate_worker_retention(record, request, request_hash, capture, record["captureSha256"], expansion)
    new_json(path, record)
    validate_public_worker_expansion(public, request["identity"], request["caseName"], inventory(public))
    require(record["status"] == "QUALIFIED", "Worker retention refused; preserve original private inputs")
    return record


def native_predicates(text, count, temporary):
    return {"expected-test-count-and-OK": bool(re.search(r"\nRan " + str(count) + r" tests? in [0-9.]+s\r?\n\r?\nOK\r?\n", text)),
            "current-Windows-marker": "Running current-host real executor fixtures: windows-x64;" in text,
            "no-skipped-marker": "skipped=" not in text,
            "native-temporary-root-empty": temporary["complete"] is True and temporary["empty"] is True}


def validate_public_native_temporary(directory, identity, case_name, rows):
    observed = []
    for row in rows:
        phase = NATIVE_TEMP_FILES.get(row["path"])
        if phase is not None:
            require(case_name == "admission" and row["bytes"] <= NATIVE_TEMP_BYTES,
                    "Native temporary metadata is outside its bounded admission location")
            value = read_json(directory / row["path"])
            validate_native_temporary(value, identity, phase)
            observed.append(value)
    if len(observed) == 2:
        require(all(observed[0][key] == observed[1][key] for key in
                    ("jobId", "source", "directory", "expectedRootIdentity")), "Native temporary observations differ in owner/source")


def expected_native_count(raw):
    tree = ast.parse(raw)
    classes = {node.name: {child.name for child in node.body if isinstance(child, ast.FunctionDef) and
                           child.name.startswith("test_")} for node in tree.body if isinstance(node, ast.ClassDef)}
    return len(classes["PurePolicyTests"]) + len(classes["DarwinObservationTests"]) + len(
        classes["ExecutorFixtureTests"] | classes["WindowsNativeTests"])


def assess_native_cleanup(directory, raw):
    tree = ast.parse(raw)
    methods = {child.name for node in tree.body if isinstance(node, ast.ClassDef) and
               node.name in ("ExecutorFixtureTests", "WindowsNativeTests") for child in node.body
               if isinstance(child, ast.FunctionDef) and child.name.startswith("test_")}
    require({path.name for path in directory.iterdir()} == methods, "Missing/extra native fixture evidence")
    observations = []
    for name in sorted(methods):
        case = read_json(directory / name / "case.json")
        initialized = read_json(directory / name / "init.json")
        require(integer(initialized.get("exitCode"), 0) and initialized.get("source") == case.get("source") and
                initialized.get("state") == case.get("state"), "Native fixture init did not succeed")
        attempts = []
        for parent in (directory / name).iterdir():
            if not re.fullmatch("teardown-" + HEX32, parent.name):
                continue
            record = read_json(parent / "cleanup.json")
            require(integer(record.get("schema"), 1) and record.get("kind") == "executor-fixture-cleanup" and
                    record.get("id") == parent.name[len("teardown-"):] and record.get("state") == case["state"] and
                    window_path(record.get("fixtureBase")) == window_path(case["source"]).parent and
                    type(record.get("startedUtc")) is str and type(record.get("endedUtc")) is str,
                    "Native fixture cleanup binding differs")
            attempts.append(record)
        require(attempts, "Native fixture final cleanup is absent")
        attempts.sort(key=lambda row: row["startedUtc"])
        final = attempts[-1]
        require(final.get("cleanupComplete") is True and final.get("fixtureDataRemoved") is True and
                final.get("errors") == [] and final.get("guardSurvivors") == [] and
                type(final.get("sentinels")) is list and
                all(type(row) is dict and row.get("survivors") == [] for row in final["sentinels"]),
                "Native fixture retirement is unknown or failed")
        guard = read_json(directory / name / ("teardown-" + final["id"]) / "guard.json")
        require(guard.get("backend") == "windows-job-list-suspended" and guard.get("discoveryErrors") == [],
                "Native fixture final guard is not genuine Windows retirement")
        # Exactly this maintained adverse case deliberately emits a failed
        # teardown before its separately recorded real recovery. Keep both.
        expected_attempts = 2 if name == "test_cleanup_failures_still_archive_authentic_receipts_and_preserve_unresolved_fixture" else 1
        require(len(attempts) == expected_attempts and all(row.get("cleanupComplete") is False and row.get("errors")
                for row in attempts[:-1]), "Unexpected native teardown/recovery history")
        observations.append({"test": name, "attemptIds": [row["id"] for row in attempts],
                             "finalCleanupId": final["id"], "cleanupComplete": True})
    return observations


def native_public_path(name):
    """Finite writers in the maintained Windows suite, not an arbitrary *.json glob."""
    if name == NATIVE_DIRECTORY_POLICY_MARKER:
        return True
    parts = PurePosixPath(name).parts
    if len(parts) < 2 or not re.fullmatch(r"test_[a-z0-9_]+", parts[0]):
        return False
    if len(parts) == 2:
        return parts[1] in {"case.json", "init.json", "init.stdout.log", "init.stderr.log",
                            "preexisting-project-context.json", "cross-context-proof.json", "nested-directory-metadata.json"}
    if re.fullmatch("controller-" + HEX32, parts[1]):
        return len(parts) == 3 and parts[2] in {"start.json", "completion.json", "stdout.log", "stderr.log"}
    if not re.fullmatch("teardown-" + HEX32, parts[1]):
        return False
    if len(parts) == 3:
        return parts[2] in {"context.json", "fixture-calls.jsonl", "guard.json", "cleanup.json",
                            "cleanup-before-disposal.json", "cleanup-failure.json"}
    if parts[2] != "invocations":
        return False
    if len(parts) == 4:
        return bool(re.fullmatch(r"cleanup-" + HEX32 + r"(?:-start|-readonly-[1-9][0-9]*-start)?\.json", parts[3])) or \
            parts[3] in {"BUILD_COMMIT.txt", "BUILD_SOURCE_STATE.txt", "BUILD_INPUTS_SHA256.txt",
                         "BUILD_ARTIFACTS_SHA256.txt", "xcframework-sidecars.json"}
    if not re.fullmatch(HEX32, parts[3]):
        return False
    if len(parts) == 5:
        return parts[4] in LEAF_FILES
    return parts[4:] in (("reports", "build", "test-results", "fixture", "result.xml"),
        ("reports", "external", "work", "consumer", "consumer", "build", "test-results", "fixture", "result.xml"))


def inventory(directory, *, byte_limit=MAX_BYTES, entry_limit=MAX_FILES):
    audit.reject_symlinks(directory)
    root = directory.lstat()
    require(stat.S_ISDIR(root.st_mode), "Control inventory root is not physical")
    pending, rows, total, entries = [(directory, 0)], [], 0, 0
    while pending:
        parent, depth = pending.pop()
        require(depth <= 64, "Control evidence depth exceeds its bound")
        with os.scandir(parent) as iterator:
            for entry in iterator:
                entries += 1
                require(entries <= entry_limit, "Control inventory entry limit exceeded")
                path = Path(entry.path)
                audit.reject_symlinks(path)
                info = path.lstat()  # Windows DirEntry device fields are not authoritative.
                require(info.st_dev == root.st_dev, "Control inventory crossed a volume")
                if stat.S_ISDIR(info.st_mode):
                    pending.append((path, depth + 1))
                else:
                    value = regular(path)
                    total += len(value)
                    require(total <= byte_limit, "Control inventory byte limit exceeded")
                    rows.append({"path": path.relative_to(directory).as_posix(), "bytes": len(value), "sha256": digest(value)})
    return sorted(rows, key=lambda row: row["path"])


def public_path(name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name and ".." not in path.parts and
            all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in path.parts), "Unsafe public evidence member")
    if len(path.parts) == 1:
        return name in {"start.json", "outcome.json", "tools.json", "source-before.json", "source-after.json",
                        "source.kt", "test.kt", "transform.json", "transform.patch", "derivative-commit.txt",
                        "context.json", "gradle.properties", "request.json", "temporary-owner.json", "temporary-before.json",
                        "temporary-after.json", "retirement-start.json", "retirement.json", "controller-error.txt",
                        "native-controls.json", "test-admission.json", "execution.json", "buildsrc-execution.json",
                        "worker-classpath.json", "worker-classpath-retention.json", "worker-classpath.args",
                        "native-temporary-before.json", "native-temporary-after.json",
                        "binding-controls.json", "binding-controls-unbound.json",
                        "TEST-control.xml", "TEST-control-unbound.xml", "unbound-report.json",
                        "sdk.json", "sdk-tool-before.json", "sdk-tool-after.json", "allocation.json", "retained-before-disposal.json",
                        "source-materialization.json", "controller-retirement.json", "fallback-stop.json", "BuildInfo.kt"}
    if path.parts[0] == "native-controls":
        return native_public_path("/".join(path.parts[1:]))
    if len(path.parts) == 3 and path.parts[0] == "commands":
        return bool(re.fullmatch(r"[1-9][0-9]*-(?:git|source-clone|source-archive|init|java17|java21|wrapper-version|sdk-install|executor-native-controls|binding-controls|product|fallback-stop)",
                                 path.parts[1])) and path.parts[2] in {"start.json", "command.json", "stdout.log", "stderr.log"}
    if len(path.parts) == 2 and path.parts[0] == "readonly-recovery":
        return bool(re.fullmatch(HEX32 + r"-(?:start|outcome)\.json", path.parts[1]))
    if len(path.parts) == 2 and path.parts[0] in {"java17", "java21", "init"}:
        return path.parts[1] in {"command.json", "stdout.log", "stderr.log"}
    if len(path.parts) == 2 and path.parts[0] in {"wrapper-version", "sdk-install", "executor-native-controls", "binding-controls", "product"}:
        return path.parts[1] in LEAF_FILES | {"controller.json", "controller.stdout.log", "controller.stderr.log"}
    return False


def public_manifest(identity, case_name, rows):
    return {"schema": 1, "identity": identity, "caseName": case_name, "files": rows,
            "scope": "synthetic local-filesystem witness; no private/device/payload evidence or full-gate claim"}


def seal_public(directory, identity, case_name):
    rows = inventory(directory)
    require(rows and all(public_path(row["path"]) for row in rows), "Unaudited public evidence member")
    validate_public_native_temporary(directory, identity, case_name, rows)
    validate_public_test_temporary(directory, identity, case_name, rows)
    validate_public_worker_expansion(directory, identity, case_name, rows)
    manifest = public_manifest(identity, case_name, rows)
    new_json(directory / "manifest.json", manifest)
    require(inventory(directory) == sorted(rows + [{"path": "manifest.json",
        "bytes": (directory / "manifest.json").stat().st_size, "sha256": digest(regular(directory / "manifest.json"))}],
        key=lambda row: row["path"]), "Public evidence changed while sealing")
    return digest(regular(directory / "manifest.json"))


def verify_public(directory, identity, case_name):
    rows = inventory(directory)
    actual = [row for row in rows if row["path"] != "manifest.json"]
    require(regular(directory / "manifest.json") == audit.json_bytes(public_manifest(identity, case_name, actual)) and
            actual and all(public_path(row["path"]) for row in actual),
            "Missing, changed, extra or unsafe sealed public artifact member")
    validate_public_native_temporary(directory, identity, case_name, actual)
    validate_public_test_temporary(directory, identity, case_name, actual)
    validate_public_worker_expansion(directory, identity, case_name, actual)


def copy_public(source, destination, *, expected=None):
    value = regular(source, MAX_FILE if expected is None else len(expected))
    require(expected is None or value == expected, "Public synthetic marker differs from its reviewed bytes")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    write(destination, value)
    require(regular(destination) == value, "Public retention differs from its original")


def retain_available(source, destination):
    if audit.existing_lstat(source) is not None:
        if audit.existing_lstat(destination) is None:
            copy_public(source, destination)
        else:
            require(regular(destination) == regular(source), "Existing retained original changed or was truncated")


def retain_before_disposal(directory, identity, case_name):
    rows = inventory(directory)
    require(rows and all(public_path(row["path"]) for row in rows), "Unsafe retention prevents disposable cleanup")
    validate_public_native_temporary(directory, identity, case_name, rows)
    validate_public_test_temporary(directory, identity, case_name, rows)
    validate_public_worker_expansion(directory, identity, case_name, rows)
    value = {"schema": 1, "identity": identity, "caseName": case_name, "files": rows}
    new_json(directory / "retained-before-disposal.json", value)
    return value


def verify_before_disposal(directory, expected):
    require(regular(directory / "retained-before-disposal.json") == audit.json_bytes(expected), "Pre-disposal manifest changed")
    rows = {row["path"]: row for row in inventory(directory)}
    require(all(public_path(name) for name in rows), "Unsafe public retention member before disposal")
    require(all(rows.get(row["path"]) == row for row in expected["files"]),
            "Required retained original is missing/changed before disposal")
    admitted = {row["path"] for row in expected["files"]} | {"retained-before-disposal.json", "retirement-start.json"}
    require(all(name in admitted or name.startswith("readonly-recovery/") and public_path(name) for name in rows),
            "Unexpected evidence was inserted before disposal")
    validate_public_worker_expansion(directory, expected["identity"], expected["caseName"], list(rows.values()))


def readonly_handler(root, identity, directory, record):
    """Delegate one owned-leaf retry; diagnostics may never replace unlink's error."""
    retried = set()

    def onerror(operation, entry, exception):
        original, traceback = exception[1], exception[2]
        recovered = False
        recovery_id = uuid.uuid4().hex
        attempt = {"schema": 1, "id": recovery_id, "outcome": "REFUSED",
                   "originalExceptionType": type(original).__name__}
        try:
            attempt["originalFailure"] = audit.removal_failure_detail(root, operation, entry, original)
            directory.mkdir(mode=0o700, exist_ok=True)

            def preserve():
                require(entry not in retried and len(retried) < 2000, "Readonly retry duplicate or journal bound")
                require(len(audit.json_bytes(attempt)) <= audit.MAX_REMOVAL_DETAIL_BYTES + 4096,
                        "Readonly original-failure journal exceeds its bound")
                retried.add(entry)
                new_json(directory / (recovery_id + "-start.json"), attempt)

            recovered = audit.retry_windows_readonly_unlink(root, identity, operation, entry, original, attempt, preserve)
        except Exception as error:
            attempt.update(outcome="FAILED", recoveryError=type(error).__name__)
        finally:
            try:
                record.setdefault("readonlyRecoveries", []).append(attempt)
                new_json(directory / (recovery_id + "-outcome.json"), attempt)
            except Exception:
                recovered = False  # Missing retained recovery evidence is never successful removal.
            if not recovered:
                raise original.with_traceback(traceback)
    return onerror


def controlled_environment(base):
    for key in ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
        require(not base.get(key, "").strip(), "Ambient JVM/Gradle options conflict with controlled execution")
    require(not any(key.startswith("GIT_") and key not in {"GIT_TERMINAL_PROMPT"} for key in base),
            "Ambient Git overrides must be resolved before admission")
    names = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE", "TEMP", "TMP", "TMPDIR",
             "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
             "HOME", "HOMEDRIVE", "HOMEPATH", "ALLUSERSPROFILE", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
             "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "ANDROID_HOME", "CI", "GITHUB_ACTIONS", "GITHUB_REPOSITORY",
             "GITHUB_SHA", "GITHUB_REF", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME",
             "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKSPACE", "RUNNER_OS", "RUNNER_ARCH",
             "RUNNER_ENVIRONMENT", processes.JOB_ENV, processes.CHAIN_ENV, processes.DOMAINS_ENV,
             processes.STATE_ENV, "GRADLE_USER_HOME"}
    result = {key: value for key, value in base.items() if key.upper() in names}
    result.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", GIT_TERMINAL_PROMPT="0")
    # This selection removes credentials, not inherited audit domains. The public
    # ownership API still validates every parent domain before crossing contexts.
    for key in (processes.JOB_ENV, processes.CHAIN_ENV, processes.DOMAINS_ENV, processes.STATE_ENV):
        require(result.get(key) == base.get(key), "Ownership environment was stripped")
    return result


def native_memory():
    from ctypes import wintypes
    class Memory(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                    *[(name, ctypes.c_ulonglong) for name in ("totalPhysical", "availablePhysical", "totalPageFile",
                                                             "availablePageFile", "totalVirtual", "availableVirtual", "reserved")]]
    value = Memory()
    value.length = ctypes.sizeof(value)
    api = ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx
    api.argtypes, api.restype = [ctypes.POINTER(Memory)], wintypes.BOOL
    require(api(ctypes.byref(value)) != 0, "Native memory admission unavailable")
    return {name: int(getattr(value, name)) for name in ("totalPhysical", "availablePhysical", "totalPageFile", "availablePageFile")}


def pe_amd64(path):
    with path.open("rb") as stream:
        header = stream.read(64)
        require(header[:2] == b"MZ" and len(header) == 64, "JDK executable is not PE")
        offset = struct.unpack_from("<I", header, 60)[0]
        require(64 <= offset <= 1024 ** 2, "Invalid PE header location")
        stream.seek(offset)
        pe = stream.read(6)
    require(pe[:4] == b"PE\0\0" and pe[4:] == b"\x64\x86", "JDK executable is not native AMD64")


class CommandFailure(audit.AuditError):
    def __init__(self, message, capture, status):
        super().__init__(message)
        self.capture, self.status = capture, status


class Controller:
    def __init__(self, root, identity):
        self.root, self.identity = root, identity
        self.cancelled = []
        self.handlers = {}
        self.base = audit.absolute_path(os.environ["RUNNER_TEMP"])
        require(not audit.within(self.base, root) and not audit.within(root, self.base), "Runner temporary root overlaps source")
        self.base = self.base / ("p2pkit-windows-directory-" + identity["runId"] + "-" + identity["runAttempt"] + "-" + uuid.uuid4().hex)
        self.base.mkdir(mode=0o700)
        self.public = self.base / "public"
        self.public.mkdir(mode=0o700)
        for name in ("admission", "current", "preimage"):
            (self.public / name).mkdir(mode=0o700)
        self.active_public = self.public / "admission"
        self.state = self.base / "controller-ownership"
        self.state.mkdir(mode=0o700)
        self.job, self.invocation = uuid.uuid4().hex, uuid.uuid4().hex
        self.env = processes.ownership_environment(controlled_environment(dict(os.environ)), self.job, self.invocation,
                                                   str(self.state), str(self.state / "unused-home"), allow_new_context=True)
        self.deadline = time.monotonic() + 4800
        self.final_deadline = self.deadline + 600
        self.cases = []
        self.raw = self.base / "raw"
        self.raw.mkdir(mode=0o700)
        self.counter = 0
        self.safe = False
        self.scope = processes.make_scope(self.job, self.invocation, str(self.state), self.env["GRADLE_USER_HOME"])

    def resources(self, starting=False):
        memory, disk = native_memory(), shutil.disk_usage(self.base)
        require(memory["totalPhysical"] >= 6 * GIB and memory["availablePhysical"] >= (2 * GIB if starting else 512 * 1024 ** 2),
                "Insufficient native RAM: total=" + str(memory["totalPhysical"]) + "; available=" + str(memory["availablePhysical"]))
        require(disk.free >= (10 * GIB if starting else 7 * GIB), "Insufficient disk finalization reserve: free=" + str(disk.free))
        return {"memory": memory, "disk": disk._asdict(), "observedUtc": audit.utc()}

    def command(self, argv, cwd, env, name, *, timeout=60, scope=None, cancellation=None, finalizing=False):
        """Short source/tool commands and externally monitored immutable leaf controllers."""
        scope = scope or self.scope
        self.counter += 1
        output = self.raw / (str(self.counter) + "-" + name)
        output.mkdir(mode=0o700)
        errors, streams = [], []
        interruptions = []

        def record_error(prefix, error):
            errors.append(prefix + processes.format_ownership_error(error))
            if not isinstance(error, Exception) and not interruptions:
                interruptions.append(error)

        child = None
        record = {"argv": argv, "cwd": str(cwd), "startedUtc": audit.utc(), "exitCode": None,
                  "cancelled": False, "finalizing": finalizing, "errors": errors}
        new_json(output / "start.json", record)
        deadline = min(self.final_deadline if finalizing else self.deadline, time.monotonic() + timeout)
        try:
            require(finalizing or not self.cancelled, "Controller cancelled before command start")
            require(time.monotonic() < deadline, "Command admission deadline exceeded")
            child = scope.spawn(argv, str(cwd), env)
            for pipe, name in ((child.stdout, "stdout"), (child.stderr, "stderr")):
                stream = audit.Tee(pipe, output / (name + ".log"), None, errors, False)
                streams.append(stream)
                stream.start()
            while child.poll() is None:
                scope.discover()
                require(time.monotonic() < deadline and (finalizing or not self.cancelled), "Controller deadline or cancellation")
                if not finalizing:
                    self.resources()
                require(sum((output / file).stat().st_size for file in ("stdout.log", "stderr.log")) <= MAX_FILE,
                        "Command output exceeded its retained bound")
                time.sleep(.1)
            record["exitCode"] = child.wait(timeout=5)
        except BaseException as error:
            record_error("", error)
            record["cancelled"] = bool(self.cancelled) or bool(interruptions) or "deadline" in str(error).lower()
        finally:
            if child is not None and child.poll() is None and cancellation is not None:
                try:
                    cancellation()
                    end = min(self.final_deadline, time.monotonic() + 165)
                    while child.poll() is None and time.monotonic() < end:
                        scope.discover()
                        time.sleep(.1)
                except BaseException as error:
                    record_error("Cooperative cancellation: ", error)
            try:
                # A command is complete only after its own domain has drained,
                # including a partially failed launch or an exited leader.
                record["membersBeforeDrain"] = scope.discover()
                if child is not None and child.poll() is not None and record["membersBeforeDrain"] and not errors:
                    errors.append("Unexpected command descendants remained after controller exit")
                survivors = scope.drain(grace=2, kill_wait=5)
                record["survivors"] = survivors
                require(survivors == [], "Owned command retirement is unknown")
                if child is not None:
                    record["exitCode"] = child.wait(timeout=5)
            except BaseException as error:
                record_error("Command retirement: ", error)
            for stream in streams:
                try:
                    stream.finish()
                except BaseException as error:
                    record_error("Command stream finalization: ", error)
            if child is not None:
                for pipe in (child.stdout, child.stderr):
                    if pipe is not None and not any(getattr(stream, "source", None) is pipe for stream in streams):
                        try:
                            pipe.close()  # A partially failed Tee allocation never acquired this pipe.
                        except BaseException as error:
                            record_error("Unclaimed command pipe close: ", error)
            try:
                record["ownership"] = scope.description()
                errors.extend(record["ownership"].get("discoveryErrors", []))
            except BaseException as error:
                record_error("Command ownership retention: ", error)
            record["cancelled"] = record["cancelled"] or bool(interruptions)
            record["endedUtc"] = audit.utc()
            try:
                new_json(output / "command.json", record)
            except BaseException as error:
                record_error("Command record retention: ", error)
            for file in ("start.json", "command.json", "stdout.log", "stderr.log"):
                try:
                    if audit.existing_lstat(output / file) is not None:
                        copy_public(output / file, self.active_public / "commands" / output.name / file)
                except BaseException as error:
                    record_error("Command public retention: " + file + ": ", error)
        if interruptions:
            raise interruptions[0]
        if errors or record["cancelled"]:
            raise CommandFailure("Controlled command infrastructure failed; original output retained", output, record["exitCode"])
        return record["exitCode"], output

    def git(self, root, *args, finalizing=False):
        # No global changes, checkout filters, credential copying, hooks, signing,
        # replacement objects, external diff, or arbitrary input-provided options.
        env = dict(self.env)
        command = ["git", "--no-replace-objects", "-c", "core.autocrlf=false", "-c", "core.fsmonitor=false",
                   "-c", "commit.gpgSign=false", "-c", "core.hooksPath=" + str(self.state), "-C", str(root), *args]
        code, output = self.command(command, root, env, "git", timeout=120, finalizing=finalizing)
        require(code == 0, "Source-binding Git command failed; retained original output")
        return regular(output / "stdout.log", MAX_BYTES)

    def source(self, root, commit, *, initial=False, finalizing=False):
        git = lambda *args: self.git(root, *args, finalizing=finalizing)
        require(Path(os.fsdecode(git("rev-parse", "--show-toplevel").rstrip(b"\r\n"))).resolve() == root,
                "Source root differs")
        snapshot = {"commit": git("rev-parse", "HEAD").decode().strip(),
                    "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
                    "status": git("status", "--porcelain=v1", "--untracked-files=all").decode(),
                    "diffSha256": digest(git("diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD"))}
        require(snapshot["commit"] == commit and snapshot["status"] == "" and snapshot["diffSha256"] == digest(b""),
                "Disposable source is dirty or at the wrong commit")
        require(git("rev-parse", "--is-shallow-repository").strip() == b"false", "Full source history required")
        if initial:
            require(not git("status", "--porcelain=v1", "--untracked-files=all", "--ignored").strip(),
                    "Preexisting ignored/untracked build inputs are not admitted")
        rows = {}
        for name, row in tree_entries(git("ls-tree", "-rlz", "HEAD")).items():
            raw = regular(root / name)
            require(blob_matches(raw, row),
                    "Actual tracked bytes differ from Git blobs, including clean CRLF/filter conversions")
            rows[name] = {**row, "sha256": digest(raw)}
        return {"source": snapshot, "files": rows}

    def allocate(self, name):
        require(name in ("current", "preimage") and not any(case["name"] == name for case in self.cases),
                "A case cannot reuse another case's source/state/home")
        parent, public = self.base / name, self.public / name
        self.active_public = public
        parent.mkdir(mode=0o700)
        root = parent / "source"
        root.mkdir(mode=0o700)
        info = root.lstat()
        case = {"name": name, "root": root, "parent": parent, "state": parent / "state", "public": public,
                "context": None, "scope": None, "before": None, "leaves": [], "safe": False, "started": False,
                "initialized": False, "retirementAttempted": False,
                "retentionErrors": [], "productPrepared": False, "productRetained": False,
                "nativeStarted": False, "nativeAccepted": False,
                "roots": {str(root): {"device": info.st_dev, "inode": info.st_ino}}}
        self.cases.append(case)  # Record the allocation before clone/init can fail.
        new_json(public / "allocation.json", {"schema": 1, "caseName": name, "identity": self.identity,
            "parent": str(parent), "source": str(root), "stateMustBeAbsent": str(case["state"]), "roots": case["roots"]})
        return case

    def materialize(self, case):
        root = case["root"]
        code, _ = self.command(["git", "-c", "core.autocrlf=false", "clone", "--no-local", "--no-hardlinks",
                                "--no-checkout", "--", str(self.root), str(root)], self.root, self.env,
                               "source-clone", timeout=180)
        require(code == 0, "Fresh full-history source clone failed")
        # Persist only in this newly owned clone: immutable-executor and later
        # ordinary Git callers must see the same long paths, not just this helper.
        self.git(root, "config", "--local", "core.longpaths", "true")
        require(self.git(root, "config", "--bool", "--get", "core.longpaths").strip() == b"true",
                "Owned source Git long-path policy was not established")
        commit = self.identity["sourceSha"]
        self.git(root, "update-ref", "--no-deref", "HEAD", commit)
        self.git(root, "read-tree", commit)
        entries = tree_entries(self.git(root, "ls-tree", "-rlz", commit))
        archive = case["parent"] / "source.tar"
        require(audit.existing_lstat(archive) is None, "Source transport path already exists")
        code, _ = self.command(["git", "--no-replace-objects", "-c", "core.autocrlf=false", "-C", str(root),
                               "archive", "--format=tar", "--output=" + str(archive), commit],
                              root, self.env, "source-archive", timeout=120)
        require(code == 0, "Source archive command failed")
        raw = regular(archive, MAX_BYTES)
        identity = archive.lstat()
        export_archive(raw, entries, root)
        new_json(case["public"] / "source-materialization.json", {"schema": 1, "commit": commit,
            "archiveSha256": digest(raw), "archiveBytes": len(raw), "fileCount": len(entries),
            "sourceBytes": sum(row["bytes"] for row in entries.values()), "everyBlobVerified": True})
        require(os.path.samestat(archive.lstat(), identity) and digest(regular(archive, MAX_BYTES)) == digest(raw),
                "Source transport changed before its exact disposal")
        archive.unlink()  # Disposable transport; source identity/commands are retained.

    def initialize(self, name):
        case = self.allocate(name)
        parent, root = case["parent"], case["root"]
        self.materialize(case)
        before = self.source(root, self.identity["sourceSha"], initial=True)
        public = self.public / name
        if name == "preimage":
            current, test = regular(root / SOURCE), regular(root / TEST_SOURCE)
            historical = self.git(root, "show", PRE_FIX + ":" + SOURCE)
            old_test = self.git(root, "show", PRE_FIX + ":" + TEST_SOURCE)
            require(self.git(root, "rev-parse", FIX + "^").decode().strip() == PRE_FIX,
                    "Historical fix ancestry differs from the approved preimage")
            value = transform(current, historical, test, old_test)
            # One mutable preparation, before any executor context exists. This is
            # the disposable derivative, NEVER the campaign or an admitted state.
            with (root / SOURCE).open("wb") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            blob = self.git(root, "hash-object", "-w", "--no-filters", SOURCE).decode().strip()
            self.git(root, "update-index", "--cacheinfo", "100644," + blob + "," + SOURCE)
            tree = self.git(root, "write-tree").decode().strip()
            commit = self.git(root, "-c", "user.name=Disposable Windows control", "-c", "user.email=control@example.invalid",
                              "commit-tree", tree, "-p", self.identity["sourceSha"], "-m",
                              "Test-only local method preimage for Windows directory fsync; never publish").decode().strip()
            self.git(root, "update-ref", "--no-deref", "HEAD", commit)
            after = self.source(root, commit, initial=True)
            tree_delta(before["files"], after["files"])
            require(self.git(root, "rev-parse", commit + "^").decode().strip() == self.identity["sourceSha"],
                    "Disposable commit parent is not the exact candidate")
            write(public / "transform.patch", self.git(root, "diff", "--binary", "--no-ext-diff", "--no-textconv",
                                                       self.identity["sourceSha"], commit))
            write(public / "derivative-commit.txt", self.git(root, "cat-file", "commit", commit))
            new_json(public / "transform.json", {"schema": 1, "parent": self.identity["sourceSha"],
                "commit": commit, "tree": tree, "historicalParent": PRE_FIX, "historicalFix": FIX,
                "sourcePath": SOURCE, "oldMethodSha256": digest(OLD_METHOD), "currentMethodSha256": digest(CURRENT_METHOD),
                "currentFileSha256": CURRENT_SHA, "preimageFileSha256": PREIMAGE_SHA, "testBlockSha256": TEST_BLOCK_SHA,
                "onlyTreeDelta": SOURCE, "scope": "method-preimage on current surrounding source, not the historical revision"})
            before = after
        else:
            commit = self.identity["sourceSha"]
            transform(regular(root / SOURCE), self.git(root, "show", PRE_FIX + ":" + SOURCE),
                      regular(root / TEST_SOURCE), self.git(root, "show", PRE_FIX + ":" + TEST_SOURCE))
        new_json(public / "source-before.json", before)
        copy_public(root / SOURCE, public / "source.kt")
        copy_public(root / TEST_SOURCE, public / "test.kt")
        case["before"] = before
        state = parent / "state"
        require(not state.exists(), "A source derivative cannot reuse an executor state")
        code, output = self.command([sys.executable, "-B", str(root / "scripts/run-audit-command.py"), "init", "--root", str(root),
            "--state", str(state), "--expected-commit", commit, "--host", "windows-x64"], root, self.env, "init")
        require(code == 0, "Native immutable state initialization failed")
        observed_state, context = audit.context_at(str(state))
        prepared_context(observed_state, context, case, self.env)
        require({path.name for path in state.iterdir()} == {"context.json", "gradle-home", "evidence", "cancellations"} and
                {path.name for path in (state / "gradle-home").iterdir()} == {"gradle.properties"} and
                not list((state / "evidence").iterdir()) and not list((state / "cancellations").iterdir()),
                "Initialized state contains reused or unowned execution inputs")
        bridge = uuid.uuid4().hex
        env = processes.ownership_environment(self.env, context["id"], bridge, str(state), context["gradleHome"], allow_new_context=True)
        scope = processes.make_scope(context["id"], bridge, str(state), context["gradleHome"])
        case.update(context=context, contextHash=digest(regular(state / "context.json")), scope=scope, env=env)
        home_info = Path(context["gradleHome"]).lstat()
        case["roots"][context["gradleHome"]] = {"device": home_info.st_dev, "inode": home_info.st_ino}
        fixtures = state / "fixtures"
        fixtures.mkdir(mode=0o700)
        fixture_info = fixtures.lstat()
        case["roots"][str(fixtures)] = {"device": fixture_info.st_dev, "inode": fixture_info.st_ino}
        create_test_temporary(case, self.identity)
        for child in ("native-tmp", "process-tmp"):
            (fixtures / child).mkdir(mode=0o700)
            if child == "native-tmp":
                case["nativeTemporaryIdentity"] = native_temporary_identity((fixtures / child).lstat())
        env.update(TEMP=str(fixtures / "process-tmp"), TMP=str(fixtures / "process-tmp"), TMPDIR=str(fixtures / "process-tmp"),
                   KONAN_DATA_DIR=str(state / "konan"), ANDROID_USER_HOME=str(state / "android-user"))
        for path in (state / "konan", state / "android-user"):
            path.mkdir(mode=0o700)
            info = path.lstat()
            case["roots"][str(path)] = {"device": info.st_dev, "inode": info.st_ino}
        copy_public(state / "context.json", public / "context.json")
        copy_public(Path(context["gradleHome"]) / "gradle.properties", public / "gradle.properties")
        for file in ("command.json", "stdout.log", "stderr.log"):
            copy_public(output / file, public / "init" / file)
        case["initialized"] = True
        return case

    def leaf(self, case, purpose, arguments, *, kind="gradle", timeout=1200, expected=0):
        self.resources(starting=True)
        identifier = uuid.uuid4().hex
        state, root = case["state"], case["root"]
        receipt_path = state / ("host-" + purpose + ".json")
        require(not receipt_path.exists(), "Leaf purpose/state was reused")
        command = [sys.executable, "-B", str(root / "scripts/run-audit-command.py"), "--cwd", str(root),
                   "--wrapper", str(root / "gradlew.bat"), "--id", identifier, "--purpose", purpose, "--kind", kind,
                   "--timeout", str(timeout), "--stop-timeout", "120", "--receipt", str(receipt_path), "--", *arguments]
        record = {"id": identifier, "purpose": purpose, "arguments": arguments, "kind": kind,
                  "receipt": receipt_path, "status": None, "valid": False, "retained": False}
        case["leaves"].append(record)
        case["started"] = True
        try:
            code, capture = self.command(command, root, dict(case["env"]), purpose,
                                         timeout=timeout + 150, scope=case["scope"],
                                         cancellation=lambda: audit.request_cancellation(state, case["context"]["id"], identifier))
            record["status"] = code
            record["capture"] = capture
            receipt = read_json(receipt_path)
            native_receipt(receipt, case["context"], root, arguments, purpose, code, identifier, kind)
            require(digest(regular(receipt_path)) == digest(regular(state / "evidence" / identifier / "receipt.json")),
                    "Leaf receipt copies differ")
            assess_report_manifest(receipt, read_json(state / "evidence" / identifier / "report-manifest.json"))
            record["valid"] = True
            require(code == expected, "Unexpected product exit (expected-red is not an infrastructure allowance)")
            return receipt
        except CommandFailure as error:
            record["capture"], record["status"] = error.capture, error.status
            raise
        finally:
            # Even setup/compilation/cancellation failures keep original receipts/logs.
            original_error = sys.exc_info()[1]
            retention_errors = []
            directory = state / "evidence" / identifier
            destination = case["public"] / purpose
            for file in sorted(LEAF_FILES):
                try:
                    path = directory / file
                    require(not record["valid"] or audit.existing_lstat(path) is not None,
                            "A valid leaf is missing required original " + file)
                    retain_available(path, destination / file)
                except Exception as error:
                    retention_errors.append(purpose + "/" + file + ": " + type(error).__name__ + ": " + str(error))
            if record.get("capture"):
                for source_name, name in (("command.json", "controller.json"), ("stdout.log", "controller.stdout.log"),
                                          ("stderr.log", "controller.stderr.log")):
                    try:
                        path = record["capture"] / source_name
                        require(not record["valid"] or audit.existing_lstat(path) is not None,
                                "A valid controller is missing required original " + source_name)
                        retain_available(path, destination / name)
                    except Exception as error:
                        retention_errors.append(purpose + "/" + name + ": " + type(error).__name__ + ": " + str(error))
            record["retained"] = not retention_errors
            case["retentionErrors"].extend(retention_errors)
            if retention_errors and original_error is None:
                raise audit.AuditError("Original leaf retention failed; keep disposable inputs: " + retention_errors[0])

    def admit_tools(self):
        require(processes.host_role() == "windows-x64" and sys.platform == "win32" and struct.calcsize("P") == 8,
                "Control requires genuine native Windows AMD64 Python")
        tools = {"python": {"executable": sys.executable, "version": sys.version, "nativeHost": processes.host_role()},
                 "resources": self.resources(starting=True), "imageOS": os.environ.get("ImageOS"),
                 "imageVersion": os.environ.get("ImageVersion"), "java": {}}
        for label, variable, version in (("java17", "JAVA_HOME", "17"), ("java21", "P2PKIT_AUDIT_JDK21", "21")):
            home = Path(self.env.get(variable, "")).resolve(strict=True)
            require(home.is_absolute() and home.is_dir(), "Missing native JDK home")
            for executable in ("java.exe", "javac.exe"):
                pe_amd64(home / "bin" / executable)
            code, output = self.command([str(home / "bin/java.exe"), "-XshowSettings:properties", "-version"],
                                        self.root, self.env, label)
            text = (regular(output / "stdout.log") + regular(output / "stderr.log")).decode("utf-8", errors="strict")
            # Match Windows line endings without rewriting the original captured evidence.
            text = text.replace("\r\n", "\n")
            require(code == 0 and re.search(r"^\s*os\.arch = amd64\s*$", text, re.M) and
                    re.search(r"^\s*os\.name = Windows[^\r\n]*$", text, re.M) and
                    re.search(r"^\s*java\.version = " + version + r"\.[^\r\n]+$", text, re.M),
                    "Actual native Java process version/architecture differs")
            tools["java"][label] = {"home": str(home), "javaSha256": audit.file_digest(home / "bin/java.exe"),
                                      "javaReleaseSha256": audit.file_digest(home / "release")}
            for file in ("command.json", "stdout.log", "stderr.log"):
                copy_public(output / file, self.public / "admission" / label / file)
            self.env[variable] = str(home)
        new_json(self.public / "admission/tools.json", tools)

    def sdk_and_native(self, case):
        self.leaf(case, "wrapper-version", ["--version"], timeout=600)
        sdk = Path(case["env"].get("ANDROID_HOME", "")).resolve(strict=True)
        require(sdk.is_absolute() and sdk.is_dir(), "Actual Android SDK is unavailable")
        obsolete = os.environ.get("ANDROID_SDK_ROOT")
        require(not obsolete or Path(obsolete).resolve(strict=True) == sdk, "Conflicting Android SDK roots")
        manager = sdk / "cmdline-tools/latest/bin/sdkmanager.bat"
        require(manager.is_file(), "Actual sdkmanager is unavailable")
        before = sdk_tool_snapshot(sdk)
        new_json(self.public / "admission/sdk-tool-before.json", before)
        # NUL stdin: this never accepts a license prompt. A missing owner-approved
        # SDK/license is a setup blocker, not permission to manufacture metadata.
        try:
            self.leaf(case, "sdk-install", [str(manager), "--sdk_root=" + str(sdk),
                                            "platforms;android-36", "platforms;android-37.0"], kind="command", timeout=900)
        finally:
            original_error = sys.exc_info()[1]
            after = {"schema": 1, "files": None, "unchanged": False, "errors": []}
            try:
                after.update(sdk_tool_snapshot(sdk))
                after["unchanged"] = after["files"] == before["files"]
                require(after["unchanged"], "SDK launcher/package metadata changed during installation")
            except Exception as error:
                after["errors"].append(type(error).__name__)
            try:
                new_json(self.public / "admission/sdk-tool-after.json", after)
            except Exception as error:
                after["errors"].append("Snapshot retention: " + type(error).__name__)
            case["retentionErrors"].extend("SDK tool binding: " + error for error in after["errors"])
            if after["errors"] and original_error is None:
                raise audit.AuditError("SDK tool binding/retention failed; preserve disposable inputs")
        platforms = {}
        for name, api in (("android-36", "36"), ("android-37.0", "37.0")):
            raw = regular(sdk / "platforms" / name / "source.properties")
            matches = re.findall(r"^AndroidVersion\.ApiLevel\s*=\s*([^\r\n]+)\s*$", raw.decode(), re.M)
            require(matches == [api], "Compile SDK metadata is not literally the supported platform")
            platforms[name] = {"api": api, "sourcePropertiesSha256": digest(raw), "content": raw.decode()}
        new_json(self.public / "admission/sdk.json", platforms)
        self.native_controls(case)

    def native_temporary(self, case, phase):
        require(case["name"] == "current" and phase in ("before", "after"), "Unexpected native temporary observation case")
        leaf = next((row for row in case["leaves"] if row["purpose"] == "executor-native-controls"), None)
        deadline = self.final_deadline if phase == "after" else self.deadline
        record = observe_native_temporary(case["state"] / "fixtures/native-tmp", case["nativeTemporaryIdentity"],
                                           min(deadline, time.monotonic() + 5))
        record.update(schema=1, kind="windows-native-temporary-metadata", phase=phase, identity=self.identity,
                      source=case["context"]["source"], caseName=case["name"], jobId=case["context"]["id"],
                      leaf={key: leaf[key] for key in ("id", "purpose", "status", "valid", "retained")} if leaf else None)
        validate_native_temporary(record, self.identity, phase)
        new_json(self.public / "admission" / ("native-temporary-" + phase + ".json"), record)
        return record

    def native_controls(self, case):
        native = case["state"] / "evidence/native-controls"
        temporary = case["state"] / "fixtures/native-tmp"
        try:
            before = self.native_temporary(case, "before")
            require(before["complete"] and before["empty"], "Native temporary precondition failed; preserve the metadata observation")
        except Exception as error:
            case["retentionErrors"].append("Native temporary precondition: " + type(error).__name__)
            raise
        case["nativeStarted"] = True
        rows, after = [], None
        try:
            self.leaf(case, "executor-native-controls", [sys.executable, "-B", "scripts/tests/run-audit-command-test.py",
                "--expected-host", "windows-x64", "--evidence-dir", str(native), "--fixture-parent", str(temporary)],
                kind="command", timeout=1800)
        finally:
            # The leaf has attempted its original same-home stop/retention before
            # either independent boundary below. Never replace its original failure.
            original_error = sys.exc_info()[1]
            retention_errors = []
            try:
                after = self.native_temporary(case, "after")
            except Exception as error:
                retention_errors.append("Native temporary post-observation retention: " + type(error).__name__)
            try:
                if audit.existing_lstat(native) is not None:
                    rows = inventory(native)
                    require(all(native_public_path(row["path"]) for row in rows),
                            "Native fixture evidence contains an unaudited public member; retain originals and stop")
                    for row in rows:
                        expected = NATIVE_DIRECTORY_POLICY_BYTES if row["path"] == NATIVE_DIRECTORY_POLICY_MARKER else None
                        copy_public(native / row["path"], self.public / "admission/native-controls" / row["path"],
                                    expected=expected)
            except Exception as error:
                retention_errors.append("Native fixture evidence retention: " + type(error).__name__)
            case["retentionErrors"].extend(retention_errors)
            if retention_errors and original_error is None:
                raise audit.AuditError("Native diagnostic/original retention failed; preserve disposable inputs: " + retention_errors[0])
        logs = case["public"] / "executor-native-controls"
        text = (regular(logs / "product.stdout.log") + regular(logs / "product.stderr.log")).decode("utf-8", errors="strict")
        count = expected_native_count(regular(case["root"] / "scripts/tests/run-audit-command-test.py"))
        predicates = native_predicates(text, count, after)
        require(all(predicates.values()), "Native acceptance failed: " + ", ".join(name for name, passed in predicates.items() if not passed))
        cleanups = assess_native_cleanup(native, regular(case["root"] / "scripts/tests/run-audit-command-test.py"))
        new_json(self.public / "admission/native-controls.json", {"schema": 1, "count": count, "exitCode": 0,
            "command": case["leaves"][-1]["arguments"], "files": rows, "fixtureCleanup": cleanups, "predicates": predicates,
            "scope": "actual current-host executor controls, not product/library acceptance"})
        case["nativeAccepted"] = True

    def binding_controls(self, case):
        require(case["name"] == "current" and case["nativeAccepted"], "Binding controls require actual native admission")
        root, state = case["root"], case["state"]
        fixture = state / "fixtures/directory-binding"
        fixture.mkdir(mode=0o700)
        (fixture / "gradle").mkdir(mode=0o700)
        sources = {name: root / BINDING_FIXTURE / name for name in ("settings.gradle", "build.gradle")}
        sources["gradle/gradle-daemon-jvm.properties"] = root / "gradle/gradle-daemon-jvm.properties"
        hashes = {"observer": digest(regular(root / OBSERVER, 65536))}
        for name, source in sources.items():
            raw = regular(source, 65536)
            write(fixture / name, raw)
            hashes[name] = digest(raw)
        case.update(bindingPrepared=True, bindingRetained=False)
        arguments = ["--project-dir", str(fixture), "verifyWindowsDirectoryBinding", "--console=plain",
                     "-Pp2pkit.windowsDirectoryObserver=" + str(root / OBSERVER)]

        def retain_result():
            leaf = next((row for row in case["leaves"] if row["purpose"] == "binding-controls"), None)
            canonical = state / "evidence" / leaf["id"] / "reports" / BINDING_REPORT if leaf else None
            original = fixture / "build/reports/windows-directory-binding/result.json"
            if canonical is not None and audit.existing_lstat(canonical) is not None:
                source, name = canonical, "binding-controls.json"
            elif audit.existing_lstat(original) is not None:
                source, name = original, "binding-controls-unbound.json"
            else:
                return  # A setup failure may not produce a report; original leaf logs remain mandatory.
            require(len(regular(source, 65536)) <= 65536, "Unbounded binding-control report")
            assess_binding_controls(read_json(source), hashes, require_pass=False)
            retain_available(source, case["public"] / name)

        try:
            receipt = self.leaf(case, "binding-controls", arguments, timeout=300)
            retain_result()
            matches = [row for row in receipt["reports"] if row["source"] == BINDING_REPORT]
            require(len(matches) == 1 and matches[0]["classification"] == "changed-since-admission" and
                    matches[0].get("retained") == "reports/" + BINDING_REPORT,
                    "Missing or stale canonical production-observer model result")
            raw = regular(case["public"] / "binding-controls.json", 65536)
            require(digest(raw) == matches[0]["sha256"] and len(raw) == matches[0]["bytes"],
                    "Binding controls differ from original producer receipt")
            assess_binding_controls(read_json(case["public"] / "binding-controls.json"), hashes, require_pass=True)
        finally:
            original_error = sys.exc_info()[1]
            try:
                retain_result()
                case["bindingRetained"] = True
            except Exception as error:
                case["retentionErrors"].append("Binding model retention: " + type(error).__name__ + ": " + str(error))
                if original_error is None:
                    raise audit.AuditError("Binding model evidence retention failed; preserve disposable inputs") from error

    def test_temporary(self, case, phase):
        owner, owner_hash = case["testTemporaryOwner"], case["testTemporaryOwnerSha256"]
        validate_test_temporary_owner(owner, self.identity, case["name"])
        directory = case["state"] / "fixtures/jvm-tmp"
        require(owner["directory"] == str(directory) and owner["source"] == case["context"]["source"] and
                owner["jobId"] == case["context"]["id"], "Test temporary creation context changed")
        deadline = self.final_deadline if phase == "after" else self.deadline
        record = observe_native_temporary(directory, owner["nativeIdentity"], min(deadline, time.monotonic() + 5))
        observed_hash, owner_error = None, None
        try:
            observed_hash = digest(regular(directory.parent / "jvm-tmp-owner.json", 65536))
        except Exception as error:
            name = type(error).__name__
            owner_error = name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name) else "Exception"
        leaf = next((row for row in case["leaves"] if row["purpose"] == "product"), None)
        record.update(schema=2, kind="windows-test-temporary-metadata", phase=phase,
            **{key: owner[key] for key in ("identity", "source", "caseName", "jobId", "nonce")},
            temporaryOwnerSha256=owner_hash, observedOwnerSha256=observed_hash, ownerError=owner_error,
            ownerUnchanged=observed_hash == owner_hash,
            leaf={key: leaf[key] for key in ("id", "purpose", "status", "valid", "retained")} if leaf else None)
        validate_test_temporary(record, owner, owner_hash, phase)
        new_json(case["public"] / ("temporary-" + phase + ".json"), record)
        return record

    def product(self, case):
        state, root = case["state"], case["root"]
        require(all(audit.existing_lstat(root / path) is None for path in
                    ("library/p2p-core/build", "buildSrc/build")), "Preexisting product outputs/classes are not admitted")
        nonce = case["testTemporaryOwner"]["nonce"]
        output = state / "evidence" / ("directory-control-" + nonce)
        output.mkdir(mode=0o700)
        case["productPrepared"] = True
        temporary = state / "fixtures/jvm-tmp"
        owner = state / "fixtures/jvm-tmp-owner.json"
        request = {"schema": 1, "caseName": case["name"], "nonce": nonce, "identity": self.identity,
            "source": case["context"]["source"], "root": str(root), "state": str(state), "task": TASK,
            "selector": SELECTOR, "outputDirectory": str(output), "testTemporary": str(temporary),
            "temporaryOwner": str(owner), "temporaryOwnerSha256": case["testTemporaryOwnerSha256"],
            "java17": case["env"]["JAVA_HOME"], "java21": case["env"]["P2PKIT_AUDIT_JDK21"]}
        new_json(output / "request.json", request)
        request_hash = digest(regular(output / "request.json"))
        copy_public(output / "request.json", case["public"] / "request.json")
        arguments = [TASK, "--tests", SELECTOR, "--console=plain", "--info", "--init-script", str(root / OBSERVER),
                     "-Pp2pkit.windowsDirectoryRoot=" + str(root),
                     "-Pp2pkit.windowsDirectoryRequest=" + str(output / "request.json"),
                     "-Pp2pkit.windowsDirectoryRequestSha256=" + request_hash]
        before_ok = False
        case["testTemporaryRetired"] = False
        receipt = None
        xml_name = "library/p2p-core/build/test-results/jvmTest/TEST-" + CLASS + ".xml"
        build_info = root / "library/p2p-core/build/generated/buildinfo/commonMain/kotlin/dev/p2pkit/core/BuildInfo.kt"

        def retain_selected():
            # Retain available originals before ANY result predicate, including
            # expected-red/setup/stop/cancellation failure. Never copy arbitrary
            # report members or synthetic payload files into public staging.
            errors = []
            for file in ("test-admission.json", "execution.json", "buildsrc-execution.json"):
                try:
                    retain_worker_report(output / file, case["public"] / file, request)
                except Exception as error:
                    errors.append(type(error).__name__)  # Never publish unsupported classpath/exception strings.
            retain_available(build_info, case["public"] / "BuildInfo.kt")
            product = next((row for row in case["leaves"] if row["purpose"] == "product"), None)
            canonical = state / "evidence" / product["id"] / "reports" / xml_name if product else None
            if canonical is not None and audit.existing_lstat(canonical) is not None:
                retain_available(canonical, case["public"] / "TEST-control.xml")
            elif audit.existing_lstat(root / xml_name) is not None:
                retain_available(root / xml_name, case["public"] / "TEST-control-unbound.xml")
                if audit.existing_lstat(case["public"] / "unbound-report.json") is None:
                    new_json(case["public"] / "unbound-report.json", {"schema": 1, "source": xml_name,
                        "sha256": digest(regular(root / xml_name)), "classification": "UNBOUND_FAILURE_EVIDENCE",
                        "reason": "No canonical leaf-retained selected XML; never assessed as fresh execution"})
            try:
                retain_worker_expansion(output, case["public"], request, request_hash, product)
            except Exception as error:
                errors.append(type(error).__name__)
            require(not errors, "Selected observer/worker originals could not be safely retained")

        try:
            before = self.test_temporary(case, "before")
            before_ok = test_temporary_ok(before)
            require(before_ok, "Test temporary creation identity/owner/freshness changed before product")
            receipt = self.leaf(case, "product", arguments, expected=int(case["name"] == "preimage"), timeout=1500)
            retain_selected()
            require(digest(regular(output / "request.json")) == request_hash, "Control request changed during product")
            execution = read_json(output / "execution.json")
            assess_execution(execution, request, request_hash)
            assess_execution(read_json(output / "buildsrc-execution.json"), request, request_hash, "buildSrc")
            admission = read_json(output / "test-admission.json")
            require(admission == {"schema": 1, "nonce": nonce, "caseName": case["name"],
                                  "requestSha256": request_hash, "admission": execution["admission"]},
                    "Prelaunch observer and final selected-task admission differ")
            xmls = [row for row in receipt.get("reports", []) if row["source"].endswith(".xml")]
            require(len(xmls) == 1 and xmls[0]["source"] == xml_name and
                    xmls[0]["classification"] == "changed-since-admission" and
                    xmls[0]["retained"] == "reports/" + xml_name, "Missing, extra or stale retained JUnit XML")
            raw = regular(state / "evidence" / receipt["id"] / xmls[0]["retained"], 1024 ** 2)
            require(digest(raw) == xmls[0]["sha256"], "Retained XML differs from its producer receipt")
            require(regular(case["public"] / "TEST-control.xml") == raw, "Public XML differs from retained producer XML")
            directory = assess_xml(raw, request)
            capture = read_json(case["public"] / "worker-classpath.json")
            assess_worker_log(regular(case["public"] / "product/product.stdout.log"), request,
                              execution["admission"], capture["original"]["path"])
            build_info_text = regular(case["public"] / "BuildInfo.kt").decode("utf-8", errors="strict")
            require(re.findall(r'^    public const val COMMIT: String = "([0-9a-f]{40})"$', build_info_text, re.M) ==
                    [case["context"]["expectedCommit"]] and
                    re.findall(r'^    public const val DIRTY: Boolean = (true|false)$', build_info_text, re.M) == ["false"],
                    "Generated BuildInfo does not name the actual clean current/derivative source")
            # The finally below still has to accept post-stop identity/owner and
            # empty metadata before this return can succeed. Case/outer retirement
            # remains a separate mandatory barrier in run(), never implied here.
            return {"verdict": "PASS_CURRENT" if case["name"] == "current" else "EXPECTED_PRODUCT_FAILURE",
                    "productExitCode": receipt["productExitCode"], "stopExitCode": receipt["stopExitCode"],
                    "finalExitCode": receipt["finalExitCode"], "testCount": 1, "failedDirectory": directory,
                    "scope": "one current test" if case["name"] == "current" else
                        "one historical method on current surrounding source; failed before second commit/final assertions"}
        finally:
            # Report missing reports as missing, not an empty successful suite.
            original_error = sys.exc_info()[1]
            retention_errors = []
            try:
                retain_selected()
            except Exception as error:
                retention_errors.append("Selected originals: " + type(error).__name__ + ": " + str(error))
            try:
                # Metadata is retained even on mismatch, before rejecting it.
                # No scratch contents are opened/hashed and no residue is removed.
                after = self.test_temporary(case, "after")
                case["testTemporaryRetired"] = before_ok and test_temporary_ok(after)
                require(case["testTemporaryRetired"], "Test temporary identity/owner/empty retirement is unproved")
            except Exception as error:
                retention_errors.append("Temporary retirement evidence: " + type(error).__name__ + ": " + str(error))
            case["productRetained"] = not retention_errors
            case["retentionErrors"].extend(retention_errors)
            if retention_errors and original_error is None:
                raise audit.AuditError("Selected product retention failed; keep disposable inputs: " + retention_errors[0])

    def fallback_stop(self, case):
        """Attempt the *same* owned wrapper/home after a lost/failed leaf finalizer.

        This is separately recorded recovery, never a replacement receipt or a
        promotion of a cancelled/infrastructure-failed product into expected red.
        """
        record = {"schema": 1, "caseName": case["name"], "startedUtc": audit.utc(), "exitCode": None, "errors": [],
                  "originalLeaves": [{key: row[key] for key in ("id", "purpose", "status", "valid")} for row in case["leaves"]]}
        lock, receipt_error = None, None
        failures = []

        def failed(label, error):
            record["errors"].append(label + processes.format_ownership_error(error))
            failures.append((label, error))

        try:
            state, context = audit.context_at(str(case["state"]))
            require(context == case["context"] and digest(regular(state / "context.json")) == case["contextHash"],
                    "Cannot stop with changed context")
            wrapper = case["root"] / "gradlew.bat"
            require(digest(regular(wrapper)) == case["before"]["files"]["gradlew.bat"]["sha256"],
                    "Cannot stop with changed wrapper bytes")
            require(case["scope"].drain() == [], "Cannot acquire fallback stop until owned leaves retire")
            lock = audit.LeafLock(state)
            lock.acquire(timeout=15)
            command = stop_arguments(case["root"])
            record.update(argv=command, gradleHome=context["gradleHome"], jobId=context["id"])
            code, _ = self.command(command, case["root"], case["env"], "fallback-stop", timeout=120,
                                   scope=case["scope"], finalizing=True)
            record["exitCode"] = code
            require(code == 0, "Same-home fallback stop failed")
        except BaseException as error:
            failed("Fallback stop: ", error)
        finally:
            if lock is not None:
                try:
                    lock.close()
                except BaseException as error:
                    failed("Fallback lease close: ", error)
            record["endedUtc"] = audit.utc()
            try:
                new_json(case["public"] / "fallback-stop.json", record)
            except BaseException as error:
                failed("Fallback receipt: ", error)
                receipt_error = error
        terminal = next((error for _, error in failures if not isinstance(error, Exception)), receipt_error)
        if terminal is not None:
            preserve_finalization_errors(terminal, failures, "fallback-stop")
            raise terminal
        return record

    def retire(self, case):
        require(not case["retirementAttempted"], "A retirement attempt cannot overwrite original evidence")
        case["retirementAttempted"] = True
        case["safe"] = False
        self.active_public = case["public"]
        errors, failures = [], []
        state, scope = case["state"], case["scope"]
        record = {"schema": 1, "caseName": case["name"], "roots": case["roots"], "removed": [], "errors": errors,
                  "startedUtc": audit.utc(), "scope": "only this allocation's source copy/home/fixtures/konan/android-user",
                  "statePath": str(state), "initialized": case["initialized"]}
        lock, receipt_error, close_attempted = None, None, False

        def failed(label, error):
            errors.append(label + processes.format_ownership_error(error))
            failures.append((label, error))
            case["safe"] = False

        def close_scope():
            nonlocal close_attempted
            if scope is not None and not close_attempted:
                close_attempted = True  # A failed native close is not safe to retry.
                try:
                    scope.close()
                except BaseException as error:
                    failed("Ownership handle close: ", error)

        try:
            survivors = None
            if scope is not None:
                try:
                    survivors = scope.drain()
                except BaseException as error:
                    record["drainError"] = processes.format_ownership_error(error)
                    failed("Case ownership drain: ", error)
            if case["started"] and not all(row["valid"] for row in case["leaves"]):
                try:
                    record["fallbackStop"] = self.fallback_stop(case)
                    require(not record["fallbackStop"]["errors"], "Fallback stop retirement is incomplete")
                except BaseException as error:
                    failed("Case fallback stop: ", error)
                # Fallback may have launched a child even when it failed. Drain
                # after that attempt before closing the case's native owner.
                try:
                    survivors = scope.drain() if scope is not None else None
                except BaseException as error:
                    survivors = None
                    failed("Post-fallback ownership drain: ", error)
            record["survivors"] = survivors
            if scope is not None:
                try:
                    record["ownership"] = scope.description()
                except BaseException as error:
                    failed("Case ownership record: ", error)
            # An empty census is not sufficient disposal authority: a native
            # close can still become UNKNOWN. Close BEFORE touching any root.
            close_scope()
            require(not errors and survivors == [] and record.get("ownership", {}).get("discoveryErrors") == [],
                    "Controller bridge retirement unknown")
            require_disposal_evidence(case)
            require(digest(regular(state / "context.json")) == case["contextHash"], "Immutable state changed")
            lock = audit.LeafLock(state)
            lock.acquire(timeout=15)
            after = self.source(case["root"], case["context"]["expectedCommit"], finalizing=True)
            new_json(case["public"] / "source-after.json", after)
            require(after == case["before"], "Source changed; preserve the source copy and outputs")
            expected = {case["root"], state / "gradle-home", state / "fixtures", state / "konan", state / "android-user"}
            require(case["parent"] == self.base / case["name"] and case["root"] == case["parent"] / "source" and
                    state == case["parent"] / "state" and set(map(Path, case["roots"])) == expected and
                    all(not audit.within(self.root, path) and not audit.within(path, self.root) for path in expected),
                    "Cleanup roots escaped the invocation allocation")
            retained = retain_before_disposal(case["public"], self.identity, case["name"])
            inspections = []
            for spelling, identity in case["roots"].items():
                path = Path(spelling)
                audit.reject_symlinks(path)
                info = path.lstat()
                require((info.st_dev, info.st_ino) == (identity["device"], identity["inode"]), "Owned cleanup root replaced")
                inspection = audit.inspect_disposable_tree(path)
                require(not inspection["links"], "Unexpected disposable links require separate review; preserve this root")
                inspections.append(inspection)
            record["inspections"] = inspections
            new_json(case["public"] / "retirement-start.json", record)
            for spelling, identity in case["roots"].items():
                verify_before_disposal(case["public"], retained)
                path = Path(spelling)
                shutil.rmtree(path, onerror=readonly_handler(path, identity, case["public"] / "readonly-recovery", record))
                require(audit.existing_lstat(path) is None, "Owned disposable root remains")
                record["removed"].append(spelling)
            case["safe"] = True
        except BaseException as error:
            failed("Case retirement: ", error)
        finally:
            if lock is not None:
                try:
                    lock.close()
                except BaseException as error:
                    failed("Cleanup lease close: ", error)
            close_scope()  # Independent fallback if an earlier operation failed.
            record.update(endedUtc=audit.utc(), complete=case["safe"] and not errors)
            try:
                new_json(case["public"] / "retirement.json", record)
            except BaseException as error:
                failed("Case retirement receipt: ", error)
                receipt_error = error
        terminal = next((error for _, error in failures if not isinstance(error, Exception)), receipt_error)
        if terminal is not None:
            preserve_finalization_errors(terminal, failures, "case-retirement")
            raise terminal
        require(case["safe"] and not errors, "Unknown retirement; preserve remaining sources/caches/evidence")

    def retire_command_copies(self):
        """Only duplicate captures are disposable; the sealed public bytes remain."""
        raw_rows = inventory(self.raw)
        for row in raw_rows:
            matches = [self.public / name / "commands" / row["path"] for name in ("admission", "current", "preimage")
                       if audit.existing_lstat(self.public / name / "commands" / row["path"]) is not None]
            require(len(matches) == 1 and digest(regular(matches[0])) == row["sha256"],
                    "Original command capture is not retained exactly; do not dispose")
        info = self.raw.lstat()
        require(not audit.inspect_disposable_tree(self.raw)["links"] and inventory(self.raw) == raw_rows,
                "Command copies changed before cleanup")
        shutil.rmtree(self.raw)
        require(audit.existing_lstat(self.raw) is None, "Duplicate command captures remain")
        require(not list(self.state.iterdir()), "Unexpected controller-ownership state; preserve it")
        self.state.rmdir()
        return {"rawDirectory": str(self.raw), "device": info.st_dev, "inode": info.st_ino,
                "files": raw_rows, "duplicateCapturesRemoved": True, "controllerStateRemoved": True}

    def finalize_resources(self, source, errors):
        failures, receipt_error = [], None

        def failed(label, error):
            errors.append(label + processes.format_ownership_error(error))
            failures.append((label, error))
            self.safe = False

        for case in self.cases:
            if not case["retirementAttempted"]:
                try:
                    self.retire(case)
                except BaseException as error:
                    failed("Partial allocation finalization: ", error)
                    case["safe"] = self.safe = False
            if not case["safe"]:
                self.safe = False
        self.active_public = self.public / "admission"
        outer = {"schema": 1, "identity": self.identity, "startedUtc": audit.utc()}
        # Source observation failure must not skip independent owned-worker drain.
        try:
            if source is not None:
                after = self.source(self.root, self.identity["sourceSha"], finalizing=True)
                new_json(self.public / "admission/source-after.json", after)
                require(after == source, "Campaign checkout changed; do not claim acceptance")
        except BaseException as error:
            failed("Final source observation: ", error)
        survivors, ownership, closed = None, {}, False
        try:
            survivors = self.scope.drain()
            require(survivors == [], "Outer owned workers did not retire")
        except BaseException as error:
            failed("Outer finalization: ", error)
        try:
            ownership = self.scope.description()
            require(ownership.get("discoveryErrors") == [], "Outer native ownership did not retire")
        except BaseException as error:
            failed("Outer ownership record: ", error)
        try:
            self.scope.close()
            closed = True
        except BaseException as error:
            failed("Outer ownership close: ", error)
        retired = survivors == [] and ownership.get("discoveryErrors") == [] and closed
        outer.update(survivors=survivors, ownership=ownership)
        # Preserve incomplete allocations/originals; dispose only verified copies.
        if retired and all(case["safe"] for case in self.cases):
            try:
                outer["duplicateCaptureCleanup"] = self.retire_command_copies()
            except BaseException as error:
                failed("Duplicate capture retirement: ", error)
        if self.cancelled:
            self.safe = False
        outer.update(endedUtc=audit.utc(), retirementKnown=retired, complete=self.safe and not errors, errors=list(errors))
        try:
            new_json(self.public / "admission/controller-retirement.json", outer)
        except BaseException as error:
            failed("Controller retirement receipt: ", error)
            receipt_error = error
        terminal = next((error for _, error in failures if not isinstance(error, Exception)), receipt_error)
        if terminal is not None:
            preserve_finalization_errors(terminal, failures, "controller-retirement")
            raise terminal

    def seal_results(self, outcomes, errors):
        failures = []

        def attempt(label, action):
            try:
                action()
            except BaseException as error:
                errors.append(label + processes.format_ownership_error(error))
                failures.append((label, error))
                self.safe = False

        for name, outcome in outcomes.items():
            case = next((case for case in self.cases if case["name"] == name), None)
            attempt(name + " outcome: ", lambda: new_json(self.public / name / "outcome.json", {"schema": 1, "identity": self.identity,
                "caseName": name, **outcome, "retirementComplete": bool(case and case["safe"]),
                "leafExits": [{key: row[key] for key in ("id", "purpose", "status", "valid", "retained")}
                              for row in case["leaves"]] if case else [],
                "retentionErrors": case["retentionErrors"] if case else []}))
            # These cases are independent. A failed seal must not suppress the
            # other case or the final admission failure record. Never rewrite a
            # case after its seal, including when a later case fails.
            attempt(name + " artifact seal: ", lambda: seal_public(self.public / name, self.identity, name))
            attempt(name + " artifact verification: ", lambda: verify_public(self.public / name, self.identity, name))
        attempt("Admission outcome: ", lambda: new_json(self.public / "admission/outcome.json", {"schema": 1, "identity": self.identity,
            "verdict": "PASS_SCOPED_CONTROL" if self.safe and not errors and not self.cancelled else "NOT_ACCEPTED",
            "errors": errors, "cancelledSignals": self.cancelled, "endedUtc": audit.utc(),
            "limitations": "Not all #141 criteria, full Windows/Linux suites, full gate, release or physical qualification."}))
        attempt("Admission artifact seal: ", lambda: seal_public(self.public / "admission", self.identity, "admission"))
        attempt("Admission artifact verification: ", lambda: verify_public(self.public / "admission", self.identity, "admission"))
        if failures:
            terminal = next((error for _, error in failures if not isinstance(error, Exception)), failures[0][1])
            preserve_finalization_errors(terminal, failures, "artifact-sealing")
            raise terminal  # Never announce artifacts_ready after any failed seal.
        require(not any(char in str(self.public) for char in "\0\r\n"), "Unsafe public output path")
        output = audit.absolute_path(os.environ["GITHUB_OUTPUT"])
        regular(output)  # Actual runner output file, not a symlink or another source.
        with output.open("a", encoding="utf-8") as stream:
            stream.write("public_root=" + str(self.public) + "\nartifacts_ready=true\n")

    def run(self):
        outcomes = {name: {"verdict": "NOT_EXECUTED", "scope": "No product acceptance"} for name in ("current", "preimage")}
        errors, source = [], None
        interruption, finalization_error, failures = None, None, []

        def failed(label, error, *, unhandled=False):
            nonlocal interruption, finalization_error
            errors.append(label + processes.format_ownership_error(error))
            failures.append((label, error))
            self.safe = False
            if not isinstance(error, Exception) and interruption is None:
                interruption = error
            if unhandled and finalization_error is None:
                finalization_error = error

        try:
            for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
                self.handlers[number] = signal.getsignal(number)
                signal.signal(number, lambda signum, _frame: self.cancelled.append(signum))
            new_json(self.public / "admission/start.json", {"schema": 1, "identity": self.identity, "startedUtc": audit.utc()})
            self.admit_tools()
            source = self.source(self.root, self.identity["sourceSha"], initial=True)
            new_json(self.public / "admission/source-before.json", source)
            for name in ("current", "preimage"):
                outcomes[name] = {"verdict": "NOT_ACCEPTED", "scope": "Case preparation/admission started; no product acceptance"}
                case = self.initialize(name)
                if name == "current":
                    self.sdk_and_native(case)
                    self.binding_controls(case)
                outcomes[name] = self.product(case)
                self.retire(case)
                require(case["safe"], "Earlier case retirement is incomplete")
            self.safe = True
        except BaseException as error:
            failed("", error)
            try:
                write(self.public / "admission/controller-error.txt", (errors[-1] + "\n").encode("utf-8"))
            except BaseException as retention_error:
                failed("Controller error retention: ", retention_error)
        finally:
            try:
                self.finalize_resources(source, errors)
            except BaseException as error:
                failed("Controller finalization: ", error, unhandled=True)
            # Each restoration and sealing is independent even when cancellation
            # occurred inside a native close or a terminal receipt write.
            for number, handler in self.handlers.items():
                try:
                    signal.signal(number, handler)
                except BaseException as error:
                    failed("Signal handler restoration: ", error)
            try:
                self.seal_results(outcomes, errors)
            except BaseException as error:
                failed("Artifact finalization: ", error, unhandled=True)
        terminal = interruption if interruption is not None else finalization_error
        if terminal is not None:
            preserve_finalization_errors(terminal, failures, "controller-run")
            raise terminal
        return 0 if self.safe and not errors and not self.cancelled else 125


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("admit", "run"))
    args = parser.parse_args()
    try:
        root = audit.absolute_path(os.environ["GITHUB_WORKSPACE"])
        require(SCRIPTS.parent == root, "Controller must be the exact checked-out workflow source")
        controlled_environment(dict(os.environ))
        source = audit.source_snapshot(root)
        identity = dispatch_identity(dict(os.environ), read_json(Path(os.environ["GITHUB_EVENT_PATH"])), source)
        require(processes.host_role() == "windows-x64", "Native Windows AMD64 is required, not an OS-name override")
        # Before setup actions, bind actual controller/helper bytes to source blobs.
        for path in ("scripts/run-windows-directory-control.py", "scripts/run-audit-command.py",
                     "scripts/check-audit-receipt.py", "scripts/audit_processes.py", OBSERVER, WORKFLOW):
            require(regular(root / path) == audit.git(root, "show", identity["sourceSha"] + ":" + path),
                    "Workflow/controller checkout bytes differ from the reviewed Git blobs")
        if args.action == "admit":
            print("PASS: exact hosted Windows dispatch/source identity only; no product execution")
            return 0
        return Controller(root, identity).run()
    except BaseException as error:
        print("Windows directory control NOT_ACCEPTED: " + processes.format_ownership_error(error), file=sys.stderr)
        if not isinstance(error, Exception):
            raise
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
