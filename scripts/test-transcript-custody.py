#!/usr/bin/env python3
"""Private, opt-in custody for the two real-JVM subprocess test fixtures.

This is an allocator/collector, NOT an executor, retirement observer or uploader.
The existing execution owner must stop/drain first and supply its original result.
No command here deletes evidence or makes a failed build an accepted candidate.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET


LIMIT = 16 * 1024 * 1024
JSON_LIMIT = 1024 * 1024
TOTAL_LIMIT = 64 * 1024 * 1024
INIT = "gradle/test-transcript-custody.init.gradle"
LOADER = "p2pkit-test-transcript-custody.gradle"
SUITES = {
    "cli": {
        "project": "p2p-sample-desktop", "class": "dev.p2pkit.sample.desktop.CliShutdownTest",
        "source": "samples/p2p-sample-desktop/src/test/kotlin/dev/p2pkit/sample/desktop/CliShutdownTest.kt",
        "count": 9, "prefix": "CLI_SHUTDOWN_RAW", "directories": ("p2pkit-cli-shutdown-",),
        "records": ("benignOption=false", "benignOption=true"),
    },
    "diagnostics": {
        "project": "p2p-sample-diagnostics", "class": "dev.p2pkit.sample.diagnostics.RollingJsonlFileSinkTest",
        "source": "samples/p2p-sample-diagnostics/src/test/kotlin/dev/p2pkit/sample/diagnostics/RollingJsonlFileSinkTest.kt",
        "count": 23, "prefix": "NATIVE_LOCK_PROBE_RAW", "directories": ("p2pkit-diagnostics-",),
        "records": tuple(f"expected={status} benignOption={option}"
                         for option in ("false", "true") for status in ("BUSY", "ACQUIRED")),
    },
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def no_links(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "Expected an absolute physical path")
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "Symlink/reparse point is not an owned custody path")
    return path


def identity(path):
    info = no_links(path).stat()
    require(stat.S_ISDIR(info.st_mode), "Expected a custody directory")
    require(os.name == "nt" or info.st_uid == os.getuid(), "Directory belongs to another user")
    return {"device": info.st_dev, "inode": info.st_ino}


def read_file(path, limit=LIMIT):
    path = no_links(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= limit,
            "Not a bounded single-link regular file")
    with path.open("rb") as stream:
        require(os.path.samestat(before, os.fstat(stream.fileno())), "Input replaced before reading")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    require(os.path.samestat(before, current) and os.path.samestat(before, after) and
            before.st_size == after.st_size == current.st_size == len(raw) <= limit and
            before.st_mtime_ns == after.st_mtime_ns == current.st_mtime_ns,
            "Input changed while retaining")
    return raw


def write_new(path, raw):
    path = no_links(path)
    require(len(raw) <= LIMIT, "Custody output exceeded bound")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
        require(stream.write(raw) == len(raw), "Short custody write")
        stream.flush()
        os.fsync(stream.fileno())
    require(read_file(path) == raw, "Retained bytes differ")


def parse_json(raw):
    require(0 < len(raw) <= JSON_LIMIT, "JSON size outside bound")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON member")
            result[key] = value
        return result

    def reject(_):
        raise ValueError("Nonfinite JSON number")

    value = json.loads(raw, object_pairs_hook=unique, parse_constant=reject)
    require(isinstance(value, dict), "Expected JSON object")
    return value


def git(root, *args):
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                 "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_EXTERNAL_DIFF"):
        require(name not in os.environ, "Conflicting Git environment")
    result = subprocess.run(["git", "--no-replace-objects", "-C", str(root), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    require(result.returncode == 0 and len(result.stdout) <= LIMIT, "Source-binding Git command failed")
    return result.stdout


def source(root):
    require(Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel").strip())).resolve() == root,
            "Use the actual source checkout root")
    return {
        "commit": git(root, "rev-parse", "HEAD").decode().strip(),
        "tree": git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
        "status": git(root, "status", "--porcelain=v1", "--untracked-files=all").decode(),
        "diffSha256": digest(git(root, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD")),
    }


def report_path(root, suite):
    return root / "samples" / suite["project"] / "build/test-results/test" / f"TEST-{suite['class']}.xml"


def methods(root, scope):
    names = re.findall(r"@Test\s+fun\s+(\w+)\s*\(", read_file(root / SUITES[scope]["source"]).decode())
    require(len(names) == len(set(names)) == SUITES[scope]["count"], "Source test-method set changed; review the scope")
    return sorted(names)


def loader_bytes(request_path, request_hash, root):
    # JSON strings are valid Groovy double-quoted strings except for interpolation.
    def quote(value):
        return json.dumps(str(value)).replace("$", "\\$")
    return (f"gradle.ext.p2pkitCustodyRequest = {quote(request_path)}\n"
            f"gradle.ext.p2pkitCustodyRequestSha256 = {quote(request_hash)}\n"
            f"apply from: {quote(root / INIT)}\n").encode()


def reserve_owner(root, home, state, kind, before, writer_job):
    if kind == "audit":
        require(writer_job is None, "Audit job must come from the actual context")
        context = parse_json(read_file(state / "context.json", JSON_LIMIT))
        require(context.get("root") == str(root) and context.get("gradleHome") == str(home) and
                context.get("source") == before, "Audit context source/root/home differs")
        job = context.get("id", "")
    else:
        job = writer_job
    require(isinstance(job, str) and re.fullmatch(r"[0-9a-f]{32}", job), "Missing actual owner job")
    # Allocate here, not from a possibly stale caller-supplied receipt/ID. The
    # established owner must consume these IDs before starting either command.
    product = uuid.uuid4().hex
    stop = uuid.uuid4().hex if kind == "writer" else None
    identifiers = [job, product] + ([stop] if stop else [])
    require(len(identifiers) == len(set(identifiers)), "Duplicate reserved owner identity")
    for invocation in identifiers[1:]:
        require(not os.path.lexists(state / "evidence" / invocation), "Reserved invocation already exists")
    return {"job": job, "productInvocation": product, "stopInvocation": stop}


def product_domain(request):
    owner = request["owner"]
    return {"id": owner["productInvocation"], "job": owner["job"],
            "state": request["ownerState"], "home": request["home"]}


def validate_owner_binding(request):
    owner = request["owner"]
    require(set(owner) == {"job", "productInvocation", "stopInvocation"}, "Unknown owner binding")
    values = [owner["job"], owner["productInvocation"]]
    if request["ownerKind"] == "writer":
        values.append(owner["stopInvocation"])
    else:
        require(owner["stopInvocation"] is None, "Audit stop must use its existing invocation domain")
    require(all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) for value in values) and
            len(values) == len(set(values)), "Invalid or duplicate owner identity")


def prepare(root, directory, home, owner_state, kind, scopes, command, writer_job=None):
    for path in (root, home, owner_state):
        identity(path)
    no_links(directory)
    require(directory.parent.is_dir() and not directory.exists(), "Custody root must be new")
    require(not directory.is_relative_to(root) and not root.is_relative_to(directory),
            "Keep private custody outside the source checkout")
    require(home == owner_state / "gradle-home", "Use the existing owner's exclusive Gradle home")
    require(kind in ("audit", "writer") and scopes in (["cli"], ["cli", "diagnostics"]), "Unsupported custody scope")
    require(isinstance(command, list) and 0 < len(command) <= 64 and
            all(isinstance(arg, str) and 0 < len(arg) <= 8192 and "\0" not in arg for arg in command),
            "Invalid exact owner command")
    before = source(root)
    require(before["status"] == "" and before["diffSha256"] == digest(b""), "Prepare at a clean committed source")
    owner = reserve_owner(root, home, owner_state, kind, before, writer_job)
    require(not (home / "init.d" / LOADER).exists(), "Custody initializer already installed")
    for scope in scopes:
        require(not report_path(root, SUITES[scope]).exists(), "Preexisting class XML is not fresh evidence")
    inputs = {name: digest(read_file(root / name)) for name in
              (INIT, "scripts/test-transcript-custody.py", *(SUITES[item]["source"] for item in scopes))}
    directory.mkdir(mode=0o700)
    for part in ("temp", "events", "retained"):
        (directory / part).mkdir(mode=0o700)
    token = uuid.uuid4().hex
    roots = {}
    for scope in scopes:
        path = directory / "temp" / scope
        path.mkdir(mode=0o700)
        write_new(path / "owner.token", (token + "\n").encode())
        roots[scope] = {"path": str(path), "identity": identity(path)}
    request = {"schema": 1, "token": token, "root": str(root), "directory": str(directory),
               "directoryIdentity": identity(directory), "home": str(home), "homeIdentity": identity(home),
               "ownerState": str(owner_state), "ownerKind": kind, "owner": owner,
               "command": command, "source": before,
               "inputs": inputs, "roots": roots, "methods": {item: methods(root, item) for item in scopes},
               "createdUtc": datetime.now(timezone.utc).isoformat()}
    raw = encoded(request)
    require(len(raw) <= JSON_LIMIT, "Request too large")
    write_new(directory / "request.json", raw)
    init_directory = home / "init.d"
    if not init_directory.exists():
        init_directory.mkdir(mode=0o700)
    identity(init_directory)
    write_new(init_directory / LOADER, loader_bytes(directory / "request.json", digest(raw), root))
    # A partial prepare leaves its new files in place, never deletes a foreign/preexisting path.
    return request


def check_request(directory):
    raw = read_file(directory / "request.json", JSON_LIMIT)
    request = parse_json(raw)
    require(request.get("schema") == 1 and re.fullmatch(r"[0-9a-f]{32}", request.get("token", "")),
            "Invalid request identity")
    require(request["directory"] == str(directory) and identity(directory) == request["directoryIdentity"],
            "Custody root replaced")
    root, home = Path(request["root"]), Path(request["home"])
    require(set(request["roots"]) in ({"cli"}, {"cli", "diagnostics"}) and
            request["ownerKind"] in ("audit", "writer"), "Unknown request scope")
    validate_owner_binding(request)
    require(not directory.is_relative_to(root) and not root.is_relative_to(directory), "Invalid custody location")
    require(identity(home) == request["homeIdentity"], "Owned Gradle home replaced")
    require(read_file(home / "init.d" / LOADER) == loader_bytes(directory / "request.json", digest(raw), root),
            "Installed initializer changed")
    expected_inputs = {INIT, "scripts/test-transcript-custody.py", *(SUITES[item]["source"] for item in request["roots"])}
    require(set(request["inputs"]) == expected_inputs, "Source input set changed")
    for name, expected in request["inputs"].items():
        require(digest(read_file(root / name)) == expected, "Bound source/initializer changed")
    for scope, entry in request["roots"].items():
        path = Path(entry["path"])
        require(path == directory / "temp" / scope, "Unexpected temporary root")
        require(identity(path) == entry["identity"] and
                read_file(path / "owner.token") == (request["token"] + "\n").encode(), "Temporary owner changed")
        require(request["methods"][scope] == methods(root, scope), "Test method set changed")
    return request, digest(raw)


def owner_outcome(request, owner, owner_path):
    """Read actual established owners, not caller-provided --retired=true claims."""
    root, state = Path(request["root"]), Path(request["ownerState"])
    validate_owner_binding(request)
    expected = request["owner"]
    require(owner.get("sourceBefore") == request["source"], "Owner source binding differs")
    if request["ownerKind"] == "audit":
        require(owner.get("schema") == 1 and owner.get("cwd") == str(root) and
                owner.get("gradleHome") == request["home"] and owner.get("requestedArgv") == request["command"],
                "Audit receipt command/home differs")
        require(owner.get("id") == expected["productInvocation"] and owner.get("jobId") == expected["job"],
                "Audit receipt is not this reserved invocation")
        canonical = state / "evidence" / owner["id"] / "receipt.json"
        require(read_file(canonical) == read_file(owner_path), "Not the finalized canonical audit receipt")
        context = parse_json(read_file(state / "context.json", JSON_LIMIT))
        require(context.get("id") == owner.get("jobId") and context.get("root") == str(root) and
                context.get("source") == request["source"] and
                context.get("gradleHome") == request["home"], "Audit context differs")
        require(owner.get("ownedSurvivors") == [] and owner.get("errors") == [] and
                owner.get("ownership", {}).get("discoveryErrors") == [], "Unknown audit retirement/finalization")
        ownership = owner.get("ownership", {})
        native_ownership(ownership)
        require(ownership["job"] == owner["jobId"] and ownership["invocation"] == owner["id"],
                "Native audit ownership domain differs")
        require(owner.get("sourceUnchanged") is True and owner.get("sourceAfter") == request["source"],
                "Audit source changed")
        return owner.get("productExitCode"), owner.get("stopExitCode"), owner.get("finalExitCode")
    require(request["ownerKind"] == "writer" and
            owner.get("scope") == "MUTABLE_FULL_WRITER_NOT_AUDIT_LEAF" and owner.get("state") == str(state),
            "Unknown mutable owner contract")
    require(Path(request["home"]) == state / "gradle-home", "Writer home differs")
    product, stop = owner.get("writer", {}), owner.get("stop", {})
    require(product.get("argv") == request["command"] and
            stop.get("argv", [])[:2] == [str(root / "gradlew"), "--stop"], "Writer/stop command differs")
    for row, stage, invocation in ((product, "product-final", expected["productInvocation"]),
                                   (stop, "stop-final", expected["stopInvocation"])):
        require(row.get("launchAttempted") is True and row.get("errors") == [], "Incomplete command finalization")
        traces = row.get("drains", [])
        require(any(item.get("stage") == stage for item in traces) and
                all(item.get("survivors") == [] and item.get("error") is None for item in traces),
                "Unknown owned writer/stop retirement")
        ownership = row.get("ownership", {})
        native_ownership(ownership)
        require(ownership["job"] == expected["job"] and ownership["invocation"] == invocation,
                "Writer/stop is not this reserved invocation/job")
        require(ownership.get("discoveryErrors") == [] and ownership.get("launches") and
                ownership["launches"][0].get("cwd") == str(root), "Missing native ownership trace")
    # The writer's pre-cleanup snapshot is not its later candidate/lease-release verdict.
    return product.get("waitExitCode"), stop.get("waitExitCode"), None


def native_ownership(ownership):
    contracts = {"linux-proc-pidfd": "controlled-marker-inheriting-descendants",
                 "darwin-libproc-audit-token": "controlled-marker-inheriting-descendants",
                 "windows-job-list-suspended": "kernel-job-no-breakaway-kill-on-close"}
    require(ownership.get("backend") in contracts and
            ownership.get("scope") == contracts[ownership["backend"]] and
            all(re.fullmatch(r"[0-9a-f]{32}", ownership.get(key, "")) for key in ("job", "invocation")) and
            isinstance(ownership.get("launches"), list) and ownership["launches"] and
            isinstance(ownership.get("startedIdentities"), list) and ownership["startedIdentities"],
            "Missing established native ownership record")


def xml_exports(raw, scope, expected_methods):
    require(b"\0" not in raw and b"<!DOCTYPE" not in raw.upper() and b"<!ENTITY" not in raw.upper(),
            "Unadmitted XML encoding/declarations")
    suite = SUITES[scope]
    xml = ET.fromstring(raw)
    require(xml.tag == "testsuite" and xml.get("name") == suite["class"], "Wrong test suite")
    cases = xml.findall("testcase")
    require(xml.get("tests") == str(suite["count"]) and len(cases) == suite["count"] and
            {case.get("name", "").removesuffix("()") for case in cases} == set(expected_methods) and
            len({case.get("name") for case in cases}) == len(cases) and
            all(case.get("classname") == suite["class"] for case in cases), "Missing/duplicate class methods")
    require(all(xml.get(name) == "0" for name in ("failures", "errors", "skipped")) and
            not xml.findall(".//failure") and not xml.findall(".//error") and not xml.findall(".//skipped"),
            "Class failure/skip is not accepted")
    outputs = [element.text or "" for element in xml.findall(".//system-out") + xml.findall(".//system-err")]
    require(not any("PROBE_EVIDENCE_HOLD" in value for value in outputs), "Fixture reported custody HOLD")
    records = {}
    for output in outputs:
        for line in output.splitlines():
            if suite["prefix"] not in line:
                continue
            match = re.fullmatch(re.escape(suite["prefix"]) + r" (.+) bytes=([0-9]{1,8}) base64=([A-Za-z0-9+/=]*)", line)
            require(match is not None, "Malformed original transcript export")
            key, length, value = match.groups()
            require(key in suite["records"] and key not in records, "Unexpected/duplicate transcript identity")
            data = base64.b64decode(value, validate=True)
            require(base64.b64encode(data).decode() == value and len(data) == int(length), "Transcript byte mismatch")
            records[key] = data
    require(set(records) == set(suite["records"]), "Missing original transcript export")
    return records


def remaining_logs(root, scope):
    """Only this newly allocated root. Never search global Java/system temp."""
    matches, pending, count = [], [(root, 0)], 0
    while pending:
        directory, depth = pending.pop()
        require(depth <= 4, "Unexpected fixture directory depth")
        identity(directory)
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1
                require(count <= 4096, "Fixture inventory exceeded bound")
                path = no_links(Path(entry.path))
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    pending.append((path, depth + 1))
                else:
                    require(stat.S_ISREG(info.st_mode), "Unknown fixture file type")
                    if path.name == "child.log" or re.fullmatch(r"native-lock-probe-.*\.log", path.name):
                        matches.append(path)
    return sorted(matches)


def validate_event(event, request, request_hash, scope, suffix):
    require(event.get("schema") == 1 and event.get("requestSha256") == request_hash and
            event.get("token") == request["token"] and
            event.get("task") == f":{SUITES[scope]['project']}:test" and
            event.get("ownerDomain") == product_domain(request), "Unbound task/owner event")
    if suffix == "finish":
        require(event.get("executed") is True and event.get("failed") is False,
                "Test task did not execute successfully")
    else:
        require(event.get("temporary") == request["roots"][scope]["path"], "Test temporary property differs")


def collect(directory, owner_path):
    request, request_hash = check_request(directory)
    target = directory / "retained"
    require(not any(target.iterdir()), "Collection is one-shot; retain the earlier result")
    result = {"schema": 1, "requestSha256": request_hash, "result": "HOLD", "source": request["source"],
              "productExitCode": None, "stopExitCode": None, "ownerFinalExitCode": None,
              "retirement": "UNKNOWN", "files": [], "errors": [], "scope": "PRIVATE_TRANSCRIPT_CUSTODY_ONLY"}

    total = 0

    def save(name, raw):
        nonlocal total
        require(total + len(raw) <= TOTAL_LIMIT and len(result["files"]) < 128, "Aggregate custody bound exceeded")
        total += len(raw)
        write_new(target / name, raw)

    def retain(path, name):
        raw = read_file(path)
        save(name, raw)
        require(read_file(path) == raw, "Original changed after copy")
        result["files"].append({"name": name, "original": str(path), "bytes": len(raw), "sha256": digest(raw)})
        return raw

    def attempt(label, operation):
        try:
            return operation()
        except (OSError, ValueError, TypeError, KeyError, ET.ParseError, RecursionError) as error:
            # Private result: keep bounded diagnostic detail, never print raw fixture data.
            result["errors"].append({"stage": label, "error": f"{type(error).__name__}: {error}"[:2048]})
            return None

    def owner_check():
        raw = retain(owner_path, "owner-result.json")
        product, stop, final = owner_outcome(request, parse_json(raw), owner_path)
        result.update(productExitCode=product, stopExitCode=stop, ownerFinalExitCode=final, retirement="KNOWN")
        require(type(product) is int and product == 0 and type(stop) is int and stop == 0 and
                (request["ownerKind"] == "writer" or type(final) is int and final == 0),
                "Failed/incomplete execution remains HOLD")

    attempt("owner", owner_check)
    for scope, entry in request["roots"].items():
        for suffix in ("start", "finish"):
            def task_event():
                event = parse_json(retain(directory / "events" / f"{scope}-{suffix}.json", f"{scope}-{suffix}.json"))
                validate_event(event, request, request_hash, scope, suffix)
            attempt(scope + "-" + suffix, task_event)

        def reports():
            raw = retain(report_path(Path(request["root"]), SUITES[scope]), f"{scope}.xml")
            for index, (key, data) in enumerate(sorted(xml_exports(raw, scope, request["methods"][scope]).items())):
                name = f"{scope}-export-{index}.log"
                save(name, data)
                result["files"].append({"name": name, "record": key, "bytes": len(data), "sha256": digest(data)})

        attempt(scope + "-reports", reports)
        if result["retirement"] == "KNOWN":
            def residuals():
                paths = remaining_logs(Path(entry["path"]), scope)
                for index, path in enumerate(paths):
                    attempt(scope + "-original-copy", lambda path=path, index=index:
                            retain(path, f"{scope}-remaining-{index}.log"))
                require(not paths, "Surviving raw originals require custody review; do not delete the root")
            attempt(scope + "-remaining-originals", residuals)
        else:
            result["errors"].append({"stage": scope + "-remaining-originals", "error": "Unknown retirement: keep originals in place"})
    attempt("final-binding", lambda: check_request(directory))
    def final_source():
        current = source(Path(request["root"]))
        require(all(current[key] == request["source"][key] for key in ("commit", "tree")), "Source revision changed")
        if request["ownerKind"] == "audit":
            require(current == request["source"], "Immutable source changed")
        else:
            root = Path(request["root"])
            allowed = set(git(root, "ls-files", "-z", "--", "*lockfile").decode().split("\0")) - {""}
            allowed.add("gradle/verification-metadata.xml")
            changed = set(git(root, "diff", "--name-only", "-z", "HEAD").decode().split("\0")) - {""}
            require(changed <= allowed and not git(root, "ls-files", "--others", "--exclude-standard"),
                    "Mutable writer changed non-lock source")
        result["sourceAfter"] = current
    attempt("final-source", final_source)
    if not result["errors"]:
        result["result"] = "RETAINED"
    write_new(directory / "result.json", encoded(result))
    return result


def uninstall(directory):
    """Remove only our exact init.d loader, never the custody root or other init scripts."""
    request, request_hash = check_request(directory)
    result = parse_json(read_file(directory / "result.json", JSON_LIMIT))
    require(result.get("requestSha256") == request_hash and result.get("retirement") == "KNOWN",
            "Unknown retirement blocks initializer removal")
    loader = Path(request["home"]) / "init.d" / LOADER
    original = read_file(loader)
    before = loader.lstat()
    require(original == loader_bytes(directory / "request.json", request_hash, Path(request["root"])),
            "Initializer no longer belongs to this request")
    write_new(directory / "uninstall-intent.json", encoded({"requestSha256": request_hash, "sha256": digest(original)}))
    require(os.path.samestat(before, loader.lstat()) and read_file(loader) == original, "Initializer changed before removal")
    loader.unlink()
    require(not loader.exists(), "Initializer removal not verified")
    write_new(directory / "uninstalled.json", encoded({"requestSha256": request_hash, "absent": True,
                                                       "custodyResult": result["result"], "originalsDeleted": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    prepare_parser = sub.add_parser("prepare")
    for name in ("root", "directory", "home", "owner-state"):
        prepare_parser.add_argument("--" + name, type=Path, required=True)
    prepare_parser.add_argument("--owner-kind", choices=("audit", "writer"), required=True)
    prepare_parser.add_argument("--writer-job", help="Existing writer controller job; audit reads its context instead")
    prepare_parser.add_argument("--scope", choices=("cli", "both"), required=True)
    prepare_parser.add_argument("command", nargs=argparse.REMAINDER)
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--directory", type=Path, required=True)
    collect_parser.add_argument("--owner-result", type=Path, required=True)
    uninstall_parser = sub.add_parser("uninstall")
    uninstall_parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            prepare(args.root, args.directory, args.home, args.owner_state, args.owner_kind,
                    ["cli"] if args.scope == "cli" else ["cli", "diagnostics"], command, args.writer_job)
            print("Custody prepared; no build, retirement or runtime validation performed")
            return 0
        if args.operation == "uninstall":
            uninstall(args.directory)
            print("Owned initializer removed; all private custody evidence remains")
            return 0
        result = collect(args.directory, args.owner_result)
        print("Custody " + result["result"] + "; private evidence remains in the owned directory")
        return 0 if result["result"] == "RETAINED" else 125
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print("Custody HOLD: " + type(error).__name__ + "; retain all originals, no cleanup", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
