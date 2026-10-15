#!/usr/bin/env python3
"""Small hosted-job evidence runner; no cache admission or initial trust protocol.

Trust the reviewed workflow/host and the independent recipient pins supplied by
Actions configuration. Capture command output privately, retire its owned process
domain, bundle closed results, and encrypt with the pinned PUBLIC key only.
Successful uploads contain manifest.json and evidence.tar.gz.gpg. A failed
export may retain failure.json instead; it is diagnostic, never qualification.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_processes
# Reuse only the existing public armor and GPG colon-listing validators. No
# recipient activation dates, historical custody, native authority, or exporter.
from hosted_evidence import _public_armor, _key_identity

SCHEMA = 1
MAX_LOG_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
MAX_REPORTS = 10000
MAX_JSON_BYTES = 1024 * 1024
CODES = frozenset({"PASS", "INPUT", "SOURCE_CHANGED", "SPAWN", "COMMAND_FAILED", "TIMEOUT",
                   "CANCELLED", "OUTPUT_LIMIT", "OUTPUT_IO", "CLEANUP", "REPORTS", "RECIPIENT",
                   "ENCRYPTION", "MANIFEST"})
TASK_NAMES = frozenset({
    "release-tag-controls", "release-identity-controls", "maven-environment-controls",
    "maven-namespace-controls", "maven-coordinate-controls", "maven-upload-controls",
    "wrapper", "layout", "links", "release-metadata", "workflow-contract", "workflow-controls", "workflow-syntax",
    "platform-contract", "version-encoding", "signed-bundle-test",
    "ci-component-test.py", "ci-evidence-test.py", "ci-qualification-test.py", "dependency-update-test.py",
    "embedded-jmdns-aar-test.py", "embedded-jmdns-archive-controls", "intel-bonjour-environment-test.py",
    "application-release-version-test.py", "sample-artifact-identity-test.py",
    "package-sample-apps-test.py", "release-application-set-test.py", "publish-sample-release-test.py",
    "run-platform-tests-test.py", "integrity-policy",
    "lock-coverage", "lock-writer-policy", "check-freemarker-floor-test.py", "check-jackson-floor-test.py",
    "build-plugin-floors", "jvm-tests", "supervisor-controls", "android-tests-and-apk", "desktop-tests-and-installer",
    "native-platform-tests", "abi-graph", "api-abi", "documentation", "sbom", "publication-shape",
    "isolated-consumers", "xcframework", "minimum-apple-os", "swift-ui", "osv-lock-coverage", "osv-scan",
    "prepare-android", "prepare-desktop", "inspect-android", "inspect-desktop", "gradle-stop", "component-setup"})


class EvidenceError(RuntimeError):
    def __init__(self, code):
        super().__init__(code if code in CODES else "INPUT")
        self.code = code if code in CODES else "INPUT"


def require(condition, code="INPUT"):
    if not condition:
        raise EvidenceError(code)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest_file(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return {"sha256": digest.hexdigest(), "bytes": size}


def write_private(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if fd is not None:
            os.close(fd)


def read_json(path, maximum=MAX_JSON_BYTES):
    with Path(path).open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum)
    return json.loads(raw)


class Capture:
    """One bounded private sink and one original pipe owner, on every OS."""
    def __init__(self, pipe, path, limit):
        self.pipe, self.path, self.limit = pipe, path, limit
        self.count, self.eof, self.closed, self.error = 0, False, False, None
        self.thread = threading.Thread(target=self._copy, daemon=True)

    def _copy(self):
        try:
            with self.path.open("xb", buffering=0) as output:
                if os.name == "posix":
                    os.chmod(self.path, 0o600)
                while True:
                    block = self.pipe.read(65536)
                    if not block:
                        self.eof = True
                        break
                    permitted = max(0, self.limit - self.count)
                    if len(block) > permitted:
                        self.error = "OUTPUT_LIMIT"
                    kept = block[:permitted]
                    if kept:
                        view = memoryview(kept)
                        while view:
                            written = output.write(view)
                            if not written:
                                raise OSError("private sink did not advance")
                            self.count += written
                            view = view[written:]
                    # Continue draining until the controller retires the child;
                    # never grow memory/disk beyond this stream's bound.
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            self.error = self.error or "OUTPUT_IO"
        finally:
            try:
                self.pipe.close()
                self.closed = True
            except BaseException:
                self.error = self.error or "CLEANUP"


def run_command(argv, *, cwd, environment, private, timeout, cancelled=None,
                log_limit=MAX_LOG_BYTES, cleanup_seconds=15.0):
    """Actual command + unchanged maintained POSIX/Windows ownership backend.

    Ordinary hosted-runner trust: POSIX marker-inheriting descendants, Windows
    kernel Job Object. This is not containment of a malicious runner/child that
    erases its ownership markers. No process-name kill or shell interpolation.
    """
    require(type(timeout) in (int, float) and 0 < timeout <= 21600)
    require(type(log_limit) is int and 0 < log_limit <= MAX_LOG_BYTES)
    private = Path(private)
    private.mkdir(mode=0o700, parents=False, exist_ok=False)
    job, invocation = uuid.uuid4().hex, uuid.uuid4().hex
    home = Path(environment.get("GRADLE_USER_HOME", str(private / "gradle-home"))).absolute()
    home.mkdir(parents=True, exist_ok=True)
    env = audit_processes.ownership_environment(dict(environment), job, invocation,
        str(private), str(home), allow_new_context=True)
    begin = time.monotonic()
    end = begin + timeout
    scope, child, captures = None, None, []
    code, returncode, cleanup_known = "PASS", None, False
    native_error = None
    timed_out = False
    cancelled = cancelled or (lambda: False)
    try:
        scope = audit_processes.make_scope(job, invocation, str(private), str(home))
        child = scope.spawn(list(argv), str(cwd), env)
        captures = [Capture(child.stdout, private / "stdout.log", log_limit),
                    Capture(child.stderr, private / "stderr.log", log_limit)]
        for capture in captures:
            capture.thread.start()
        while True:
            if cancelled():
                code = "CANCELLED"
                break
            if any(item.error for item in captures):
                code = next(item.error for item in captures if item.error)
                break
            returncode = child.poll()
            if time.monotonic() >= end:
                code, timed_out = "TIMEOUT", True
                break
            if returncode is not None:
                code = "PASS" if returncode == 0 else "COMMAND_FAILED"
                break
            time.sleep(min(0.1, max(0.0, end - time.monotonic())))
    except BaseException as error:
        code = "SPAWN" if child is None else "CLEANUP"
        native_error = native_error_diagnostic(error)
    finally:
        cleanup_end = time.monotonic() + cleanup_seconds
        # spawn can register a real child before its discovery raises. Retain all
        # original leaders/pipes BEFORE close clears the POSIX leader registry.
        leaders = tuple(getattr(scope, "leaders", ())) if scope else ()
        pipes = tuple(stream for leader in leaders for stream in (leader.stdout, leader.stderr)
                      if stream is not None)
        try:
            if scope is not None:
                live = scope.drain(grace=3.0, kill_wait=max(1.0, cleanup_seconds - 5.0), deadline=cleanup_end)
                cleanup_known = not live and not scope.discovery_errors
                for leader in leaders:
                    remaining = max(0.01, cleanup_end - time.monotonic())
                    leader.wait(timeout=remaining)
                if child is not None:
                    returncode = child.returncode
        except BaseException:
            cleanup_known = False
        finally:
            try:
                if scope is not None:
                    scope.close()
            except BaseException:
                cleanup_known = False
            for capture in captures:
                if capture.thread.ident is not None:
                    capture.thread.join(timeout=max(0.0, cleanup_end - time.monotonic()))
                if capture.thread.is_alive() or not capture.eof or not capture.closed:
                    cleanup_known = False
                if capture.error and code == "PASS":
                    code = capture.error
            # Unadopted originals on an exceptional post-spawn path still close.
            captured = {id(item.pipe) for item in captures if item.thread.ident is not None}
            for pipe in pipes:
                if id(pipe) not in captured:
                    try:
                        pipe.close()
                    except BaseException:
                        cleanup_known = False
        if not cleanup_known and code == "PASS":
            code = "CLEANUP"
    return {"exitCode": returncode, "timedOut": timed_out, "cleanupKnown": cleanup_known,
            "stage": "COMMAND", "code": code, "nativeError": native_error,
            "elapsedSeconds": round(time.monotonic() - begin, 6)}


def git_value(root, *arguments):
    # Fixed, small source-metadata queries only; the arbitrary actual task uses
    # run_command. Git output/error is never echoed to Actions.
    result = subprocess.run(["git", "-C", str(root), *arguments], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    require(result.returncode == 0 and len(result.stdout) <= MAX_JSON_BYTES, "SOURCE_CHANGED")
    return result.stdout.decode("utf-8").strip()


def source_identity(root):
    commit, tree = git_value(root, "rev-parse", "HEAD"), git_value(root, "rev-parse", "HEAD^{tree}")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) and re.fullmatch(r"[0-9a-f]{40}", tree), "SOURCE_CHANGED")
    require(not git_value(root, "status", "--porcelain=v1", "--untracked-files=no"), "SOURCE_CHANGED")
    versions = re.findall(r"^VERSION_NAME=(\S+)$", (root / "gradle.properties").read_text(), re.M)
    require(len(versions) == 1 and re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+_-]{0,79}", versions[0]), "SOURCE_CHANGED")
    return {"commit": commit, "tree": tree, "version": versions[0]}


def github_identity(environment, source):
    def value(name, pattern):
        result = environment.get(name, "")
        require(re.fullmatch(pattern, result))
        return result
    repository = value("GITHUB_REPOSITORY", r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
    require(value("GITHUB_SHA", r"[0-9a-f]{40}") == source["commit"], "SOURCE_CHANGED")
    workflow = value("GITHUB_WORKFLOW_REF", r"[^\r\n]{1,512}")
    prefix = repository + "/"
    require(workflow.startswith(prefix) and "@" in workflow)
    workflow_path = workflow[len(prefix):].rsplit("@", 1)[0]
    require(re.fullmatch(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml", workflow_path))
    return {"repository": repository, "runId": value("GITHUB_RUN_ID", r"[1-9][0-9]{0,19}"),
            "runAttempt": value("GITHUB_RUN_ATTEMPT", r"[1-9][0-9]{0,19}"),
            "workflowPath": workflow_path,
            "workflowSha": value("GITHUB_WORKFLOW_SHA", r"[0-9a-f]{40}"),
            "jobId": value("GITHUB_JOB", r"[A-Za-z_][A-Za-z0-9_-]{0,99}")}


def collect_reports(root, patterns, destination):
    destination.mkdir(mode=0o700)
    selected, total = set(), 0
    for pattern in patterns:
        require(not Path(pattern).is_absolute() and ".." not in Path(pattern).parts, "REPORTS")
        for path in root.glob(pattern):
            if path.is_dir() and not path.is_symlink():
                continue
            relative = path.relative_to(root)
            require(not any((root.joinpath(*relative.parts[:i])).is_symlink()
                            for i in range(1, len(relative.parts) + 1)), "REPORTS")
            info = path.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "REPORTS")
            if relative in selected:
                continue
            selected.add(relative)
            total += info.st_size
            require(len(selected) <= MAX_REPORTS and total <= MAX_BUNDLE_BYTES, "REPORTS")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(path, target)
            if os.name == "posix":
                os.chmod(target, 0o600)
            require(path.stat().st_size == info.st_size and target.stat().st_size == info.st_size, "REPORTS")


def archive_private(bundle, destination):
    files, total = [], 0
    for path in sorted(bundle.rglob("*")):
        info = path.lstat()
        require(not path.is_symlink() and (path.is_dir() or stat.S_ISREG(info.st_mode)), "REPORTS")
        if path.is_dir():
            continue
        total += info.st_size
        require(len(files) < MAX_REPORTS and total <= MAX_BUNDLE_BYTES, "REPORTS")
        files.append({"path": path.relative_to(bundle).as_posix(), **digest_file(path)})
    with tarfile.open(destination, "x:gz", format=tarfile.PAX_FORMAT) as archive:
        for record in files:
            path = bundle / record["path"]
            archive.add(path, arcname=record["path"], recursive=False)
            require(digest_file(path) == {key: record[key] for key in ("sha256", "bytes")}, "REPORTS")
    if os.name == "posix":
        os.chmod(destination, 0o600)
    return files


def encrypt_archive(archive, output, key_raw, expected_sha, expected_fingerprint, work, environment):
    require(re.fullmatch(r"[0-9a-f]{64}", expected_sha or "") and
            re.fullmatch(r"[A-Fa-f0-9]{40}", expected_fingerprint or ""), "RECIPIENT")
    require(hashlib.sha256(key_raw).hexdigest() == expected_sha, "RECIPIENT")
    _public_armor(key_raw)  # Reject secret packets even before a GPG invocation.
    key_file = work / "recipient.asc"
    write_private(key_file, key_raw)
    home = work / "gnupg"
    home.mkdir(mode=0o700)
    gpg = shutil.which("gpg", path=environment.get("PATH"))
    require(gpg is not None, "RECIPIENT")
    # The native supervisor sets cwd=work. Relative forward-slash arguments name
    # the same files for both native Windows GPG and Git/MSYS GPG; native drive
    # and backslash syntax is not a portable GPG homedir/filename contract.
    def filename(path):
        try:
            return os.path.relpath(path, work).replace(os.sep, "/")
        except ValueError:
            raise EvidenceError("ENCRYPTION") from None  # Different Windows drives.
    base = [gpg, "--no-options", "--batch", "--no-tty", "--no-autostart", "--pinentry-mode", "error",
            "--homedir", filename(home), "--no-auto-key-retrieve"]
    environment = {key: value for key, value in environment.items() if key in {
        "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR",
        "LANG", "LC_ALL", "PATHEXT"}}
    # Public key only, no agent/keyserver/private-key lookup. GPG output remains
    # private. Use the same cross-platform process supervisor as the real task.
    def invoke(label, arguments, timeout=60):
        directory = work / label
        result = run_command([*base, *arguments], cwd=work, environment=environment,
                             private=directory, timeout=timeout, log_limit=MAX_JSON_BYTES)
        if not (result["code"] == "PASS" and result["exitCode"] == 0 and result["cleanupKnown"]):
            error = EvidenceError("ENCRYPTION")
            # Only this source-owned exception carries a fixed public diagnostic.
            # Unknown writer retirement must also prevent erasing its private files.
            error.encryption_diagnostic = {
                "phase": label, "outcome": public_outcome(result),
                "categories": gpg_failure_categories(directory) if result["cleanupKnown"] else []}
            raise error
        return (directory / "stdout.log").read_bytes()
    listing = invoke("key-show", ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint",
                                   "--import-options", "show-only", "--import", filename(key_file)])
    fingerprint, expires_at = _key_identity(listing, expected_fingerprint.upper())
    invoke("key-import", ["--import", filename(key_file)])
    imported = invoke("key-list", ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint", "--list-keys"])
    require(_key_identity(imported, expected_fingerprint.upper()) == (fingerprint, expires_at), "RECIPIENT")
    invoke("encrypt", ["--trust-model", "always", "--compress-algo", "none", "--recipient", fingerprint + "!",
                        "--output", filename(output), "--encrypt", filename(archive)], timeout=300)
    require(output.is_file() and 32 < output.stat().st_size <= MAX_BUNDLE_BYTES + 16 * 1024 * 1024, "ENCRYPTION")
    return {**digest_file(output), "recipientFingerprint": expected_fingerprint.upper()}


def tool_identity(tools_file):
    result = {"python": {"version": platform.python_version(),
                         "executableSha256": digest_file(Path(sys.executable).resolve())["sha256"]}}
    if tools_file.exists():
        supplied = read_json(tools_file)
        require(type(supplied) is dict and len(supplied) <= 12)
        for name, item in supplied.items():
            require(name in {"java", "gradle", "node", "xcode", "android-sdk", "gpg"} and type(item) is dict and
                    set(item) == {"version", "executableSha256"})
            require(type(item["version"]) is str and re.fullmatch(r"[A-Za-z0-9 ._+()/-]{1,120}", item["version"]) and
                    re.fullmatch(r"[0-9a-f]{64}", item["executableSha256"]))
            result[name] = item
    return result


def component_tasks(root, component):
    """Optional public diagnostic, never a replacement for actual task outcome.

    Only fixed source-owned task names and integral exit codes leave the private
    report. Missing/malformed reports remain unavailable, not invented success.
    """
    try:
        report = read_json(root / "build/reports/ci-component" / (component + ".json"), 64 * 1024)
        require(type(report) is dict and set(report) == {"component", "tasks", "exitCode"} and
                report["component"] == component and type(report["exitCode"]) is int)
        rows = report["tasks"]
        require(type(rows) is list and len(rows) <= 100)
        for row in rows:
            require(type(row) is dict and set(row) == {"task", "exitCode"} and
                    type(row["task"]) is str and row["task"] in TASK_NAMES and
                    type(row["exitCode"]) is int and -(2**31) <= row["exitCode"] < 2**32)
        return [{"task": row["task"], "exitCode": row["exitCode"]} for row in rows]
    except (OSError, ValueError, TypeError, KeyError, EvidenceError):
        return None


def junit_failures(root, source_commit="HEAD"):
    """Project failed JUnit cases onto public source names, never error text.

    Unmatched/dynamic names remain private. This diagnostic is not acceptance;
    malformed/oversized reports cannot create passing test evidence.
    """
    def bounded(path, limit):
        require(not any(p.is_symlink() for p in (path, *path.parents)))
        info = path.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit)
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        require(len(raw) == info.st_size)
        return raw

    try:
        blobs = {}
        for record in git_value(root, "--no-replace-objects", "ls-tree", "-r", "-z", source_commit).split("\0"):
            if record:
                identity, name = record.split("\t", 1)
                mode, kind, blob = identity.split()
                if mode in ("100644", "100755") and kind == "blob" and name.endswith(".kt"):
                    blobs[name] = blob
    except (OSError, ValueError, subprocess.SubprocessError, EvidenceError):
        return []

    rows, consumed = [], 0
    for number, path in enumerate(root.glob("**/build/test-results/**/TEST-*.xml")):
        if number >= MAX_REPORTS or consumed >= 32 * 1024 * 1024 or len(rows) >= 32:
            break
        try:
            raw = bounded(path, 4 * 1024 * 1024)
            consumed += len(raw)
            if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", raw, re.I):
                continue
            document = ET.fromstring(raw)
            for case in document.iter("testcase"):
                failures = [node for node in case if node.tag in ("failure", "error")]
                if not failures or len(rows) >= 32:
                    continue
                classname, method = case.get("classname", ""), case.get("name", "")
                if not re.fullmatch(r"(?:[A-Za-z_]\w*\.)+[A-Za-z_]\w*", classname):
                    continue
                # Gradle may append a target suffix; publish only the source identifier.
                match = re.fullmatch(r"([A-Za-z_]\w*)(?:\(\)|\[[A-Za-z0-9_-]{1,40}\])?", method)
                if not match:
                    continue
                method = match[1]
                package, cls = classname.rsplit(".", 1)
                for group in ("library", "samples"):
                    for source in (root / group).glob("*/src/*Test/**/" + cls + ".kt"):
                        relative = source.relative_to(root).as_posix()
                        if relative not in blobs:
                            continue
                        content = bounded(source, 1024 * 1024)
                        blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
                        if blob != blobs[relative]:
                            continue
                        text = content.decode("utf-8")
                        if (not re.search(r"(?m)^package " + re.escape(package) + r"\s*$", text) or
                            not re.search(r"\bclass\s+" + re.escape(cls) + r"\b", text) or
                            not re.search(r"\bfun\s+" + re.escape(method) + r"\s*\(", text)):
                            continue
                        kinds = {"java.lang.AssertionError": "ASSERTION", "org.opentest4j.AssertionFailedError": "ASSERTION",
                                 "kotlinx.coroutines.TimeoutCancellationException": "TIMEOUT",
                                 "java.net.NoRouteToHostException": "NETWORK_NO_ROUTE"}
                        row = {"source": source.relative_to(root).as_posix(), "test": method,
                               "kinds": sorted({kinds.get(node.get("type"), "OTHER") for node in failures})}
                        if row not in rows:
                            rows.append(row)
        except (OSError, ValueError, UnicodeError, ET.ParseError, EvidenceError):
            continue
    return rows[:32]


def failure_diagnostics(root, command_directory, source_commit="HEAD"):
    """Public error identifiers only; logs/payloads/paths remain encrypted.

    These observations help diagnose a failed command, never qualify it. Scan
    the already bounded closed captures; never copy arbitrary error messages.
    """
    categories, tasks, publication_lines, platform_lines = set(), set(), [], []
    modules = {"p2p-core", "p2p-transport-lan", "p2p-rpc", "p2p-network-provisioning-android",
               "p2p-network-provisioning-desktop", "p2p-sample-android", "p2p-sample-desktop",
               "p2p-sample-desktop-ui", "p2p-sample-diagnostics", "sample-kmp-shared", "p2p-sample-rpc", "buildSrc"}
    task_names = {"allTests", "check", "jvmTest", "test", "testDebugUnitTest", "testAndroidHostTest", "iosX64Test",
                  "iosSimulatorArm64Test", "dokkaGeneratePublicationHtml", "checkKotlinAbi", "checkAndroidAbi",
                  "publishToMavenLocal", "assembleDebug", "packageMsi", "packageDmg", "packageDeb", "compileJava"}
    task_names.update(prefix + target for prefix in ("compileKotlin", "compileTestKotlin", "linkDebugTest", "cinteropP2pkit_nw")
                      for target in ("Jvm", "IosArm64", "IosSimulatorArm64", "IosX64"))
    phase_labels = {"simulator-macos-version", "simulator-xcode-version", "simulator-first-launch",
                    "simulator-runtimes", "intel-bootstatus-help", "simulator-devices", "intel-boot",
                    "intel-bootstatus", "intel-prelaunch", "intel-retire-before", "intel-shutdown", "intel-retire-after"}
    known = {
        b"Dependency verification failed": "DEPENDENCY_INTEGRITY",
        b"Unresolved reference": "COMPILATION_UNRESOLVED_REFERENCE",
        b"unresolved link": "DOCUMENTATION_UNRESOLVED_LINK",
        b"NoRouteToHostException": "NETWORK_NO_ROUTE",
        b"host_not_announced": "LAN_HOST_NOT_ANNOUNCED",
        b"SIMULATOR_UNADMITTED_XCODE": "SIMULATOR_XCODE_MISMATCH",
        b"SIMULATOR_RUNTIME_UNAVAILABLE_OR_CHANGED": "SIMULATOR_RUNTIME_MISMATCH",
        b"INTEL_PHASE_FAILED": "SIMULATOR_COMMAND_FAILED",
        b"extraction failed on specified lockfile": "OSV_LOCKFILE_EXTRACTION_FAILED",
        b"cannot determine extractor": "OSV_UNSUPPORTED_LOCKFILE",
        b"FAIL embedded JmDNS": "PUBLICATION_EMBEDDED_JMDNS",
        b"publishing artifact set incomplete": "PUBLICATION_INCOMPLETE",
        b"Cannot convert the provided notation": "GRADLE_INVALID_NOTATION",
        b"Could not determine the dependencies of task": "GRADLE_TASK_DEPENDENCIES",
        b"Could not resolve all files": "GRADLE_DEPENDENCY_RESOLUTION",
        b"could not determine extractor": "OSV_UNSUPPORTED_LOCKFILE",
    }
    for name in ("stdout.log", "stderr.log"):
        try:
            stream = (Path(command_directory) / name).open("rb")
        except OSError:
            continue  # A refused spawn may have no original output pipes.
        with stream:
            for line in stream:
                # The captures themselves are bounded; cap each parsed line too.
                if len(line) > 4096:
                    continue
                location = re.fullmatch(rb"PUBLICATION_EMBEDDED_CHECK_LINES ([0-9]{1,5}(?:,[0-9]{1,5}){0,15})\s*", line)
                if location:
                    publication_lines = [int(value) for value in location[1].split(b",")]
                location = re.fullmatch(rb"PLATFORM_CHECK_LINES ([0-9]{1,5}(?:,[0-9]{1,5}){0,15})\s*", line)
                if location:
                    platform_lines = [int(value) for value in location[1].split(b",")]
                for token, category in known.items():
                    if token.lower() in line.lower():
                        categories.add(category)
                match = re.fullmatch(rb"> Task (:(?:p2p-[a-z0-9-]+|sample-kmp-shared|buildSrc):[A-Za-z0-9_:.-]{1,120}) FAILED\s*", line)
                if match:
                    task = match[1].decode("ascii")
                    pieces = task.split(":")
                    if len(pieces) == 3 and pieces[1] in modules and pieces[2] in task_names:
                        tasks.add(task)
    phases = []
    for path in sorted((root / "build/reports/platform-tests").glob("*/intel-simulator/*/result.json")):
        try:
            row = read_json(path, 64 * 1024)
            if type(row) is not dict:
                continue
            label = row.get("label")
            if (type(label) is str and label in phase_labels
                    and "exitCode" in row and (row["exitCode"] is None or
                        type(row["exitCode"]) is int and -255 <= row["exitCode"] <= 255)
                    and all(type(row.get(k)) is bool for k in ("timedOut", "outputLimitExceeded", "ownedGroupDrained"))):
                phases.append({k: row[k] for k in ("label", "exitCode", "timedOut", "outputLimitExceeded", "ownedGroupDrained")})
        except (OSError, ValueError, TypeError):
            continue
    platform_reports = []
    for path in sorted((root / "build/reports/platform-tests").glob("*/execution.json")):
        try:
            report = read_json(path, MAX_JSON_BYTES)
            if type(report) is not dict or type(report.get("tests")) is not dict:
                continue
            tests = []
            for task, row in report["tests"].items():
                pieces = task.split(":")
                if (len(pieces) == 3 and pieces[1] in modules and pieces[2] in task_names and
                    type(row) is dict and type(row.get("outcome")) is str and row["outcome"] in
                    {"EXECUTED", "FAILED", "NO_SOURCE", "SKIPPED", "UP-TO-DATE", "FROM-CACHE", "NOT_COMPLETED", "NOT_REQUESTED"} and
                    all(type(row.get(k)) is int and 0 <= row[k] <= 1000000 for k in ("passed", "failed", "skipped"))):
                    tests.append({"task": task, **{k: row[k] for k in ("outcome", "passed", "failed", "skipped")}})
            platform_reports.append({"buildFailed": report.get("buildFailed") if type(report.get("buildFailed")) is bool else None,
                                     "tests": sorted(tests, key=lambda row: row["task"])[:64]})
        except (OSError, ValueError, TypeError):
            continue
    return {"categories": sorted(categories), "failedGradleTasks": sorted(tasks), "simulatorPhases": phases[:32],
            "embeddedPublicationCheckLines": publication_lines, "platformCheckLines": platform_lines,
            "platformTests": platform_reports[:8], "failedSourceTests": junit_failures(root, source_commit)}


def public_outcome(value):
    """Finite process metadata only; never copy a command or an exception."""
    if (type(value) is not dict or type(value.get("code")) is not str or value["code"] not in CODES or
            "exitCode" not in value or
            not (value.get("exitCode") is None or type(value.get("exitCode")) is int and
                 -(2**31) <= value["exitCode"] < 2**32) or
            any(type(value.get(key)) is not bool for key in ("timedOut", "cleanupKnown"))):
        return None
    result = {key: value[key] for key in ("code", "exitCode", "timedOut", "cleanupKnown")}
    if "nativeError" in value:
        result["nativeError"] = value["nativeError"]
    return result


def native_error_diagnostic(error):
    """Only native numeric codes or exact source-owned operation names escape."""
    result = {"kind": "UNKNOWN", "operation": None, "errno": None, "winerror": None}
    if isinstance(error, OSError):
        result["kind"] = "OS"
        for key in ("errno", "winerror"):
            value = getattr(error, key, None)
            if type(value) is int and 0 <= value < 2**32:
                result[key] = value
    elif type(error) is audit_processes.OwnershipError and len(error.args) == 1 and type(error.args[0]) is str:
        message = error.args[0]
        operations = {"CreateJobObjectW", "SetInformationJobObject", "CreatePipe", "SetHandleInformation",
                      "GetHandleInformation", "CreateProcessW (atomic job assignment)", "Initialize attributes",
                      "HANDLE_LIST", "JOB_LIST", "pre-resume IsProcessInJob", "GetProcessTimes",
                      "GetExitCodeProcess", "CloseHandle", "QueryInformationJobObject", "IsProcessInJob",
                      "OpenProcess owned-job member", "TerminateJobObject", "TerminateJobObject failed launch",
                      "DuplicateHandle owned input", "DuplicateHandle owned output"}
        match = re.fullmatch(r"Windows (.{1,64}) failed: error ([0-9]{1,10})", message)
        if match and match[1] in operations and int(match[2]) < 2**32:
            result.update(kind="WIN32", operation=match[1], winerror=int(match[2]))
        else:
            fixed = {"Unsupported Windows Job Object ABI layout": "WINDOWS_ABI",
                     "Windows audit ownership requires native 64-bit Python": "WINDOWS_NATIVE_PYTHON",
                     "Native Windows command requires .exe/.com or explicit interpreter": "WINDOWS_EXECUTABLE_TYPE",
                     "Command executable does not resolve to an existing file": "EXECUTABLE_UNAVAILABLE"}
            if message in fixed:
                result.update(kind="OWNERSHIP", operation=fixed[message])
    return result


def gpg_failure_categories(directory):
    """Classify closed GPG stderr without publishing any of its text."""
    tokens = {
        b"invalid option": "UNSUPPORTED_OPTION",
        b"permission denied": "ACCESS_DENIED",
        b"no such file or directory": "FILE_NOT_FOUND",
        b"can't connect to the keyboxd": "KEYBOXD_UNAVAILABLE",
        b"keyblock resource": "KEYRING_RESOURCE",
        b"can't connect to the agent": "AGENT_UNAVAILABLE",
        b"no gpg-agent running": "AGENT_UNAVAILABLE",
        b"error spawning": "HELPER_SPAWN",
        b"no valid openpgp data found": "RECIPIENT_PARSE",
        b"unusable public key": "RECIPIENT_UNUSABLE",
        b"encryption failed": "ENCRYPTION_FAILED",
    }
    try:
        with (directory / "stderr.log").open("rb") as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            return []
        return sorted({category for token, category in tokens.items() if token in raw.lower()})
    except OSError:
        return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-glob", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    stage, private, output, previous = "INPUT", None, None, {}
    source, github, outcome, root = None, None, None, None
    cleanup_known = True
    cancelled = threading.Event()
    try:
        require(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.component))
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        require(command and all(type(item) is str and item and "\0" not in item for item in command))
        root = args.source_root.resolve()
        output = args.output_dir.absolute()
        require(not output.exists() and root not in output.parents, "INPUT")
        output.mkdir(parents=True, mode=0o700)
        private = Path(tempfile.mkdtemp(prefix="ci-evidence-private-", dir=os.environ.get("RUNNER_TEMP")))
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, lambda _s, _f: cancelled.set())
        started = utc()
        stage = "SOURCE"
        source = source_identity(root)
        github = github_identity(os.environ, source)
        environment = dict(os.environ)
        tools_file = private / "tools.json"
        environment["CI_EVIDENCE_TOOLS_FILE"] = str(tools_file)
        stage = "COMMAND"
        cleanup_known = False
        outcome = run_command(command, cwd=root, environment=environment, private=private / "command",
                              timeout=args.timeout_seconds, cancelled=cancelled.is_set)
        cleanup_known = outcome["cleanupKnown"]
        require(cleanup_known, "CLEANUP")
        stage = "SOURCE"
        require(source_identity(root) == source, "SOURCE_CHANGED")
        stage = "REPORTS"
        bundle = private / "bundle"
        bundle.mkdir(mode=0o700)
        for name in ("stdout.log", "stderr.log"):
            shutil.copyfile(private / "command" / name, bundle / name)
        collect_reports(root, args.report_glob, bundle / "reports")
        write_private(bundle / "run.json", encoded({"source": source, "github": github, "command": command,
                                                     "outcome": outcome}))
        archive = private / "evidence.tar.gz"
        reports = archive_private(bundle, archive)
        stage = "RECIPIENT"
        with (root / ".github/ci-evidence-recipient.asc").open("rb") as public_key:
            key_raw = public_key.read(64 * 1024 + 1)
        require(0 < len(key_raw) <= 64 * 1024, "RECIPIENT")
        ciphertext = encrypt_archive(archive, output / "evidence.tar.gz.gpg", key_raw,
            os.environ.get("CI_EVIDENCE_RECIPIENT_SHA256", ""),
            os.environ.get("CI_EVIDENCE_RECIPIENT_FINGERPRINT", ""), private, environment)
        stage = "MANIFEST"
        manifest = {"schema": SCHEMA, "component": args.component, "source": source, "github": github,
            "host": {"platform": platform.system(), "arch": platform.machine(),
                     "runnerEnvironment": os.environ.get("RUNNER_ENVIRONMENT", "")},
            "timing": {"startedAt": started, "completedAt": utc()}, "tools": tool_identity(tools_file),
            "command": {"sha256": hashlib.sha256(encoded(command)).hexdigest()}, "outcome": outcome,
            "taskResults": component_tasks(root, args.component),
            "failureDiagnostics": failure_diagnostics(root, private / "command", source["commit"]) if outcome["code"] != "PASS" else None,
            "reports": reports, "privateArchive": digest_file(archive), "ciphertext": ciphertext}
        write_private(output / "manifest.json", encoded(manifest))
        print("CI_EVIDENCE " + ("PASS" if outcome["code"] == "PASS" else "FAIL") + " " + outcome["code"])
        return 0 if outcome["code"] == "PASS" else 1
    except BaseException as error:
        code = error.code if type(error) is EvidenceError else "INPUT"
        encryption = getattr(error, "encryption_diagnostic", None) if type(error) is EvidenceError else None
        if encryption is not None and (encryption["outcome"] is None or
                                       not encryption["outcome"]["cleanupKnown"]):
            cleanup_known = False
        # Never render an exception, command, private path, GPG diagnostic or env.
        print("CI_EVIDENCE FAIL " + stage + " " + code, file=sys.stderr)
        try:
            if output is not None and output.is_dir():
                # No partial uploadable public receipt/ciphertext is a success.
                for name in ("manifest.json", "evidence.tar.gz.gpg"):
                    (output / name).unlink(missing_ok=True)
                # Explicitly NOT a qualification manifest. The job remains failed;
                # consumers still require manifest.json plus matching ciphertext.
                failure = {"schema": SCHEMA, "kind": "CI_EVIDENCE_FAILURE",
                    "component": args.component if re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.component) else None,
                    "source": source, "github": github, "stage": stage, "code": code,
                    "outcome": public_outcome(outcome), "encryptionDiagnostic": encryption,
                    "taskResults": component_tasks(root, args.component) if source is not None else None,
                    "failureDiagnostics": failure_diagnostics(root, private / "command", source["commit"])
                        if source is not None and outcome is not None and outcome["cleanupKnown"] else None}
                write_private(output / "failure.json", encoded(failure))
        except BaseException:
            # An OS cleanup error must not print a private filename/exception or
            # convert this failure to PASS. Job/API failure still denies intake.
            print("CI_EVIDENCE CLEANUP UNKNOWN", file=sys.stderr)
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if private is not None and cleanup_known:
            shutil.rmtree(private, ignore_errors=True)
        # Unknown writer retirement retains the private directory for runner
        # teardown; never erase evidence while a possible original writer lives.


if __name__ == "__main__":
    raise SystemExit(main())
