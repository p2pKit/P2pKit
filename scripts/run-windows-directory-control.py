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
CLASS = "dev.p2pkit.core.transfer.FileTransferJvmTest"
METHOD = "durableDestinationPublishesOnlyAfterCommitAndCommitIsIdempotent"
SELECTOR = CLASS + "." + METHOD
TASK = ":p2p-core:jvmTest"
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
            event.get("ref") in (ref, ref[len("refs/heads/"):]) and event.get("inputs") == {
                "operation": OPERATION, "expected_sha": expected, "expected_tree": tree},
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
    require(suite.tag == "testsuite" and suite.get("name") == CLASS and suite.get("tests") == "1" and
            suite.get("failures") == str(int(negative)) and suite.get("errors") == suite.get("skipped") == "0",
            "Wrong, empty, skipped or extra control JUnit suite")
    require(all(child.tag in ("properties", "testcase", "system-out", "system-err") for child in suite),
            "Unexpected JUnit suite element")
    cases = suite.findall("testcase")
    require(len(cases) == 1 and cases[0].get("classname") == CLASS and cases[0].get("name") == METHOD,
            "Wrong or duplicate selected testcase")
    require(all(child.tag in ("failure", "system-out", "system-err") for child in cases[0]),
            "Skipped/error control testcase is not acceptance")
    failures = cases[0].findall("failure")
    require(len(failures) == int(negative), "Incorrect selected-test failure count")
    return failure_directory(failures[0], request["testTemporary"]) if negative else None


def assess_execution(report, request, request_hash, scope="root"):
    require(type(report) is dict and integer(report.get("schema"), 1) and report.get("scope") == scope and
            report.get("nonce") == request["nonce"] and report.get("caseName") == request["caseName"] and
            report.get("source") == request["source"] and report.get("identity") == request["identity"] and
            report.get("requestSha256") == request_hash, "Wrong/stale execution nonce, source, case or run")
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
            report.get("requestedTasks") == [TASK] and set(paths) <= CORE_TASKS and REQUIRED_TASKS <= set(paths) and
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
            type(admission.get("temporaryFileKey")) is str and bool(admission["temporaryFileKey"]) and
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


def assess_worker_log(raw, request):
    text = raw.decode("utf-8", errors="strict")
    commands = re.findall(r"^Starting process 'Gradle Test Executor [0-9]+'.*? Command: ([^\r\n]+)", text, re.M)
    require(len(commands) == 1 and len(re.findall(r"^Successfully started process 'Gradle Test Executor [0-9]+'", text, re.M)) == 1,
            "Original info log lacks the one actually launched Test worker")
    java = str(PureWindowsPath(request["java17"]) / "bin/java.exe")
    command = commands[0]
    require(command.startswith(java + " ") or command.startswith('"' + java + '" '),
            "Actual worker command uses another launcher")
    for token in ("-Djava.io.tmpdir=" + request["testTemporary"],
                  "-Dp2pkit.windowsDirectoryNonce=" + request["nonce"], "-Xmx512m", "-Xms128m",
                  "-XX:ActiveProcessorCount=2", "-XX:-UsePerfData"):
        require(len(re.findall(r'(?:^| )"?' + re.escape(token) + r'"?(?= |$)', command)) == 1,
                "Actual worker command lacks its exact bounded temporary/nonce argument token")
    for prefix in ("-Djava.io.tmpdir=", "-Dp2pkit.windowsDirectoryNonce=", "-Xmx", "-Xms", "-XX:ActiveProcessorCount="):
        require(len(re.findall(r'(?:^| )"?' + re.escape(prefix), command)) == 1, "Duplicate actual worker critical option")
    require(not re.search(r'(?:^| )"?(?:-Dos\.(?:name|arch)=|-javaagent:|@)', command), "Actual worker OS/agent was injected")


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
            (not case["productPrepared"] or case["productRetained"]) and
            (not case["nativeStarted"] or case["nativeAccepted"]),
            "Required original retention failed; preserve sources, outputs and caches")


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
                        "context.json", "gradle.properties", "request.json", "temporary-before.json",
                        "temporary-after.json", "retirement-start.json", "retirement.json", "controller-error.txt",
                        "native-controls.json", "test-admission.json", "execution.json", "buildsrc-execution.json",
                        "TEST-control.xml", "TEST-control-unbound.xml", "unbound-report.json",
                        "sdk.json", "allocation.json", "retained-before-disposal.json",
                        "source-materialization.json", "controller-retirement.json", "fallback-stop.json", "BuildInfo.kt"}
    if path.parts[0] == "native-controls":
        return native_public_path("/".join(path.parts[1:]))
    if len(path.parts) == 3 and path.parts[0] == "commands":
        return bool(re.fullmatch(r"[1-9][0-9]*-(?:git|source-clone|source-archive|init|java17|java21|wrapper-version|sdk-install|executor-native-controls|product|fallback-stop)",
                                 path.parts[1])) and path.parts[2] in {"start.json", "command.json", "stdout.log", "stderr.log"}
    if len(path.parts) == 2 and path.parts[0] == "readonly-recovery":
        return bool(re.fullmatch(HEX32 + r"-(?:start|outcome)\.json", path.parts[1]))
    if len(path.parts) == 2 and path.parts[0] in {"java17", "java21", "init"}:
        return path.parts[1] in {"command.json", "stdout.log", "stderr.log"}
    if len(path.parts) == 2 and path.parts[0] in {"wrapper-version", "sdk-install", "executor-native-controls", "product"}:
        return path.parts[1] in LEAF_FILES | {"controller.json", "controller.stdout.log", "controller.stderr.log"}
    return False


def public_manifest(identity, case_name, rows):
    return {"schema": 1, "identity": identity, "caseName": case_name, "files": rows,
            "scope": "synthetic local-filesystem witness; no private/device/payload evidence or full-gate claim"}


def seal_public(directory, identity, case_name):
    rows = inventory(directory)
    require(rows and all(public_path(row["path"]) for row in rows), "Unaudited public evidence member")
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


def copy_public(source, destination):
    value = regular(source)
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
    value = {"schema": 1, "identity": identity, "caseName": case_name, "files": rows}
    new_json(directory / "retained-before-disposal.json", value)
    return value


def verify_before_disposal(directory, expected):
    require(regular(directory / "retained-before-disposal.json") == audit.json_bytes(expected), "Pre-disposal manifest changed")
    rows = {row["path"]: row for row in inventory(directory)}
    require(all(rows.get(row["path"]) == row for row in expected["files"]),
            "Required retained original is missing/changed before disposal")
    admitted = {row["path"] for row in expected["files"]} | {"retained-before-disposal.json", "retirement-start.json"}
    require(all(name in admitted or name.startswith("readonly-recovery/") and public_path(name) for name in rows),
            "Unexpected evidence was inserted before disposal")


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
        child = None
        record = {"argv": argv, "cwd": str(cwd), "startedUtc": audit.utc(), "exitCode": None,
                  "cancelled": False, "finalizing": finalizing, "errors": errors}
        new_json(output / "start.json", record)
        deadline = min(self.final_deadline if finalizing else self.deadline, time.monotonic() + timeout)
        try:
            require(finalizing or not self.cancelled, "Controller cancelled before command start")
            require(time.monotonic() < deadline, "Command admission deadline exceeded")
            child = scope.spawn(argv, str(cwd), env)
            streams.append(audit.Tee(child.stdout, output / "stdout.log", None, errors))
            streams.append(audit.Tee(child.stderr, output / "stderr.log", None, errors))
            while child.poll() is None:
                scope.discover()
                require(time.monotonic() < deadline and (finalizing or not self.cancelled), "Controller deadline or cancellation")
                if not finalizing:
                    self.resources()
                require(sum((output / file).stat().st_size for file in ("stdout.log", "stderr.log")) <= MAX_FILE,
                        "Command output exceeded its retained bound")
                time.sleep(.1)
            record["exitCode"] = child.wait(timeout=5)
        except Exception as error:
            errors.append(type(error).__name__ + ": " + str(error))
            record["cancelled"] = bool(self.cancelled) or "deadline" in str(error).lower()
        finally:
            if child is not None and child.poll() is None and cancellation is not None:
                try:
                    cancellation()
                    end = min(self.final_deadline, time.monotonic() + 165)
                    while child.poll() is None and time.monotonic() < end:
                        scope.discover()
                        time.sleep(.1)
                except Exception as error:
                    errors.append("Cooperative cancellation: " + type(error).__name__ + ": " + str(error))
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
            except Exception as error:
                errors.append("Command retirement: " + type(error).__name__ + ": " + str(error))
            for stream in streams:
                try:
                    stream.finish()
                except Exception as error:
                    errors.append("Command stream finalization: " + type(error).__name__ + ": " + str(error))
            if child is not None:
                for pipe in (child.stdout, child.stderr):
                    if not any(getattr(stream, "source", None) is pipe for stream in streams):
                        try:
                            pipe.close()  # A partially failed Tee allocation never acquired this pipe.
                        except Exception as error:
                            errors.append("Unclaimed command pipe close: " + type(error).__name__)
            try:
                record["ownership"] = scope.description()
                errors.extend(record["ownership"].get("discoveryErrors", []))
            except Exception as error:
                errors.append("Command ownership retention: " + type(error).__name__ + ": " + str(error))
            record["endedUtc"] = audit.utc()
            try:
                new_json(output / "command.json", record)
            except Exception as error:
                errors.append("Command record retention: " + type(error).__name__ + ": " + str(error))
            for file in ("start.json", "command.json", "stdout.log", "stderr.log"):
                try:
                    if audit.existing_lstat(output / file) is not None:
                        copy_public(output / file, self.active_public / "commands" / output.name / file)
                except Exception as error:
                    errors.append("Command public retention: " + file + ": " + type(error).__name__ + ": " + str(error))
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
        for child in ("jvm-tmp", "native-tmp", "process-tmp"):
            (fixtures / child).mkdir(mode=0o700)
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

    def leaf(self, case, purpose, arguments, *, kind="gradle", timeout=1200, expected=0, extra_env=None):
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
            require(not extra_env or purpose == "executor-native-controls" and kind == "command" and
                    extra_env == {name: str(state / "fixtures/native-tmp") for name in ("TEMP", "TMP", "TMPDIR")},
                    "Only the native fixture's owned temporary bridge may augment leaf environment")
            code, capture = self.command(command, root, dict(case["env"], **(extra_env or {})), purpose,
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
        # NUL stdin: this never accepts a license prompt. A missing owner-approved
        # SDK/license is a setup blocker, not permission to manufacture metadata.
        self.leaf(case, "sdk-install", [str(manager), "--sdk_root=" + str(sdk),
                                        "platforms;android-36", "platforms;android-37.0"], kind="command", timeout=900)
        platforms = {}
        for name, api in (("android-36", "36"), ("android-37.0", "37.0")):
            raw = regular(sdk / "platforms" / name / "source.properties")
            matches = re.findall(r"^AndroidVersion\.ApiLevel\s*=\s*([^\r\n]+)\s*$", raw.decode(), re.M)
            require(matches == [api], "Compile SDK metadata is not literally the supported platform")
            platforms[name] = {"api": api, "sourcePropertiesSha256": digest(raw), "content": raw.decode()}
        new_json(self.public / "admission/sdk.json", platforms)
        native = case["state"] / "evidence/native-controls"
        temporary = case["state"] / "fixtures/native-tmp"
        case["nativeStarted"] = True
        try:
            self.leaf(case, "executor-native-controls", [sys.executable, "-B", "scripts/tests/run-audit-command-test.py",
                "--expected-host", "windows-x64", "--evidence-dir", str(native)], kind="command", timeout=1800,
                extra_env={name: str(temporary) for name in ("TEMP", "TMP", "TMPDIR")})
        finally:
            if audit.existing_lstat(native) is not None:
                rows = inventory(native)
                require(all(native_public_path(row["path"]) for row in rows),
                        "Native fixture evidence contains an unaudited public member; retain originals and stop")
                for row in rows:
                    copy_public(native / row["path"], self.public / "admission/native-controls" / row["path"])
        logs = case["public"] / "executor-native-controls"
        text = (regular(logs / "product.stdout.log") + regular(logs / "product.stderr.log")).decode("utf-8", errors="strict")
        count = expected_native_count(regular(case["root"] / "scripts/tests/run-audit-command-test.py"))
        require(re.search(r"\nRan " + str(count) + r" tests? in [0-9.]+s\r?\n\r?\nOK\r?\n", text) and
                "Running current-host real executor fixtures: windows-x64;" in text and
                "skipped=" not in text and not list(temporary.iterdir()),
                "Complete native suite did not pass without skips/temporary survivors")
        cleanups = assess_native_cleanup(native, regular(case["root"] / "scripts/tests/run-audit-command-test.py"))
        new_json(self.public / "admission/native-controls.json", {"schema": 1, "count": count, "exitCode": 0,
            "command": case["leaves"][-1]["arguments"], "files": rows, "fixtureCleanup": cleanups,
            "scope": "actual current-host executor controls, not product/library acceptance"})
        case["nativeAccepted"] = True

    def product(self, case):
        state, root = case["state"], case["root"]
        require(all(audit.existing_lstat(root / path) is None for path in
                    ("library/p2p-core/build", "buildSrc/build")), "Preexisting product outputs/classes are not admitted")
        nonce = uuid.uuid4().hex
        output = state / "evidence" / ("directory-control-" + nonce)
        output.mkdir(mode=0o700)
        case["productPrepared"] = True
        temporary = state / "fixtures/jvm-tmp"
        info = temporary.lstat()
        require(not list(temporary.iterdir()), "Selected-test temporary root is not genuinely fresh")
        owner = state / "fixtures/jvm-tmp-owner.json"
        new_json(owner, {"schema": 1, "nonce": nonce, "caseName": case["name"], "jobId": case["context"]["id"],
                         "directory": str(temporary), "device": info.st_dev, "inode": info.st_ino})
        request = {"schema": 1, "caseName": case["name"], "nonce": nonce, "identity": self.identity,
            "source": case["context"]["source"], "root": str(root), "state": str(state), "task": TASK,
            "selector": SELECTOR, "outputDirectory": str(output), "testTemporary": str(temporary),
            "temporaryOwner": str(owner), "temporaryOwnerSha256": digest(regular(owner)),
            "java17": case["env"]["JAVA_HOME"], "java21": case["env"]["P2PKIT_AUDIT_JDK21"]}
        new_json(case["public"] / "temporary-before.json", read_json(owner))
        new_json(output / "request.json", request)
        request_hash = digest(regular(output / "request.json"))
        copy_public(output / "request.json", case["public"] / "request.json")
        arguments = [TASK, "--tests", SELECTOR, "--console=plain", "--info", "--init-script", str(root / OBSERVER),
                     "-Pp2pkit.windowsDirectoryRoot=" + str(root),
                     "-Pp2pkit.windowsDirectoryRequest=" + str(output / "request.json"),
                     "-Pp2pkit.windowsDirectoryRequestSha256=" + request_hash]
        succeeded = False
        receipt = None
        xml_name = "library/p2p-core/build/test-results/jvmTest/TEST-" + CLASS + ".xml"
        build_info = root / "library/p2p-core/build/generated/buildinfo/commonMain/kotlin/dev/p2pkit/core/BuildInfo.kt"

        def retain_selected():
            # Retain available originals before ANY result predicate, including
            # expected-red/setup/stop/cancellation failure. Never copy arbitrary
            # report members or synthetic payload files into public staging.
            for file in ("test-admission.json", "execution.json", "buildsrc-execution.json"):
                retain_available(output / file, case["public"] / file)
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
            assess_worker_log(regular(case["public"] / "product/product.stdout.log"), request)
            build_info_text = regular(case["public"] / "BuildInfo.kt").decode("utf-8", errors="strict")
            require(re.findall(r'^    public const val COMMIT: String = "([0-9a-f]{40})"$', build_info_text, re.M) ==
                    [case["context"]["expectedCommit"]] and
                    re.findall(r'^    public const val DIRTY: Boolean = (true|false)$', build_info_text, re.M) == ["false"],
                    "Generated BuildInfo does not name the actual clean current/derivative source")
            require(not list(temporary.iterdir()), "Test teardown left fixture residue; not a clean acceptance")
            succeeded = True
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
                after = temporary.lstat()
                require((after.st_dev, after.st_ino) == (info.st_dev, info.st_ino), "Owned test temporary root was replaced")
                rows = inventory(temporary)
                new_json(case["public"] / "temporary-after.json", {"schema": 1, "directory": str(temporary),
                    "device": after.st_dev, "inode": after.st_ino, "empty": not list(temporary.iterdir()),
                    "residue": rows, "productAccepted": succeeded})
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
        lock = None
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
        except Exception as error:
            record["errors"].append(type(error).__name__ + ": " + str(error))
        finally:
            if lock is not None:
                try:
                    lock.close()
                except Exception as error:
                    record["errors"].append("Fallback lease close: " + type(error).__name__)
            record["endedUtc"] = audit.utc()
            new_json(case["public"] / "fallback-stop.json", record)
        return record

    def retire(self, case):
        require(not case["retirementAttempted"], "A retirement attempt cannot overwrite original evidence")
        case["retirementAttempted"] = True
        self.active_public = case["public"]
        errors = []
        state, scope = case["state"], case["scope"]
        record = {"schema": 1, "caseName": case["name"], "roots": case["roots"], "removed": [], "errors": errors,
                  "startedUtc": audit.utc(), "scope": "only this allocation's source copy/home/fixtures/konan/android-user",
                  "statePath": str(state), "initialized": case["initialized"]}
        lock = None
        try:
            survivors = None
            if scope is not None:
                try:
                    survivors = scope.drain()
                    record["ownership"] = scope.description()
                    record["survivors"] = survivors
                except Exception as error:
                    record["drainError"] = type(error).__name__ + ": " + str(error)
            if case["started"] and not all(row["valid"] for row in case["leaves"]):
                record["fallbackStop"] = self.fallback_stop(case)
            require(survivors == [] and record.get("ownership", {}).get("discoveryErrors") == [],
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
        except Exception as error:
            errors.append(type(error).__name__ + ": " + str(error))
        finally:
            if lock is not None:
                try:
                    lock.close()
                except Exception as error:
                    errors.append("Cleanup lease close: " + type(error).__name__)
                    case["safe"] = False
            try:
                if scope is not None:
                    scope.close()
            except Exception as error:
                errors.append("Ownership handle close: " + type(error).__name__)
                case["safe"] = False
            record.update(endedUtc=audit.utc(), complete=case["safe"] and not errors)
            try:
                new_json(case["public"] / "retirement.json", record)
            except Exception:
                case["safe"] = False
                raise
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
        for case in self.cases:
            if not case["retirementAttempted"]:
                try:
                    self.retire(case)
                except Exception as error:
                    errors.append("Partial allocation finalization: " + type(error).__name__ + ": " + str(error))
                    case["safe"] = self.safe = False
        self.active_public = self.public / "admission"
        outer = {"schema": 1, "identity": self.identity, "startedUtc": audit.utc()}
        # Source observation failure must not skip independent owned-worker drain.
        try:
            if source is not None:
                after = self.source(self.root, self.identity["sourceSha"], finalizing=True)
                new_json(self.public / "admission/source-after.json", after)
                require(after == source, "Campaign checkout changed; do not claim acceptance")
        except Exception as error:
            errors.append("Final source observation: " + type(error).__name__ + ": " + str(error))
            self.safe = False
        retired = False
        try:
            survivors = self.scope.drain()
            outer.update(survivors=survivors, ownership=self.scope.description())
            require(survivors == [] and outer["ownership"].get("discoveryErrors") == [], "Outer native ownership did not retire")
            retired = True
        except Exception as error:
            errors.append("Outer finalization: " + type(error).__name__ + ": " + str(error))
            self.safe = False
        finally:
            try:
                self.scope.close()
            except Exception as error:
                errors.append("Outer ownership close: " + type(error).__name__ + ": " + str(error))
                retired = self.safe = False
        # Preserve incomplete allocations/originals; dispose only verified copies.
        if retired and all(case["safe"] for case in self.cases):
            try:
                outer["duplicateCaptureCleanup"] = self.retire_command_copies()
            except Exception as error:
                errors.append("Duplicate capture retirement: " + type(error).__name__ + ": " + str(error))
                self.safe = False
        if self.cancelled:
            self.safe = False
        outer.update(endedUtc=audit.utc(), retirementKnown=retired, complete=self.safe and not errors, errors=list(errors))
        new_json(self.public / "admission/controller-retirement.json", outer)

    def seal_results(self, outcomes, errors):
        for name, outcome in outcomes.items():
            case = next((case for case in self.cases if case["name"] == name), None)
            new_json(self.public / name / "outcome.json", {"schema": 1, "identity": self.identity,
                "caseName": name, **outcome, "retirementComplete": bool(case and case["safe"]),
                "leafExits": [{key: row[key] for key in ("id", "purpose", "status", "valid", "retained")}
                              for row in case["leaves"]] if case else [],
                "retentionErrors": case["retentionErrors"] if case else []})
        new_json(self.public / "admission/outcome.json", {"schema": 1, "identity": self.identity,
            "verdict": "PASS_SCOPED_CONTROL" if self.safe and not errors and not self.cancelled else "NOT_ACCEPTED",
            "errors": errors, "cancelledSignals": self.cancelled, "endedUtc": audit.utc(),
            "limitations": "Not all #141 criteria, full Windows/Linux suites, full gate, release or physical qualification."})
        for name in ("admission", "current", "preimage"):
            seal_public(self.public / name, self.identity, name)
            verify_public(self.public / name, self.identity, name)
        require(not any(char in str(self.public) for char in "\0\r\n"), "Unsafe public output path")
        output = audit.absolute_path(os.environ["GITHUB_OUTPUT"])
        regular(output)  # Actual runner output file, not a symlink or another source.
        with output.open("a", encoding="utf-8") as stream:
            stream.write("public_root=" + str(self.public) + "\nartifacts_ready=true\n")

    def run(self):
        outcomes = {name: {"verdict": "NOT_EXECUTED", "scope": "No product acceptance"} for name in ("current", "preimage")}
        errors, source = [], None
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
                try:
                    if name == "current":
                        self.sdk_and_native(case)
                    outcomes[name] = self.product(case)
                except Exception:
                    try:
                        self.retire(case)
                    except Exception as error:
                        errors.append("Failed-case retirement: " + type(error).__name__ + ": " + str(error))
                        case["safe"] = False
                    raise  # The product's original failure remains authoritative.
                self.retire(case)
                require(case["safe"], "Earlier case retirement is incomplete")
            self.safe = True
        except Exception as error:
            errors.append(type(error).__name__ + ": " + str(error))
            self.safe = False
            try:
                write(self.public / "admission/controller-error.txt", (errors[-1] + "\n").encode("utf-8"))
            except Exception as retention_error:
                errors.append("Controller error retention: " + type(retention_error).__name__)
        finally:
            try:
                self.finalize_resources(source, errors)
            finally:
                # Guaranteed even if resource receipts, artifact sealing or the
                # runner's output channel fail. No owned work starts afterward.
                for number, handler in self.handlers.items():
                    try:
                        signal.signal(number, handler)
                    except Exception as error:
                        errors.append("Signal handler restoration: " + type(error).__name__)
                        self.safe = False
        self.seal_results(outcomes, errors)
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
    except (Exception, KeyboardInterrupt) as error:
        print("Windows directory control NOT_ACCEPTED: " + type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
