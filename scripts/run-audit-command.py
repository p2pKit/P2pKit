#!/usr/bin/env python3
"""Opt-in, source-bound audit leaf/command execution with retained final receipts.

This is an evidence/ownership adapter, not a replacement for any product assessor.
A successful receipt proves only this invocation's execution and finalization. It
never turns preexisting XML, host tests or simulator tests into external validation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from typing import Any

# Importing the adapter must not create untracked __pycache__ in the bound source.
sys.dont_write_bytecode = True
from audit_processes import CHAIN_ENV, OwnershipError, STATE_ENV, host_role, make_scope, ownership_environment

INFRASTRUCTURE_EXIT = 125
HOSTS = ("windows-x64", "macos-arm64", "macos-x64", "linux-x64")
JVM_ARGUMENTS = "-Xmx2048m -XX:MaxMetaspaceSize=768m -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8"
AUDIT_FLAGS = ["--no-daemon", "--console=plain", "--dependency-verification", "strict", "--rerun-tasks",
               "--no-build-cache", "--no-configuration-cache", "--no-parallel", "--max-workers=2",
               "-Pkotlin.compiler.execution.strategy=in-process", f"-Dorg.gradle.jvmargs={JVM_ARGUMENTS}"]
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_FILES = 20000
MAX_CLEANUP_ENTRIES = 250000
MAX_REMOVAL_DETAIL_BYTES = 32768
LOCK_NAME = "gradle.lock"


class AuditError(RuntimeError):
    pass


class AuditParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise AuditError(message)


def require(condition: Any, message: str) -> None:
    if not condition:
        raise AuditError(message)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_digest(path: Path, limit: int = MAX_ARCHIVE_BYTES) -> str:
    hasher, total = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            total += len(block)
            require(total <= limit, "Evidence/policy file exceeded its admitted byte bound")
            hasher.update(block)
    return hasher.hexdigest()


def reject_symlinks(path: Path) -> None:
    for candidate in [path, *path.parents]:
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400),
                "Symlink/reparse-point path is not an owned audit path")


def absolute_path(value: str, *, exists: bool = True) -> Path:
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "Audit path must be absolute without '..'")
    reject_symlinks(path)
    path = path.resolve(strict=exists)
    if exists:
        require(path.exists(), "Required audit path is missing")
    return path


def within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, "Duplicate audit JSON key")
        value[key] = item
    return value


def read_json(path: Path) -> dict[str, Any]:
    reject_symlinks(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    require(0 < len(raw) <= MAX_JSON_BYTES, "Audit JSON is empty or exceeds its bound")
    value = json.loads(raw, object_pairs_hook=unique_object,
                       parse_constant=lambda _: (_ for _ in ()).throw(AuditError("Nonfinite audit JSON")))
    require(isinstance(value, dict), "Audit JSON root is not an object")
    return value


def new_file(path: Path) -> Any:
    reject_symlinks(path)
    require(path.parent.is_dir(), "New audit file parent is missing")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    return os.fdopen(os.open(path, flags, 0o600), "wb")


def write_new_json(path: Path, value: Any) -> None:
    with new_file(path) as stream:
        stream.write(json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def git(root: Path, *args: str) -> bytes:
    env = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_EXTERNAL_DIFF"):
        env.pop(key, None)
    result = subprocess.run(["git", "--no-replace-objects", "-C", str(root), *args], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    require(result.returncode == 0, "Source-binding Git command failed")
    return result.stdout


def source_snapshot(root: Path) -> dict[str, str]:
    top = Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel").rstrip(b"\r\n"))).resolve()
    require(top == root, "Audit cwd is not the admitted repository root")
    commit = git(root, "rev-parse", "HEAD").decode("ascii").strip()
    tree = git(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all").decode("utf-8", errors="surrogateescape")
    diff = git(root, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD")
    return {"commit": commit, "tree": tree, "status": status, "diffSha256": digest(diff)}


def existing_lstat(path: Path) -> os.stat_result | None:
    # Only genuine absence is optional. Permission/I/O failures must not silently
    # turn a source or evidence directory into an empty successful inventory.
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def physical_directory_present(path: Path) -> bool:
    reject_symlinks(path)
    info = existing_lstat(path)
    if info is None:
        return False
    require(stat.S_ISDIR(info.st_mode), "Expected physical directory is not a directory")
    return True


def immediate_output_roots(parent: Path) -> list[Path]:
    if not physical_directory_present(parent):
        return []
    paths = []
    with os.scandir(parent) as entries:
        for count, entry in enumerate(entries, start=1):
            require(count <= MAX_ARCHIVE_FILES, "Source module entry count exceeds its bound")
            info = entry.stat(follow_symlinks=False)
            # A link is not an admitted module directory. Do not inspect its
            # target merely to decide whether to omit it from this module map.
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                continue
            if stat.S_ISDIR(info.st_mode):
                paths.append(Path(entry.path) / "build")
    return sorted(paths)


def output_roots(root: Path) -> list[Path]:
    paths = [root / "build", root / "buildSrc" / "build"]
    for parent in (root / "library", root / "samples"):
        paths.extend(immediate_output_roots(parent))
    return paths


def disposable_roots(root: Path) -> list[Path]:
    # This one generated project has a committed XcodeGen source and is explicitly
    # ignored. Never infer arbitrary *.xcodeproj or source directories named build.
    return [*output_roots(root), root / "samples/iosApp/p2pkit-sample.xcodeproj"]


def java_policy() -> tuple[bytes, list[str]]:
    homes: list[str] = []
    for key in ("JAVA_HOME", "P2PKIT_AUDIT_JDK21"):
        value = os.environ.get(key)
        if not value:
            continue
        # setup-java may use a symlinked tool installation. Canonicalize the Java
        # home but never permit symlinked state/evidence/cleanup paths.
        candidate = Path(value)
        require(candidate.is_absolute(), f"{key} must be an absolute JDK directory")
        home = candidate.resolve(strict=True)
        require(home.is_dir(), f"{key} is not a JDK directory")
        suffix = ".exe" if os.name == "nt" else ""
        require((home / "bin" / f"java{suffix}").is_file() and (home / "bin" / f"javac{suffix}").is_file(),
                f"{key} lacks java/javac executables")
        if os.name != "nt":
            require(all(os.access(home / "bin" / binary, os.X_OK) for binary in ("java", "javac")),
                    f"{key} java/javac are not executable")
        if str(home) not in homes:
            homes.append(str(home))
    lines = [f"org.gradle.jvmargs={JVM_ARGUMENTS}", "org.gradle.workers.max=2", "org.gradle.parallel=false",
             "org.gradle.caching=false", "org.gradle.configuration-cache=false", "org.gradle.daemon=false",
             "kotlin.compiler.execution.strategy=in-process", "org.gradle.java.installations.auto-download=false"]
    if homes:
        # Java Properties syntax, not shell quoting; Windows uses forward slashes.
        escaped = []
        for home in homes:
            value = home.replace("\\", "/")
            require(not any(char in value for char in ("\0", "\r", "\n", ",")), "Unsupported JDK path character")
            pieces = []
            for char in value:
                if char in " :=#!":
                    pieces.append("\\" + char)
                elif not 0x20 <= ord(char) <= 0x7e:
                    encoded = char.encode("utf-16-be")
                    pieces.extend("\\u" + encoded[index:index + 2].hex() for index in range(0, len(encoded), 2))
                else:
                    pieces.append(char)
            escaped.append("".join(pieces))
        lines += ["org.gradle.java.installations.auto-detect=false",
                  "org.gradle.java.installations.paths=" + ",".join(escaped)]
    return ("\n".join(lines) + "\n").encode("utf-8"), homes


def initialize(args: argparse.Namespace) -> int:
    root = absolute_path(args.root)
    state = absolute_path(args.state, exists=False)
    require(root.is_dir(), "Source root is not a directory")
    require(not within(state, root) and not within(root, state), "Audit state must be outside the checkout")
    require(state.parent.is_dir() and not state.exists(), "Audit state must be a new directory with an existing parent")
    require(args.host == host_role() and args.host in HOSTS, "Requested audit host differs from the actual native host")
    require(re.fullmatch(r"[0-9a-f]{40}", args.expected_commit), "Expected commit must be an exact lowercase SHA")
    source = source_snapshot(root)
    require(source["commit"] == args.expected_commit and source["status"] == "" and
            source["diffSha256"] == digest(b""), "Initialization requires the exact clean expected source")
    policy, java_homes = java_policy()
    preexisting = [str(path) for path in disposable_roots(root) if existing_lstat(path) is not None]
    state.mkdir(mode=0o700)
    home = state / "gradle-home"
    home.mkdir(mode=0o700)
    (state / "evidence").mkdir(mode=0o700)
    (state / "cancellations").mkdir(mode=0o700)
    with new_file(home / "gradle.properties") as stream:
        stream.write(policy)
        stream.flush()
        os.fsync(stream.fileno())
    context = {"schema": 1, "root": str(root), "expectedCommit": args.expected_commit,
               "tree": source["tree"], "source": source, "host": args.host, "gradleHome": str(home),
               "createdUtc": utc(), "id": uuid.uuid4().hex, "gradlePropertiesSha256": digest(policy),
               "javaHomes": java_homes, "preexistingOutputPaths": preexisting}
    write_new_json(state / "context.json", context)
    print(str(state / "context.json"))
    return 0


def context_at(value: str) -> tuple[Path, dict[str, Any]]:
    state = absolute_path(value)
    require(state.is_dir(), "Audit state is not a directory")
    context = read_json(state / "context.json")
    require(type(context.get("schema")) is int and context["schema"] == 1, "Wrong audit context schema")
    require(isinstance(context.get("id"), str) and re.fullmatch(r"[0-9a-f]{32}", context["id"]),
            "Malformed context identity")
    root = absolute_path(context.get("root", ""))
    home = absolute_path(context.get("gradleHome", ""))
    require(home == state / "gradle-home" and not within(state, root) and not within(root, state),
            "Context home/state/root ownership mismatch")
    require(context.get("host") == host_role() and context["host"] in HOSTS, "Wrong actual native audit host")
    expected = context.get("source")
    require(isinstance(expected, dict) and set(expected) == {"commit", "tree", "status", "diffSha256"},
            "Malformed context source binding")
    require(expected.get("commit") == context.get("expectedCommit") and expected.get("tree") == context.get("tree")
            and expected.get("status") == "" and expected.get("diffSha256") == digest(b""),
            "Audit context does not bind clean source")
    require(isinstance(context.get("gradlePropertiesSha256"), str), "Missing bounded-home policy binding")
    reject_symlinks(home / "gradle.properties")
    require(file_digest(home / "gradle.properties", MAX_JSON_BYTES) == context["gradlePropertiesSha256"],
            "Job-owned Gradle resource/toolchain policy changed")
    require(isinstance(context.get("preexistingOutputPaths"), list) and
            all(isinstance(path, str) for path in context["preexistingOutputPaths"]), "Invalid output baseline")
    return state, context


def gradle_arguments(original: list[str]) -> list[str]:
    require(original and all(isinstance(arg, str) and "\0" not in arg for arg in original), "Missing Gradle argv")
    forbidden = {"daemon", "parallel", "build-cache", "configuration-cache", "continuous", "t",
                 "offline", "refresh-keys", "write-verification-metadata", "M", "F", "gradle-user-home", "g",
                 "include-build", "project-cache-dir"}
    allowed_values = {"dependency-verification": "strict", "max-workers": "2", "console": "plain"}
    allowed_properties = {"org.gradle.jvmargs": JVM_ARGUMENTS, "org.gradle.parallel": "false",
                          "org.gradle.workers.max": "2", "org.gradle.caching": "false",
                          "org.gradle.configuration-cache": "false", "org.gradle.daemon": "false",
                          "kotlin.compiler.execution.strategy": "in-process"}
    index = 0
    while index < len(original):
        argument = original[index]
        # Gradle registers names and aliases independently of their one/two-dash
        # spelling. Its parser supports short '=' and long '=' arguments as well
        # as a separate value. Inspect the same property expression in every
        # form, without reconstructing or normalizing the raw argv we execute.
        require(argument != "--", "Inner Gradle option terminator would disable appended audit enforcement")
        require(not argument.startswith(("-system-prop=", "-project-prop=")),
                "Single-dash long '=' property spelling is not a Gradle property expression")
        option, separator, attached = argument.partition("=")
        if option.startswith("--"):
            option = option[2:]
        elif option.startswith("-"):
            option = option[1:]
        else:
            index += 1
            continue
        require(option not in forbidden and not any(argument.startswith(short)
                for short in ("-g", "-M", "-F")), "Conflicting/unsafe Gradle option")
        # Combined short switches with a later property/home/resource switch are
        # deliberately unsupported. Never guess whether a later token is an
        # argument or permit an uninspected option hidden inside such a cluster.
        if option != "status":
            require(not re.match(r"^-[qidsSmhvw?]+[DPgMFt]", argument),
                    "Combined Gradle property/home/resource switches are unsupported")
        if option in allowed_values:
            if separator:
                value = attached
            else:
                index += 1
                require(index < len(original), "Missing Gradle policy option value")
                value = original[index]
            require(value == allowed_values[option], "Conflicting Gradle verification/resource option")
        expression = None
        if option in ("D", "P", "system-prop", "project-prop"):
            if separator:
                expression = attached
            else:
                index += 1
                require(index < len(original), "Missing Gradle property expression")
                expression = original[index]
        elif argument.startswith(("-D", "-P")):
            expression = argument[2:]
        if expression is not None:
            key, has_value, value = expression.partition("=")
            require(key and key == key.strip() and not key.startswith("-"), "Malformed Gradle property key")
            if key in allowed_properties:
                require(has_value and value == allowed_properties[key], "Conflicting Gradle resource property")
            elif key.startswith(("org.gradle.", "kotlin.compiler.", "kotlin.daemon.")) or key in (
                    "gradle.user.home", "java.home", "org.gradle.java.home"):
                raise AuditError("Unapproved Gradle resource/home/toolchain override")
        index += 1
    # Do not add --no-configure-on-demand: an intentional policy rejection uses its
    # opposite. Preserve every original token, especially isolated Maven paths.
    return [*original, *AUDIT_FLAGS]


class LeafLock:
    def __init__(self, state: Path):
        path = state / LOCK_NAME
        reject_symlinks(path)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        self.fd = os.open(path, flags, 0o600)
        require(stat.S_ISREG(os.fstat(self.fd).st_mode), "Gradle lease is not a regular file")
        if os.fstat(self.fd).st_size == 0:
            os.write(self.fd, b"\0")
        self.held = False

    def acquire(self, timeout: float = 0) -> None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.held = True
                return
            except OSError as error:
                if time.monotonic() >= deadline:
                    raise AuditError("Another audit Gradle leaf owns the invocation lease") from error
                time.sleep(0.1)

    def close(self) -> None:
        if self.fd is None:
            return
        try:
            if self.held:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
            self.fd = None
            self.held = False


class Tee:
    def __init__(self, source: Any, destination: Path, live: Any | None, errors: list[str]):
        self.source, self.live, self.errors = source, live, errors
        self.output = new_file(destination)
        self.thread = threading.Thread(target=self._copy, name="audit-byte-tee", daemon=True)
        self.thread.start()

    def _copy(self) -> None:
        file_ok, live_ok = True, self.live is not None
        try:
            while True:
                block = self.source.read(65536)
                if not block:
                    break
                if file_ok:
                    try:
                        self.output.write(block)
                    except OSError as error:
                        self.errors.append(f"Evidence stream write failed: {type(error).__name__}")
                        file_ok = False
                if live_ok:
                    try:
                        self.live.write(block)
                        self.live.flush()
                    except (OSError, ValueError) as error:
                        self.errors.append(f"Product stream delivery failed: {type(error).__name__}")
                        live_ok = False
        except (OSError, ValueError) as error:
            self.errors.append(f"Owned stream read failed: {type(error).__name__}")
        finally:
            try:
                self.source.close()
                self.output.flush()
                os.fsync(self.output.fileno())
                self.output.close()
            except (OSError, ValueError) as error:
                self.errors.append(f"Evidence stream finalization failed: {type(error).__name__}")

    def finish(self) -> None:
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            self.errors.append("Owned pipe did not reach EOF after worker drain")


def regular_report_files(directory: Path, budget: list[int]) -> list[Path]:
    # Deliberately use bounded scandir iteration rather than os.walk's default
    # error suppression. Count directories as well as files, including empty
    # trees. Neither root nor descendant scan errors mean "no reports".
    result = []
    pending = [(directory, 0)]
    while pending:
        parent, depth = pending.pop()
        require(depth <= 256, "Report directory depth exceeds its bound")
        require(physical_directory_present(parent), "Admitted report directory disappeared during inventory")
        budget[0] += 1
        require(budget[0] <= MAX_ARCHIVE_FILES, "Report archive entry count exceeds its bound")
        with os.scandir(parent) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                require(not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400),
                        "Symlink/reparse-point report evidence is not admitted")
                path = Path(entry.path)
                if stat.S_ISDIR(info.st_mode):
                    pending.append((path, depth + 1))
                    # Account for queued directories immediately, not only once
                    # opened, so a very wide tree cannot grow an unbounded queue.
                    require(budget[0] + len(pending) <= MAX_ARCHIVE_FILES,
                            "Report archive entry count exceeds its bound")
                else:
                    budget[0] += 1
                    require(budget[0] + len(pending) <= MAX_ARCHIVE_FILES,
                            "Report archive entry count exceeds its bound")
                    require(stat.S_ISREG(info.st_mode), "Nonregular report evidence")
                    result.append(path)
    return result


def report_candidates(root: Path, state: Path, original: list[str]) -> list[tuple[str, Path]]:
    roots = [(str(path.relative_to(root)), path) for path in output_roots(root)]
    index = 0
    while index < len(original):
        token = original[index]
        option, separator, attached = token.partition("=")
        option = option[2:] if option.startswith("--") else option[1:] if option.startswith("-") else ""
        project = None
        if option in ("D", "P", "system-prop", "project-prop"):
            if not separator:
                index += 1  # A property expression is not another project-dir option.
        elif option in ("p", "project-dir"):
            if separator:
                project = attached
            else:
                index += 1
                require(index < len(original), "Missing Gradle project directory")
                project = original[index]
        elif token.startswith("-p") and not token.startswith("--") and len(token) > 2:
            project = token[2:]
        if project:
            fixture = Path(project)
            if not fixture.is_absolute():
                fixture = root / fixture
            fixture = absolute_path(str(fixture), exists=False)
            require(within(fixture, state) or within(fixture, root),
                    "External Gradle project must be under the admitted owned state for report retention")
            if within(fixture, state) and physical_directory_present(fixture):
                for build in [fixture / "build", *immediate_output_roots(fixture)]:
                    roots.append(("external/" + str(build.relative_to(state)), build))
        index += 1
    result = []
    budget = [0]
    for label, build in roots:
        for name in ("reports", "test-results"):
            directory = build / name
            if not physical_directory_present(directory):
                continue
            for path in regular_report_files(directory, budget):
                relative = Path(label) / name / path.relative_to(directory)
                result.append((relative.as_posix(), path))
    return sorted(result)


def report_snapshot(root: Path, state: Path, original: list[str]) -> dict[str, dict[str, Any]]:
    result, total = {}, 0
    for label, path in report_candidates(root, state, original):
        size = path.stat().st_size
        total += size
        require(total <= MAX_ARCHIVE_BYTES, "Report archive bytes exceed its bound")
        result[label] = {"sha256": file_digest(path), "bytes": size}
    return result


def retain_reports(root: Path, state: Path, original: list[str], before: dict[str, Any],
                   evidence: Path) -> list[dict[str, Any]]:
    after = report_snapshot(root, state, original)
    paths = dict(report_candidates(root, state, original))
    records = []
    for label, item in after.items():
        unchanged = before.get(label) == item
        row = {"source": label, **item, "classification": "preexisting-unchanged" if unchanged else "changed-since-admission"}
        if not unchanged:
            destination = evidence / "reports" / label
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with paths[label].open("rb") as source, new_file(destination) as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
                target.flush()
                os.fsync(target.fileno())
            require(file_digest(destination) == item["sha256"], "Report changed during evidence retention")
            row["retained"] = destination.relative_to(evidence).as_posix()
        records.append(row)
    write_new_json(evidence / "report-manifest.json", {"schema": 1, "records": records,
                   "limitation": "Changed bytes are not proof of test execution; use the unchanged product assessor."})
    return records


def request_cancellation(state: Path, job: str, invocation: str) -> None:
    require(re.fullmatch(r"[0-9a-f]{32}", invocation), "Cancellation needs an exact invocation ID")
    path = state / "cancellations" / f"{invocation}.json"
    if path.exists():
        previous = read_json(path)
        require(previous.get("id") == invocation and previous.get("jobId") == job and previous.get("schema") == 1,
                "Existing cancellation request has the wrong identity")
        return
    try:
        write_new_json(path, {"schema": 1, "id": invocation, "jobId": job, "requestedUtc": utc()})
    except FileExistsError:
        previous = read_json(path)
        require(previous.get("id") == invocation and previous.get("jobId") == job and previous.get("schema") == 1,
                "Racing cancellation request has the wrong identity")


def cancellation_requested(state: Path, context: dict[str, Any], invocation: str, cancelled: list[int]) -> None:
    path = state / "cancellations" / f"{invocation}.json"
    if not path.exists() or 0 in cancelled:
        return
    request = read_json(path)
    require(type(request.get("schema")) is int and request["schema"] == 1 and request.get("id") == invocation and
            request.get("jobId") == context["id"], "Cancellation request identity/schema mismatch")
    cancelled.append(0)  # Cooperative request, not a POSIX or Windows signal.


def cancel_command(args: argparse.Namespace) -> int:
    # Cancellation remains available even if source/home policy has changed. Do not
    # make the repair's fail-closed source check prevent stopping its owned workers.
    state = absolute_path(args.state)
    context = read_json(state / "context.json")
    require(type(context.get("schema")) is int and context["schema"] == 1 and
            isinstance(context.get("id"), str) and re.fullmatch(r"[0-9a-f]{32}", context["id"]),
            "Cancellation state lacks an admitted job identity")
    reject_symlinks(state / "cancellations")
    require((state / "cancellations").is_dir(), "Cancellation directory is missing")
    request_cancellation(state, context["id"], args.id)
    return 0


def cancel_nested_leaves(state: Path, context: dict[str, Any], invocation: str,
                         scope: Any, errors: list[str]) -> None:
    pending: list[tuple[Path, int]] = []
    for entry in (state / "evidence").iterdir():
        if not re.fullmatch(r"[0-9a-f]{32}", entry.name) or not entry.is_dir() or \
                not (entry / "start.json").is_file() or (entry / "receipt.json").exists():
            continue
        start = read_json(entry / "start.json")
        if start.get("jobId") == context["id"] and start.get("id") == entry.name and \
                invocation in start.get("ancestorInvocationIds", []) and type(start.get("controllerPid")) is int:
            request_cancellation(state, context["id"], entry.name)
            pending.append((entry / "receipt.json", start["controllerPid"]))
    # Give actual nested adapters a chance to complete their own finally/--stop
    # before OS-level drain. Numeric PIDs here only describe liveness already
    # established by scope identities; they are never used to send a signal.
    deadline = time.monotonic() + 150
    while pending and time.monotonic() < deadline:
        live_pids = {identity["pid"] for identity in scope.discover()}
        pending = [(path, pid) for path, pid in pending if not path.exists() and pid in live_pids]
        if pending:
            time.sleep(.1)
    if pending:
        errors.append("Nested adapter did not finalize within cooperative cancellation grace")


def wait_process(scope: Any, child: Any, timeout: float, cancelled: list[int], check_cancel: Any,
                 *, stop: bool = False) -> int:
    deadline = time.monotonic() + timeout
    while True:
        code = child.poll()
        scope.discover()
        check_cancel()
        if code is not None:
            return code
        if cancelled and not stop:
            raise AuditError("Invocation cancellation requested")
        require(time.monotonic() < deadline, "Wrapper stop timed out" if stop else "Product command timed out")
        time.sleep(0.1)


def finalize_receipts(receipt: dict[str, Any], evidence: Path, optional: Any,
                      optional_path: Path | None, lock: LeafLock | None) -> None:
    targets = []
    if optional is not None:
        targets.append((optional_path, optional, os.fstat(optional.fileno())))

    def failed(label: str, error: Exception) -> None:
        receipt["finalExitCode"] = INFRASTRUCTURE_EXIT
        receipt["errors"].append(f"{label}: {type(error).__name__}: {error}")

    def publish() -> bool:
        success = True
        for _path, stream, _identity in targets:
            try:
                stream.seek(0)
                stream.write(json_bytes(receipt))
                stream.truncate()
                stream.flush()
                os.fsync(stream.fileno())
            except Exception as error:
                failed("Receipt write/fsync failed", error)
                success = False
        return success

    try:
        path = evidence / "receipt.json"
        stream = new_file(path)
        targets.append((path, stream, os.fstat(stream.fileno())))
    except Exception as error:
        failed("Canonical receipt creation failed", error)
    if not publish():
        publish()  # Best-effort invalidate another output written before the failure.
    if lock is not None:
        try:
            lock.close()  # Receipt bytes/fsync completed while the leaf lease was held.
        except Exception as error:
            failed("Gradle lease release failed", error)
            publish()
    close_failed = False
    for _path, stream, _identity in targets:
        try:
            stream.close()
        except Exception as error:
            failed("Receipt handle close failed", error)
            close_failed = True
    if close_failed:
        # Only reopen the very same newly-created inode, never an existing caller
        # file or a path replaced during execution. The process exit125 remains
        # authoritative if damaged storage makes even this invalidation impossible.
        for path, _stream, identity in targets:
            descriptor = None
            try:
                reject_symlinks(path)
                descriptor = os.open(path, os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0))
                observed = os.fstat(descriptor)
                require((observed.st_dev, observed.st_ino) == (identity.st_dev, identity.st_ino),
                        "Receipt path was replaced; preserve the replacement")
                with os.fdopen(descriptor, "wb") as target:
                    descriptor = None
                    target.write(json_bytes(receipt))
                    target.truncate()
                    target.flush()
                    os.fsync(target.fileno())
            except Exception as error:
                failed("Receipt invalidation failed", error)
            finally:
                if descriptor is not None:
                    os.close(descriptor)


def execute(args: argparse.Namespace) -> int:
    require(os.environ.get(STATE_ENV), f"{STATE_ENV} is required")
    state, context = context_at(os.environ[STATE_ENV])
    root = absolute_path(args.cwd)
    wrapper = absolute_path(args.wrapper)
    invocation = args.id or uuid.uuid4().hex
    require(re.fullmatch(r"[0-9a-f]{32}", invocation), "Invocation ID must be an exact lowercase UUID hex value")
    evidence = state / "evidence" / invocation
    evidence.mkdir(mode=0o700)
    require(isinstance(args.purpose, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", args.purpose),
            "Purpose must be a short nonsecret stable label")
    original = list(args.argv)
    if original[:1] == ["--"]:
        original = original[1:]
    receipt: dict[str, Any] = {"schema": 1, "id": invocation, "purpose": args.purpose, "kind": args.kind,
        "requestedArgv": original, "cwd": str(root), "wrapper": str(wrapper), "host": host_role(),
        "jobId": context["id"], "gradleHome": context["gradleHome"], "startedUtc": utc(),
        "ancestorInvocationIds": os.environ.get(CHAIN_ENV, "").split(":") if os.environ.get(CHAIN_ENV) else [],
        "controllerPid": os.getpid(),
        "sourceBefore": None, "sourceAfter": None, "productExitCode": None, "stopExitCode": None,
        "finalExitCode": INFRASTRUCTURE_EXIT, "sourceUnchanged": False, "ownedSurvivors": [], "errors": [],
        "evidenceDirectory": str(evidence)}
    errors: list[str] = receipt["errors"]
    scope, lock, optional, child, stop_child = None, None, None, None, None
    optional_path = None
    streams: list[Tee] = []
    cancelled: list[int] = []
    handlers: dict[int, Any] = {}
    started = False
    baseline: dict[str, Any] = {}
    report_arguments = original if args.kind == "gradle" else []
    context_hash = digest((state / "context.json").read_bytes())
    monotonic_start = time.monotonic()
    check_cancel = lambda: cancellation_requested(state, context, invocation, cancelled)
    write_new_json(evidence / "start.json", receipt)
    try:
        if args.receipt:
            optional_path = absolute_path(args.receipt, exists=False)
            require(not within(optional_path, root), "Optional receipt must be outside the checkout")
            optional = new_file(optional_path)
        require(root == Path(context["root"]), "Command cwd differs from the admitted root")
        expected_wrapper = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
        require(wrapper == expected_wrapper and wrapper.is_file(), "Use the applicable checked-in root wrapper")
        require(original, "Command argv must not be empty")
        require(0.1 <= args.timeout <= 24 * 60 * 60 and 0.1 <= args.stop_timeout <= 300,
                "Invalid bounded command/stop timeout")
        actual = gradle_arguments(original) if args.kind == "gradle" else original
        env = ownership_environment(dict(os.environ), context["id"], invocation, str(state), context["gradleHome"])
        # Environment JVM arguments can affect even the wrapper stop and unchanged
        # platform driver; don't silently shadow a caller's competing resource flags.
        for variable in ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
            require(not env.get(variable, "").strip(), f"Inherited {variable} conflicts with owned resource policy")
        if args.kind == "gradle":
            lock = LeafLock(state)
            lock.acquire()
        receipt["sourceBefore"] = source_snapshot(root)
        require(receipt["sourceBefore"] == context["source"], "Source differs from the exact clean admitted revision")
        baseline = report_snapshot(root, state, report_arguments)
        scope = make_scope(context["id"], invocation, str(state), context["gradleHome"])
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda signum, _frame: cancelled.append(signum))
        check_cancel()
        require(not cancelled, "Invocation cancelled before product launch")
        command = [str(wrapper), *actual] if args.kind == "gradle" else actual
        receipt["executedArgv"] = command
        receipt["executedArgvSemantics"] = "logical-command; exact platform launch is ownership.launches[productLaunchIndex]"
        receipt["productLaunchIndex"] = len(scope.launches)
        receipt["productStartedUtc"] = utc()
        started = True  # A partially failed launch still needs same-home stop.
        child = scope.spawn(command, str(root), env)
        receipt["productPid"] = child.pid
        streams += [Tee(child.stdout, evidence / "product.stdout.log", sys.stdout.buffer, errors),
                    Tee(child.stderr, evidence / "product.stderr.log", sys.stderr.buffer, errors)]
        receipt["productExitCode"] = wait_process(scope, child, args.timeout, cancelled, check_cancel)
    except Exception as error:
        errors.append(f"{type(error).__name__}: {error}")
    finally:
        receipt["productEndedUtc"] = utc()
        # Outer commands must release/drain their own nested leaves before acquiring
        # the leaf lease for their final stop. A cancelled leaf drains before stop too.
        if scope is not None and (args.kind == "command" or errors or cancelled):
            try:
                if args.kind == "command":
                    cancel_nested_leaves(state, context, invocation, scope, errors)
                receipt["ownedSurvivors"] = scope.drain()
                if receipt["ownedSurvivors"]:
                    errors.append("Owned product workers survived pre-stop drain")
            except Exception as error:
                errors.append(f"Pre-stop ownership drain failed: {error}")
                receipt["ownedSurvivors"] = [{"status": "UNKNOWN", "reason": "pre-stop drain failed"}]
        if started and scope is not None:
            try:
                if lock is None:
                    lock = LeafLock(state)
                    lock.acquire(timeout=15)
                require(lock.held, "Cannot stop without owning the Gradle leaf lease")
                # Never use the product argv to choose another home or wrapper.
                stop_argv = [str(wrapper), "--stop", "--console=plain", "--no-parallel", "--max-workers=2",
                             f"-Dorg.gradle.jvmargs={JVM_ARGUMENTS}"]
                receipt["stopArgv"] = stop_argv
                receipt["stopLaunchIndex"] = len(scope.launches)
                receipt["stopStartedUtc"] = utc()
                stop_child = scope.spawn(stop_argv, str(root), env)
                streams += [Tee(stop_child.stdout, evidence / "stop.stdout.log", None, errors),
                            Tee(stop_child.stderr, evidence / "stop.stderr.log", None, errors)]
                receipt["stopExitCode"] = wait_process(scope, stop_child, args.stop_timeout, cancelled, check_cancel, stop=True)
                if receipt["stopExitCode"] != 0:
                    errors.append("Applicable same-home Gradle wrapper --stop failed")
            except Exception as error:
                errors.append(f"Wrapper stop/finalizer failed: {error}")
            receipt["stopEndedUtc"] = utc()
        if scope is not None:
            try:
                receipt["ownedSurvivors"] = scope.drain()
                if receipt["ownedSurvivors"]:
                    errors.append("Owned workers survived final drain")
            except Exception as error:
                errors.append(f"Final ownership drain failed: {error}")
                receipt["ownedSurvivors"] = [{"status": "UNKNOWN", "reason": "final drain failed"}]
            try:
                receipt["ownership"] = scope.description()
                errors.extend(receipt["ownership"].get("discoveryErrors", []))
            except Exception as error:
                errors.append(f"Ownership trace retention failed: {error}")
            if child is not None:
                try:
                    receipt["productExitCode"] = child.poll()
                except Exception as error:
                    errors.append(f"Product exit observation failed: {error}")
            if stop_child is not None and receipt["stopExitCode"] is None:
                try:
                    receipt["stopExitCode"] = stop_child.poll()
                except Exception as error:
                    errors.append(f"Stop exit observation failed: {error}")
        for stream in streams:
            stream.finish()
        try:
            receipt["sourceAfter"] = source_snapshot(root)
            receipt["sourceUnchanged"] = receipt["sourceBefore"] == receipt["sourceAfter"] == context["source"]
            if not receipt["sourceUnchanged"]:
                errors.append("Exact admitted source changed or could not be admitted")
            require(digest((state / "context.json").read_bytes()) == context_hash, "Audit context changed during invocation")
            require(file_digest(Path(context["gradleHome"]) / "gradle.properties", MAX_JSON_BYTES) ==
                    context["gradlePropertiesSha256"], "Bounded Gradle-home policy changed during invocation")
            if started:
                receipt["reports"] = retain_reports(root, state, report_arguments, baseline, evidence)
        except Exception as error:
            errors.append(f"Source/evidence finalization failed: {error}")
        if scope is not None:
            try:
                scope.close()
            except Exception as error:
                errors.append(f"Owned handle close failed: {error}")
        try:
            check_cancel()
        except Exception as error:
            errors.append(f"Cancellation finalization failed: {type(error).__name__}: {error}")
        if cancelled:
            receipt["cancelledSignals"] = [number for number in cancelled if number != 0]
            receipt["cancelRequested"] = 0 in cancelled
            errors.append("Invocation cancellation cannot be a successful product result")
        receipt["endedUtc"] = utc()
        receipt["durationSeconds"] = round(time.monotonic() - monotonic_start, 3)
        if not errors and receipt["productExitCode"] is not None and receipt["stopExitCode"] == 0:
            product_code = receipt["productExitCode"]
            receipt["finalExitCode"] = product_code if 0 <= product_code <= 255 else INFRASTRUCTURE_EXIT
            if receipt["finalExitCode"] == INFRASTRUCTURE_EXIT:
                errors.append("Product exit is reserved/unsupported as an expected-red audit result")
        finalize_receipts(receipt, evidence, optional, optional_path, lock)
        for number, handler in handlers.items():
            signal.signal(number, handler)
    if receipt["errors"]:
        print(f"audit executor infrastructure failure; receipt {evidence / 'receipt.json'}", file=sys.stderr)
    return receipt["finalExitCode"]


def inspect_disposable_tree(path: Path) -> dict[str, Any]:
    """Inventory owned entries without entering descendant links or junctions.

    A generated runtime/framework may legitimately link outside this output tree.
    Record only the link's lexical-target digest/length, never read target bytes.
    The root/ancestors remain non-links. Unknown reparse types and special files
    fail closed. This is quiescent owned-output cleanup, not containment of a
    malicious concurrent actor changing filesystem names or mount topology.
    """
    require(sys.version_info >= (3, 8), "Cleanup requires junction-safe Python rmtree semantics")
    require(os.name == "nt" or shutil.rmtree.avoids_symlink_attacks,
            "POSIX cleanup requires fd-based no-follow rmtree")
    reject_symlinks(path)
    root_info = path.lstat()
    root_device = root_info.st_dev
    pending = [(path, 0)]
    count, metadata_bytes = 0, 0
    links = []
    while pending:
        directory, depth = pending.pop()
        require(depth <= 256, "Disposable output tree exceeds its directory-depth bound")
        reject_symlinks(directory)
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1
                require(count <= MAX_CLEANUP_ENTRIES, "Disposable output entry count exceeds its bound")
                info = entry.stat(follow_symlinks=False)
                reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
                tag = getattr(info, "st_reparse_tag", None) if reparse else None
                link_kind = None
                if reparse:
                    require(os.name == "nt" and tag in (0xA0000003, 0xA000000C),
                            "Unknown descendant reparse type blocks cleanup")
                    link_kind = "junction" if tag == 0xA0000003 else "symlink"
                elif stat.S_ISLNK(info.st_mode):
                    link_kind = "symlink"
                if link_kind:
                    target = os.fsencode(os.readlink(entry.path))
                    require(len(target) <= 65536, "Disposable link target exceeds its metadata bound")
                    record = {"path": Path(entry.path).relative_to(path).as_posix(), "kind": link_kind,
                              "reparseTag": tag, "targetSha256": digest(target), "targetBytes": len(target),
                              "policy": "unlink-entry-only; do-not-traverse-target"}
                    metadata_bytes += len(json_bytes(record))
                    require(metadata_bytes <= MAX_JSON_BYTES // 2, "Disposable link evidence exceeds its bound")
                    links.append(record)
                elif stat.S_ISDIR(info.st_mode):
                    # Windows DirEntry caches have st_dev=0. Keep their initial
                    # reparse classification above, but compare full path stats.
                    child = Path(entry.path)
                    physical = child.lstat()
                    require(stat.S_ISDIR(physical.st_mode) and
                            not (getattr(physical, "st_file_attributes", 0) & 0x400),
                            "Descendant changed from a physical directory before cleanup")
                    require(physical.st_dev == root_device, "Cross-device descendant directory blocks cleanup")
                    pending.append((child, depth + 1))
                else:
                    require(stat.S_ISREG(info.st_mode), "Unexpected special file blocks disposable-output cleanup")
    return {"path": str(path), "rootIdentity": {"device": root_info.st_dev, "inode": root_info.st_ino},
            "entryCount": count, "links": sorted(links, key=lambda item: item["path"]),
            "noTargetTraversal": True, "removal": "shutil.rmtree; child symlinks/junctions are unlinked"}


def removal_failure_detail(root: Path, operation: Any, entry: Any, error: BaseException) -> dict[str, Any]:
    """Bounded post-failure metadata, never a retry or an inspection of a link target."""
    observation = {"observedUtc": utc(), "status": "UNAVAILABLE"}
    detail = {"failedRoot": str(root) if len(str(root)) <= 1024 else "UNAVAILABLE",
              "operation": "UNAVAILABLE",
              "relativePath": "UNAVAILABLE", "exceptionType": type(error).__name__[:128],
              "errno": None, "winerror": None,
              "metadataObservation": observation}

    def number(value, minimum=-(2 ** 31)):
        return value if type(value) is int and minimum <= value < 2 ** 32 else None

    try:
        name = getattr(operation, "__name__", None)
        if name in ("unlink", "rmdir", "open", "scandir", "lstat", "listdir", "close"):
            detail["operation"] = name
        detail["errno"] = number(getattr(error, "errno", None))
        detail["winerror"] = number(getattr(error, "winerror", None))
        if entry is None:
            return detail
        require(len(os.fspath(entry)) <= 32768, "Failure path exceeds diagnostic bound")
        path = Path(entry)  # Lexical admission only: never resolve a failed filename.
        require(path.is_absolute() and ".." not in path.parts and within(path, root), "Outside failed output root")
        relative = path.relative_to(root).as_posix()
        require(len(relative) <= 1024 and len(path.parts) <= 512, "Failure path exceeds diagnostic bound")
        detail["relativePath"] = relative
        # Check from the filesystem root toward the parent before lstat of the
        # leaf: even lstat follows links in intermediate path components.
        for parent in reversed(path.parents):
            info = parent.lstat()
            require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
                    not (getattr(info, "st_file_attributes", 0) & 0x400), "Nonphysical failure ancestor")
        info = path.lstat()
        mode = number(info.st_mode, minimum=0)
        require(mode is not None, "Invalid failure metadata mode")
        attributes = number(getattr(info, "st_file_attributes", None), minimum=0)
        tag = number(getattr(info, "st_reparse_tag", None), minimum=0)
        observation.update({"status": "OBSERVED", "mode": mode,
                            "type": "symlink" if stat.S_ISLNK(mode) else
                                "directory" if stat.S_ISDIR(mode) else "file" if stat.S_ISREG(mode) else "other",
                            "fileAttributes": attributes, "reparseTag": tag,
                            "readOnly": bool(attributes & 1) if attributes is not None else None})
    except FileNotFoundError:
        observation["status"] = "ABSENT"
    except (AuditError, TypeError, ValueError):
        observation["status"] = "REFUSED"
    except Exception:
        observation["status"] = "UNAVAILABLE"
    return detail


def retry_windows_readonly_unlink(root: Path, root_identity: dict[str, int], operation: Any, entry: Any,
                                  error: BaseException, attempt: dict[str, Any], persist: Any) -> bool:
    """One leaf retry under the existing quiescent, already-finalized output contract.

    Windows chmod changes only READONLY, not ACLs. Python 3.12 cannot chmod a
    Windows fd/no-follow path; physical ancestor and same-file checks below retain
    rmtree's explicit non-hostile-name-mutation limitation. Never chmod a link,
    directory, hardlink, unknown attribute class or unverified output root.
    """
    if (sys.platform != "win32" or operation is not os.unlink or not isinstance(error, PermissionError) or
            error.errno != errno.EACCES or getattr(error, "winerror", None) != 5):
        return False
    attempt["stage"] = "admission"
    path = Path(entry)
    require(path.is_absolute() and ".." not in path.parts and path != root and within(path, root),
            "Readonly retry requires a strict lexical child of the admitted output")
    relative = path.relative_to(root).as_posix()
    require(len(str(path)) <= 32768 and len(relative) <= 1024 and len(path.parts) <= 512 and ":" not in relative,
            "Readonly retry path is oversized or not an ordinary leaf name")
    require(root_identity["inode"] > 0, "Readonly retry requires a known preflight root identity")

    def observe():
        # Even lstat follows intermediate links: inspect from the filesystem root
        # before approaching the leaf. Descendants must stay on the preflight disk.
        for parent in reversed(path.parents):
            info = parent.lstat()
            require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
                    not (getattr(info, "st_file_attributes", 0) & 0x400), "Readonly retry has a nonphysical ancestor")
            if parent == root:
                require((info.st_dev, info.st_ino) == (root_identity["device"], root_identity["inode"]),
                        "Readonly retry output root changed after preflight")
            if within(parent, root):
                require(info.st_dev == root_identity["device"], "Readonly retry ancestor changed device")
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400) and
                getattr(info, "st_reparse_tag", 0) == 0, "Readonly retry leaf is not an ordinary non-reparse file")
        require(info.st_dev == root_identity["device"] and info.st_ino > 0 and info.st_nlink == 1,
                "Readonly retry leaf is foreign, unidentified or hardlinked")
        return info

    before = observe()
    attributes = getattr(before, "st_file_attributes", None)
    require(attributes in (0x1, 0x21), "Readonly retry requires only READONLY and optional ARCHIVE attributes")
    identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_nlink)
    attempt.update({"relativePath": relative, "leafIdentity": {"device": before.st_dev, "inode": before.st_ino,
                    "links": before.st_nlink, "bytes": before.st_size, "mtimeNs": before.st_mtime_ns},
                    "attributesBefore": attributes, "outcome": "PENDING", "stage": "retain-original-failure"})
    persist()  # Durably retain the original unlink error before any attribute change.
    current = observe()
    require((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_nlink) == identity and
            current.st_file_attributes == attributes, "Readonly retry leaf changed before chmod")
    attempt["stage"] = "clear-readonly"
    os.chmod(path, stat.S_IWRITE)  # Windows only: clear exactly FILE_ATTRIBUTE_READONLY.
    attempt["stage"] = "revalidate-before-unlink"
    current = observe()
    # NORMAL is the Windows marker for no remaining attributes, not another permission.
    allowed_after = (0, 0x80) if attributes == 0x1 else (0x20,)
    require((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_nlink) == identity and
            current.st_file_attributes in allowed_after, "Readonly retry leaf changed beyond its readonly bit")
    attempt["attributesAfter"] = current.st_file_attributes
    attempt["stage"] = "unlink-once"
    os.unlink(path)
    require(existing_lstat(path) is None, "Readonly retry did not remove its exact leaf")
    attempt.update({"stage": "finished", "outcome": "REMOVED"})
    return True


def cleanup(args: argparse.Namespace) -> int:
    state, context = context_at(args.state)
    root = Path(context["root"])
    lock = LeafLock(state)
    try:
        lock.acquire()
        current = source_snapshot(root)
        require(current["commit"] == context["expectedCommit"] and current["tree"] == context["tree"],
                "Do not clean outputs after switching the admitted source revision")
        for entry in (state / "evidence").iterdir():
            if entry.is_dir() and (entry / "start.json").exists():
                require((entry / "receipt.json").is_file(), "Unfinalized invocation blocks disposable-output cleanup")
                receipt = read_json(entry / "receipt.json")
                require(receipt.get("ownedSurvivors") == [] and receipt.get("errors") == [],
                        "Unresolved workers/infrastructure evidence block cleanup")
        allowed = set(disposable_roots(root)) - {Path(path) for path in context["preexistingOutputPaths"]}
        allowed.update(state / child for child in ("consumer", "fixtures", "xcode-deriveddata"))
        targets = []
        inspections = []
        for value in args.path:
            path = absolute_path(value)
            require(path in allowed, "Cleanup path is not an exact newly-owned disposable output root")
            require(path.is_dir(), "Cleanup target must be a disposable directory")
            if within(path, root):
                tracked = git(root, "ls-files", "-z", "--", path.relative_to(root).as_posix())
                require(not tracked, "Cleanup target contains tracked source")
            require(path not in targets, "Duplicate cleanup target")
            inspections.append(inspect_disposable_tree(path))
            targets.append(path)
        record = {"schema": 1, "id": uuid.uuid4().hex, "jobId": context["id"], "startedUtc": utc(),
                  "paths": [str(path) for path in targets], "inspections": inspections, "removed": [], "errors": []}
        require(len(json_bytes({**record, "removed": record["paths"]})) + MAX_REMOVAL_DETAIL_BYTES + 1024 <=
                MAX_JSON_BYTES, "Combined cleanup evidence exceeds its bound")
        # Retain no-follow provenance before deletion, not just after successful
        # removal. The final record separately reports partial failures.
        write_new_json(state / "evidence" / f"cleanup-{record['id']}-start.json", record)
        readonly_retried = set()
        for index, path in enumerate(targets):
            detail = None

            def failed(operation, entry, exception):
                nonlocal detail
                recovered, retained = False, False
                attempt = {}
                try:
                    detail = removal_failure_detail(path, operation, entry, exception[1])
                    attempt = {"originalFailure": {**detail, "failedRootIndex": index}, "outcome": "REFUSED"}

                    def retain_attempt():
                        nonlocal retained
                        rows = record.get("readonlyRecoveries", [])
                        candidate = record if retained else {**record, "readonlyRecoveries": [*rows, attempt]}
                        require(len(json_bytes(candidate)) + MAX_REMOVAL_DETAIL_BYTES + 1024 <= MAX_JSON_BYTES,
                                "Readonly retry evidence exceeds the cleanup bound")
                        if not retained:
                            record.setdefault("readonlyRecoveries", []).append(attempt)
                            retained = True

                    def before_change():
                        leaf = Path(entry)
                        require(leaf not in readonly_retried, "A readonly leaf cannot be retried twice")
                        readonly_retried.add(leaf)
                        retain_attempt()
                        write_new_json(state / "evidence" / f"cleanup-{record['id']}-readonly-{len(readonly_retried)}-start.json",
                                       {"cleanupId": record["id"], "jobId": context["id"], "recovery": attempt})

                    try:
                        recovered = retry_windows_readonly_unlink(path, inspections[index]["rootIdentity"],
                                                                  operation, entry, exception[1], attempt, before_change)
                    except Exception as retry_error:
                        attempt["outcome"] = "FAILED" if retained else "REFUSED"
                        attempt["failureType"] = type(retry_error).__name__[:128]
                        if isinstance(retry_error, AuditError):
                            attempt["reason"] = str(retry_error)[:256]
                        for field in ("errno", "winerror"):
                            value = getattr(retry_error, field, None)
                            attempt[field] = value if type(value) is int and -(2 ** 31) <= value < 2 ** 32 else None
                    if "stage" in attempt:
                        attempt["endedUtc"] = utc()
                        retain_attempt()
                except Exception:
                    recovered = False  # Evidence failure never licenses successful removal.
                finally:
                    if not recovered:
                        # Keep the first unlink/removal exception authoritative even
                        # when admission, chmod, revalidation, retry or diagnostics fail.
                        raise exception[1].with_traceback(exception[2])

            try:
                reject_symlinks(path)
                shutil.rmtree(path, onerror=failed)
                record["removed"].append(str(path))
            except (OSError, AuditError) as error:
                record["errors"].append(f"Removal failed: {type(error).__name__}")
                try:
                    if detail is None:
                        detail = removal_failure_detail(path, None, None, error)
                    detail["failedRootIndex"] = index  # Exact root remains in paths if its display is too long.
                    require(len(json_bytes(detail)) <= MAX_REMOVAL_DETAIL_BYTES, "Removal diagnostic exceeds its bound")
                except Exception:
                    # Diagnostic/encoding failures must not erase the original removal failure.
                    detail = {"failedRootIndex": index, "failedRoot": "UNAVAILABLE", "operation": "UNAVAILABLE",
                              "relativePath": "UNAVAILABLE", "exceptionType": type(error).__name__[:128],
                              "errno": None, "winerror": None,
                              "metadataObservation": {"observedUtc": None, "status": "UNAVAILABLE"}}
                record["failureDetail"] = detail
                break
        record["endedUtc"] = utc()
        require(len(json_bytes(record)) <= MAX_JSON_BYTES, "Final cleanup evidence exceeds its bound")
        write_new_json(state / "evidence" / f"cleanup-{record['id']}.json", record)
        return INFRASTRUCTURE_EXIT if record["errors"] else 0
    finally:
        lock.close()


def parser() -> AuditParser:
    result = AuditParser(description=__doc__)
    subparsers = result.add_subparsers(dest="operation")
    init = subparsers.add_parser("init")
    init.add_argument("--root", required=True)
    init.add_argument("--state", required=True)
    init.add_argument("--expected-commit", required=True)
    init.add_argument("--host", choices=HOSTS, required=True)
    clean = subparsers.add_parser("cleanup")
    clean.add_argument("--state", required=True)
    clean.add_argument("--path", required=True, action="append")
    cancel = subparsers.add_parser("request-cancel")
    cancel.add_argument("--state", required=True)
    cancel.add_argument("--id", required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments[:1] in (["init"], ["cleanup"], ["request-cancel"]):
            args = parser().parse_args(arguments)
            return {"init": initialize, "cleanup": cleanup, "request-cancel": cancel_command}[args.operation](args)
        runtime = AuditParser(description=__doc__)
        runtime.add_argument("--cwd", required=True)
        runtime.add_argument("--wrapper", required=True)
        runtime.add_argument("--purpose", required=True)
        runtime.add_argument("--kind", choices=("gradle", "command"), default="gradle")
        runtime.add_argument("--receipt")
        runtime.add_argument("--id")
        runtime.add_argument("--timeout", type=float, default=7200)
        runtime.add_argument("--stop-timeout", type=float, default=120)
        runtime.add_argument("argv", nargs=argparse.REMAINDER)
        return execute(runtime.parse_args(arguments))
    except (Exception, KeyboardInterrupt) as error:
        print(f"audit executor admission failed: {type(error).__name__}: {error}", file=sys.stderr)
        return INFRASTRUCTURE_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
