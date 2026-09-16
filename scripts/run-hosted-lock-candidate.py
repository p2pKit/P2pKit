#!/usr/bin/env python3
"""One explicitly reviewed, mutable full dependency writer on genuine hosted macOS.

Not an immutable audit leaf, publisher, cache importer, or product acceptance assessor.
All child output is private; the separate always-run seal step exports ciphertext only.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import audit_processes as processes
import hosted_evidence
import hosted_lock_resources as resources

MIB, GIB = 1024 ** 2, 1024 ** 3
OPERATION = "dependency-lock-candidate"
INTEL_OPERATION = "dependency-lock-candidate-x64"
WORKFLOW = "p2pKit/P2pKit/.github/workflows/desktop-cross-host.yml@"
XCODE = "/Applications/Xcode_26.5.app/Contents/Developer"
PROFILES = {
    OPERATION: {"runnerArch": "ARM64", "hostRole": "macos-arm64", "osMajor": "26", "javaArch": "aarch64|arm64",
                "xcode": XCODE, "xcodeVersion": "Xcode 26.5\nBuild version 17F42\n",
                "runtime": "com.apple.CoreSimulator.SimRuntime.iOS-26-5", "runtimeVersion": "26.5"},
    INTEL_OPERATION: {"runnerArch": "X64", "hostRole": "macos-x64", "osMajor": "15", "javaArch": "amd64|x86_64",
                      "xcode": "/Applications/Xcode_26.3.app/Contents/Developer",
                      "xcodeVersion": "Xcode 26.3\nBuild version 17C529\n",
                      "runtime": "com.apple.CoreSimulator.SimRuntime.iOS-26-2", "runtimeVersion": "26.2"},
}
WRITER_SECONDS, STOP_SECONDS = 7200, 120
INIT = "gradle/hosted-lock-candidate.init.gradle"
CUSTODY = "scripts/test-transcript-custody.py"
IDENTITY_ENV = (
    "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_REF", "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA",
    "GITHUB_WORKSPACE", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_ENVIRONMENT", "ImageOS", "ImageVersion",
)
INPUTS = {"operation": "P2PKIT_OPERATION", "expected_sha": "P2PKIT_EXPECTED_SHA",
          "expected_tree": "P2PKIT_EXPECTED_TREE", "reviewed_base": "P2PKIT_REVIEWED_BASE",
          "evidence_public_key": "P2PKIT_EVIDENCE_PUBLIC_KEY", "evidence_fingerprint": "P2PKIT_EVIDENCE_FINGERPRINT"}


def require(value, message):
    if not value:
        raise ValueError(message)


def native_profile(operation):
    require(operation in PROFILES, "unknown hosted native profile")
    return PROFILES[operation]


def physical(path, *, directory=False):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "absolute physical path required")
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            require(not stat.S_ISLNK(part.lstat().st_mode), "symlink is not an owned path")
    if directory:
        info = path.stat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid(), "directory not owned")
    return path


def digest(path):
    value = hashlib.sha256()
    with physical(path).open("rb") as stream:
        for block in iter(lambda: stream.read(MIB), b""):
            value.update(block)
    return value.hexdigest()


def read(path, limit=16 * MIB):
    path = physical(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
            "input is not a bounded single-link regular file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(os.path.samestat(before, after) and os.path.samestat(before, path.lstat()) and
            len(raw) == before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns,
            "input changed while reading")
    return raw


def parse(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def write(path, raw):
    path = physical(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def record(path, value):
    write(path, (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())


def identity(path):
    value = physical(path, directory=True).stat()
    return {"device": value.st_dev, "inode": value.st_ino}


def dispatch(env, root):
    operation = env.get("P2PKIT_OPERATION")
    profile = native_profile(operation)
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit" and
            env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            env.get("RUNNER_OS") == "macOS" and env.get("RUNNER_ARCH") == profile["runnerArch"] and
            env.get("GITHUB_SERVER_URL") == "https://github.com" and env.get("GITHUB_API_URL") == "https://api.github.com",
            "genuine hosted dispatch matching the selected native profile required")
    require(env.get("GITHUB_JOB") == OPERATION, "wrong isolated operation/job")
    for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(re.fullmatch(r"[1-9][0-9]{0,19}", env.get(name, "")), "invalid run identity")
    sha, tree = env.get("P2PKIT_EXPECTED_SHA", ""), env.get("P2PKIT_EXPECTED_TREE", "")
    require(re.fullmatch(r"[0-9a-f]{40}", sha) and re.fullmatch(r"[0-9a-f]{40}", tree), "full source SHA/tree required")
    require(env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA") == sha and
            env.get("P2PKIT_REVIEWED_BASE") == sha, "writer base must be this exact independently reviewed revision")
    ref = env.get("GITHUB_REF", "")
    require(ref.startswith("refs/heads/") and len(ref) <= 256 and not any(c in ref for c in "\r\n\x00") and
            ref != "refs/heads/audit/complete-2026-09-04" and
            env.get("GITHUB_WORKFLOW_REF") == WORKFLOW + ref, "workflow/ref identity mismatch")
    require(Path(env["GITHUB_WORKSPACE"]).resolve(strict=True) == root, "checkout root mismatch")
    event = parse(read(Path(env["GITHUB_EVENT_PATH"]).resolve(strict=True), MIB))
    expected = {key: env.get(name, "") for key, name in INPUTS.items()}
    require(event.get("inputs") == expected and event.get("ref") in (ref, ref.removeprefix("refs/heads/")) and
            event.get("repository", {}).get("full_name") == "p2pKit/P2pKit", "original dispatch inputs differ")
    key = expected["evidence_public_key"]
    require(isinstance(key, str) and 0 < len(key.encode("ascii")) <= 65536 and
            "-----BEGIN PGP PUBLIC KEY BLOCK-----" in key and "PRIVATE KEY" not in key, "public evidence recipient required")
    require(re.fullmatch(r"[0-9A-F]{40}", expected["evidence_fingerprint"]), "full recipient fingerprint required")
    return {"commit": sha, "tree": tree, "base": sha, "ref": ref, "operation": operation,
            "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"],
            "recipientFingerprint": expected["evidence_fingerprint"]}


def credential_free_environment(base, state, root):
    """New child-only non-inheritance boundary; does NOT amend the no-child collector.

    Parent hooks/agents are untouched. HOME remains the ordinary runner's home for
    CoreSimulator. This is NOT a sandbox against hostile same-user source code.
    """
    blocked = {"JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
               "GRADLE_HOME", "GRADLE_USER_HOME", "KONAN_DATA_DIR", "KONAN_HOME", "KOTLIN_HOME",
               "KOTLIN_OPTS", "KONAN_OPTS", "KONAN_JVM_ARGS", "KOTLIN_NATIVE_HOME", "ANDROID_USER_HOME",
               "P2PKIT_GRADLE_EXECUTOR", "P2PKIT_ROOT_OVERRIDE", "GNUPGHOME", "SDKROOT", "TOOLCHAINS",
               "XCODE_XCCONFIG_FILE", "BASH_ENV", "ENV", "ZDOTDIR", "PYTHONPATH", "PYTHONHOME",
               "PYTHONSTARTUP", "PYTHONINSPECT", "SUDO_USER", "SUDO_UID", "SUDO_GID", "SUDO_COMMAND"}
    for name, value in base.items():
        require(not ((name in blocked or name.startswith(("DYLD_", "LD_", "ORG_GRADLE_PROJECT_", "BASH_FUNC_")))
                    and value), "ambient execution override must be resolved: " + name)
        require(not name.startswith("GIT_") or name == "GIT_TERMINAL_PROMPT", "ambient Git override")
        require(not name.startswith("P2PKIT_AUDIT_"), "nested/inherited owner is not this hosted controller")
    profile = native_profile(base.get("P2PKIT_OPERATION"))
    require(base.get("DEVELOPER_DIR") == profile["xcode"], "explicit admitted Xcode required")
    home = Path(base["HOME"]).resolve(strict=True)
    physical(home, directory=True)
    require(os.geteuid() != 0 and os.getuid() == os.geteuid(), "ordinary non-elevated user required")
    env = {name: base[name] for name in IDENTITY_ENV if name in base}
    env.update(PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin", HOME=str(home),
               LANG="en_US.UTF-8", LC_ALL="en_US.UTF-8", CI="true", DEVELOPER_DIR=profile["xcode"],
               GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_SYSTEM="/dev/null", GIT_CONFIG_GLOBAL="/dev/null",
               GH_CONFIG_DIR=str(state / "empty-config/gh"), CURL_HOME=str(state / "empty-config/curl"),
               GNUPGHOME=str(state / "empty-config/gpg"), XDG_CONFIG_HOME=str(state / "empty-config/xdg"),
               KONAN_DATA_DIR=str(state / "konan"), ANDROID_USER_HOME=str(state / "android-user"),
               TMPDIR=str(state / "tmp/native"), TEMP=str(state / "tmp/native"), TMP=str(state / "tmp/native"),
               JDK_JAVA_OPTIONS="-Djava.io.tmpdir=" + str(state / "tmp/java"),
               P2PKIT_PYTHON3=sys.executable, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
               P2PKIT_WRITER_SOURCE=str(root), P2PKIT_WRITER_TASK_MAP=str(state / "evidence/task-maps"))
    sdk = Path(base.get("ANDROID_HOME", "")).resolve(strict=True)
    require(sdk.is_dir() and base.get("ANDROID_HOME"), "installed Android SDK required")
    if base.get("ANDROID_SDK_ROOT"):
        require(Path(base["ANDROID_SDK_ROOT"]).resolve(strict=True) == sdk, "Android SDK aliases disagree")
    env["ANDROID_HOME"] = str(sdk)  # Canonicalize the agreeing alias, never rename a platform.
    return env


def policy(jdk17, jdk21, temporary):
    homes = [str(Path(p)) for p in (jdk17, jdk21)]
    require(len(set(homes)) == 2 and all(Path(p).is_absolute() and not re.search(r"[\s,\\=\x00]", p) for p in homes),
            "unsupported JDK policy path")
    require(Path(temporary).is_absolute() and not re.search(r"[\s,\\=\x00]", str(temporary)), "unsupported Java temporary path")
    jvm = "-Xmx2048m -XX:MaxMetaspaceSize=768m -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8 -Djava.io.tmpdir=" + str(temporary)
    lines = ["org.gradle.jvmargs=" + jvm, "org.gradle.workers.max=2", "org.gradle.parallel=false",
             "org.gradle.caching=false", "org.gradle.configuration-cache=false", "org.gradle.daemon=false",
             "kotlin.compiler.execution.strategy=in-process", "org.gradle.java.installations.auto-download=false",
             "org.gradle.java.installations.auto-detect=false",
             "org.gradle.java.installations.paths=" + ",".join(homes)]
    return ("\n".join(lines) + "\n").encode(), jvm


def load_api():
    spec = importlib.util.spec_from_file_location("hosted_lock_audit_helpers", SCRIPTS / "run-audit-command.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StreamBudget:
    """Finite private transcript storage; exhaustion is failure, never a pass."""
    def __init__(self, limit):
        self.remaining = limit
        self.lock = threading.Lock()

    def claim(self, size):
        with self.lock:
            granted = min(size, self.remaining)
            self.remaining -= granted
            return granted


class BoundedReader:
    def __init__(self, source, budget, result, errors, *, limit=16 * MIB):
        self.source, self.budget, self.result, self.errors = source, budget, result, errors
        self.limit, self.exhausted = limit, False
        result.update(observedBytes=0, retainedBytes=0, truncated=False, limitBytes=limit)

    def read(self, size=65536):
        if self.exhausted:
            return b""
        block = self.source.read(min(65536, size) if size >= 0 else 65536)
        self.result["observedBytes"] += len(block)
        available = min(len(block), self.limit - self.result["retainedBytes"])
        granted = self.budget.claim(available)
        self.result["retainedBytes"] += granted
        if granted != len(block):
            self.exhausted = self.result["truncated"] = True
            self.errors.append("Private transcript bound exceeded; retained prefix is NOT complete execution evidence")
        return block[:granted]

    def close(self):
        self.source.close()


def scope_domain(start):
    return {key: start[key] for key in ("job", "invocation", "state", "home", "cwd")}


def baseline_keys(values):
    require(isinstance(values, list) and len(values) <= processes.MAX_PROCESSES, "bounded original native baseline required")
    for value in values:
        require(isinstance(value, list) and len(value) == 4 and
                all(type(part) is int and 0 <= part < 2 ** 64 for part in value) and
                0 < value[0] < 2 ** 31 and value[3] < 1000000, "invalid Darwin lifetime tuple")
    keys = {tuple(value) for value in values}
    require(len(keys) == len(values), "duplicate native baseline lifetime")
    return keys


def save_baseline(scope, directory, start):
    require(scope.name == "darwin-libproc-audit-token", "hosted writer requires actual Darwin ownership backend")
    values = [list(key) for key in sorted(scope.baseline)]
    baseline_keys(values)
    record(directory / "baseline.json", {"schema": 1, "backend": scope.name, "domain": scope_domain(start), "lifetimes": values})


def recover_scope(directory, start):
    """Reuse the ORIGINAL pre-launch exclusion set, not a later process census.

    A fresh PosixScope excludes all processes present at its creation. Using that
    new baseline would hide precisely the orphans being recovered. Only the
    persisted exclusion set changes here: live markers/domain checks and fresh
    native audit-token acquisition/signaling remain the maintained backend's.
    """
    launch = parse(read(directory / "launch-attempt.json"))
    require(launch["job"] == start["job"] and launch["invocation"] == start["invocation"] and
            launch["argv"] == start["argv"] and launch["baselineSha256"] == digest(directory / "baseline.json"),
            "durable original launch/baseline binding differs")
    saved = parse(read(directory / "baseline.json"))
    require(set(saved) == {"schema", "backend", "domain", "lifetimes"} and saved["schema"] == 1 and
            saved["backend"] == "darwin-libproc-audit-token" and saved["domain"] == scope_domain(start),
            "original native baseline binding differs")
    keys = baseline_keys(saved["lifetimes"])
    scope = processes.make_scope(start["job"], start["invocation"], start["state"], start["home"])
    try:
        require(scope.name == saved["backend"], "recovery backend differs")
        scope.baseline = keys
        return scope
    except Exception:
        scope.close()
        raise


class Command:
    def __init__(self, runtime, label, argv, seconds=120, invocation=None):
        self.rt, self.label, self.argv, self.seconds = runtime, label, list(argv), seconds
        self.invocation = invocation or uuid.uuid4().hex
        require(re.fullmatch(r"[0-9a-f]{32}", self.invocation), "bad invocation")
        self.directory = runtime.commands / label
        self.directory.mkdir(mode=0o700)
        self.scope = self.child = None
        self.tees = []
        self.row = {"argv": self.argv, "invocation": self.invocation, "timeoutSeconds": seconds,
                    "launchAttempted": False, "waitExitCode": None, "errors": [], "drains": [], "streams": {}}
        record(self.directory / "start.json", {**self.row, "job": runtime.job, "state": str(runtime.state),
                                               "home": str(runtime.home), "cwd": str(runtime.root)})

    def start(self, finalizing=False):
        self.rt.check(finalizing)
        self.scope = processes.make_scope(self.rt.job, self.invocation, str(self.rt.state), str(self.rt.home))
        save_baseline(self.scope, self.directory, parse(read(self.directory / "start.json")))
        env = processes.ownership_environment(self.rt.env, self.rt.job, self.invocation, str(self.rt.state), str(self.rt.home))
        self.row["launchAttempted"] = True
        self.row["startedMonotonic"] = time.monotonic()
        record(self.directory / "launch-attempt.json", {"job": self.rt.job, "invocation": self.invocation,
            "startedMonotonic": self.row["startedMonotonic"], "argv": self.argv,
            "baselineSha256": digest(self.directory / "baseline.json")})
        try:
            self.child = self.scope.spawn(self.argv, str(self.rt.root), env)
        finally:
            if self.child is None and self.scope.leaders:
                require(len(self.scope.leaders) == 1, "unexpected partial-launch leader set")
                self.child = self.scope.leaders[0]
            if self.child is not None:
                for name, pipe in (("stdout", self.child.stdout), ("stderr", self.child.stderr)):
                    observation = self.row["streams"][name] = {}
                    bounded = BoundedReader(pipe, self.rt.final_stream_budget if finalizing else self.rt.stream_budget,
                                            observation, self.row["errors"])
                    self.tees.append(self.rt.api.Tee(bounded, self.directory / (name + ".log"), None, self.row["errors"]))

    def wait(self, finalizing=False):
        if self.scope is None:
            self.start(finalizing)
        remaining = self.seconds - (time.monotonic() - self.row["startedMonotonic"])
        require(remaining > 0, "command absolute deadline")
        def check():
            self.rt.check(finalizing)
            require(not self.row["errors"], "original command stream/ownership failure")
        self.row["waitExitCode"] = self.rt.api.wait_process(
            self.scope, self.child, remaining, self.rt.cancelled, check, stop=finalizing)
        return self.row["waitExitCode"]

    def drain(self, stage):
        outcome = {"stage": stage, "survivors": None, "error": None}
        try:
            outcome["survivors"] = self.scope.drain(grace=5, kill_wait=5) if self.scope is not None else []
            require(not outcome["survivors"], "owned survivors")
        except Exception as error:
            outcome["error"] = str(error)
            self.row["errors"].append(stage + ": " + str(error))
        self.row["drains"].append(outcome)

    def close(self):
        try:
            if self.child is not None:
                self.row["exitAfterDrain"] = self.child.poll()
            if self.scope is not None:
                self.row["ownership"] = self.scope.description()
                self.row["errors"].extend(self.row["ownership"].get("discoveryErrors", []))
        except Exception as error:
            self.row["errors"].append("retirement record: " + str(error))
        finally:
            for tee in self.tees:
                try:
                    tee.finish()
                except Exception as error:
                    self.row["errors"].append("stream finalization: " + str(error))
            if self.scope is not None:
                try:
                    self.scope.close()
                except Exception as error:
                    self.row["errors"].append("native handle close: " + str(error))
            self.row["endedMonotonic"] = time.monotonic()
            record(self.directory / "command.json", self.row)
        require(not self.row["errors"], "original command finalization incomplete")

    def text(self):
        require(self.row["waitExitCode"] == 0 and not self.row["errors"], "command not successful")
        return read(self.directory / "stdout.log").decode("utf-8")


class Runtime:
    def __init__(self, root, state, binding, env, *, job=None):
        self.root, self.state, self.binding, self.env = root, state, binding, env
        self.profile = native_profile(binding["operation"])
        self.job, self.api = job or uuid.uuid4().hex, load_api()
        self.home, self.evidence, self.commands = state / "gradle-home", state / "evidence", state / "evidence/commands"
        self.state_identity, self.home_identity = identity(state), identity(self.home)
        self.task_maps = self.evidence / "task-maps"
        self.stream_budget, self.final_stream_budget = StreamBudget(64 * MIB), StreamBudget(8 * MIB)
        self.cancelled, self.errors, self.command_index = [], [], 0
        self.resource = None
        self.resource_cursor, self.resource_buffer, self.resource_samples = 0, b"", {}
        self.resource_ready = self.resource_stopping = False
        self.simulator = None
        self.custody_attempted = False
        self.custody_request = None
        self.report = {"schema": 1, "scope": "MUTABLE_FULL_WRITER_NOT_AUDIT_LEAF", "state": str(state),
                       "binding": binding, "job": self.job, "writer": None, "stop": None, "errors": self.errors,
                       "candidateAccepted": False, "releaseGateExecuted": False, "physicalDeviceEvidence": False}
        self.lockfiles = []
        self.jvm = None

    def fail(self, stage, error):
        self.errors.append({"stage": stage, "type": type(error).__name__, "message": str(error)})

    def safely(self, stage, action):
        try:
            return action()
        except Exception as error:
            self.fail(stage, error)
            return None

    def check(self, finalizing=False):
        # Native drains do not depend on this check. A replaced path must never
        # redirect a cleanup Gradle command into someone else's directory.
        require(identity(self.state) == self.state_identity and identity(self.home) == self.home_identity,
                "owned state/Gradle home identity changed")
        # A failed resource lane/cancellation must never suppress same-home stop,
        # native drains, original-custody collection or failure-evidence retention.
        if finalizing:
            return
        if self.resource is not None and not self.resource_stopping:
            require(not self.resource.row["errors"], "resource observer stream/ownership failure")
            path = self.resource.directory / "stdout.log"
            if path.exists():
                require(path.stat().st_size <= 16 * MIB, "resource transcript bound")
                with path.open("rb") as stream:
                    stream.seek(self.resource_cursor)
                    raw = stream.read(MIB)
                self.resource_cursor += len(raw)
                self.resource_buffer += raw
                while b"\n" in self.resource_buffer:
                    line, self.resource_buffer = self.resource_buffer.split(b"\n", 1)
                    row = parse(line)
                    require(row.get("kind") != "resource-error", "resource observer failed")
                    if row.get("kind") == "resource-sample":
                        self.resource_samples[row["lane"]] = row
                    if row.get("kind") == "resource-ready":
                        self.resource_ready = True
            if self.resource.child is not None:
                self.resource.scope.discover()
                if not finalizing:
                    require(self.resource.child.poll() is None, "resource observer exited during work")
            if self.resource_ready and not finalizing:
                resources.check_shared_freshness(self.resource_samples)
        if not finalizing:
            require(not self.cancelled, "controller cancelled")
            require(not self.errors, "prior failure remains latched")

    def command(self, label, argv, seconds=120, *, finalizing=False, allowed=(0,)):
        self.command_index += 1
        cmd = Command(self, f"{self.command_index:03d}-{label}", argv, seconds)
        try:
            require(cmd.wait(finalizing) in allowed, label + " exited nonzero")
        finally:
            cmd.drain("command-final")
            cmd.close()
        return cmd

    def git(self, label, *args, finalizing=False, allowed=(0,)):
        return self.command(label, ["/usr/bin/git", "--no-replace-objects", "-C", str(self.root), *args],
                            30, finalizing=finalizing, allowed=allowed)

    def source(self, phase, finalizing=False):
        sha = self.git(phase + "-commit", "rev-parse", "HEAD", finalizing=finalizing).text().strip()
        tree = self.git(phase + "-tree", "rev-parse", "HEAD^{tree}", finalizing=finalizing).text().strip()
        status = self.git(phase + "-status", "status", "--porcelain=v1", "--untracked-files=all", finalizing=finalizing).text()
        diff = self.git(phase + "-diff", "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", finalizing=finalizing)
        raw = read(diff.directory / "stdout.log")
        if finalizing:
            write(self.evidence / "source-after.patch", raw)
        return {"commit": sha, "tree": tree, "status": status, "diffSha256": hashlib.sha256(raw).hexdigest()}

    def admit(self):
        before = self.source("before")
        self.report["sourceBefore"] = before
        require(before["commit"] == self.binding["commit"] and before["tree"] == self.binding["tree"] and
                before["status"] == "" and before["diffSha256"] == hashlib.sha256(b"").hexdigest(), "exact clean source required")
        record(self.evidence / "source-before.json", before)
        require(self.git("shallow", "rev-parse", "--is-shallow-repository").text() == "false\n", "full history required")
        self.git("base-ancestry", "merge-base", "--is-ancestor", self.binding["base"], "HEAD")
        names = self.git("local-config-names", "config", "--local", "--name-only", "--get-regexp",
                         r"^(credential\.|include|http\..*extraheader|core\.hooksPath)", allowed=(0, 1))
        require(not read(names.directory / "stdout.log"), "persisted credentials or config includes are not admitted")
        self.lockfiles = self.git("lock-map", "ls-files", "*lockfile").text().splitlines()
        require(len(set(self.lockfiles)) == len(self.lockfiles) == 12, "all twelve tracked locks required")
        require(not (self.root / "local.properties").exists(), "unexpected local SDK settings")
        for path in [*self.api.output_roots(self.root), self.root / ".gradle", self.root / ".kotlin", self.root / "buildSrc/.gradle"]:
            physical(path)
            require(not path.exists(), "fresh output roots required")
        self.copy_candidates("before")
        require(processes.host_role() == self.profile["hostRole"], "selected native interpreter role required")
        version = self.command("macos-version", ["/usr/bin/sw_vers", "-productVersion"]).text().strip()
        require(re.fullmatch(re.escape(self.profile["osMajor"]) + r"\.[0-9]+(?:\.[0-9]+)?", version), "unadmitted macOS major")
        memory = self.command("physical-memory", ["/usr/sbin/sysctl", "-n", "hw.memsize"]).text().strip()
        require(re.fullmatch(r"[0-9]+", memory) and int(memory) >= 7 * GIB, "hosted writer requires at least 7GiB physical RAM")
        self.command("xcode-version", ["/usr/bin/xcodebuild", "-version"])
        xcode = read(self.commands / f"{self.command_index:03d}-xcode-version/stdout.log").decode()
        require(xcode == self.profile["xcodeVersion"], "unadmitted Xcode/build")
        self.command("xcode-first-launch", ["/usr/bin/xcodebuild", "-checkFirstLaunchStatus"])
        homes = []
        for major in (17, 21):
            home = Path(self.command("java-home-" + str(major), ["/usr/libexec/java_home", "-v", str(major)]).text().strip()).resolve(strict=True)
            jdk = self.command("java-" + str(major), [str(home / "bin/java"), "-XshowSettings:properties", "-version"])
            output = read(jdk.directory / "stderr.log").decode()
            require(re.search(r"^\s*java.version = " + str(major) + r"\.", output, re.M) and
                    re.search(r"^\s*os.arch = (" + self.profile["javaArch"] + r")\s*$", output, re.M) and
                    re.search(r"^\s*java.io.tmpdir = " + re.escape(str(self.state / "tmp/java")) + r"\s*$", output, re.M),
                    "native JDK/version/temporary routing not admitted")
            require((home / "bin/javac").is_file(), "native JDK compiler missing")
            homes.append(str(home))
        raw, self.jvm = policy(*homes, self.state / "tmp/java")
        write(self.home / "gradle.properties", raw)
        self.env.update(JAVA_HOME=homes[0], P2PKIT_AUDIT_JDK21=homes[1], PATH=homes[0] + "/bin:" + self.env["PATH"])
        self.report["javaPolicy"] = {"homes": homes, "propertiesSha256": digest(self.home / "gradle.properties"),
                                     "workers": 2, "automaticJdkDownload": False}
        for folder, level in (("android-36", "36"), ("android-37.0", "37.0")):
            raw = read(Path(self.env["ANDROID_HOME"]) / "platforms" / folder / "source.properties").decode()
            require(re.findall(r"^AndroidVersion.ApiLevel=(.*)$", raw, re.M) == [level], "literal Android platform metadata required")
        runtimes = parse(self.command("simulator-runtimes", ["/usr/bin/xcrun", "simctl", "list", "--json", "runtimes"]).text())
        matches = [row for row in runtimes["runtimes"] if row.get("identifier") == self.profile["runtime"]]
        require(len(matches) == 1 and matches[0].get("version") == self.profile["runtimeVersion"] and matches[0].get("isAvailable") is True,
                "real admitted simulator runtime unavailable")
        devices = parse(self.command("simulator-devices", ["/usr/bin/xcrun", "simctl", "list", "--json", "devices", "available"]).text())
        matches = [row for row in devices["devices"].get(self.profile["runtime"], []) if row.get("name") == "iPhone 17" and
                   row.get("state") == "Shutdown" and row.get("isAvailable") is True]
        require(len(matches) == 1 and re.fullmatch(r"[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}", matches[0].get("udid", "")),
                "one available originally Shutdown iPhone 17 required")
        self.simulator = matches[0]
        self.report["simulatorBefore"] = self.simulator
        record(self.evidence / "simulator-before.json", self.simulator)
        self.env["P2PKIT_WRITER_SIMULATOR"] = self.simulator["udid"]
        write(self.home / "init.d/owned-simulator.gradle", read(self.root / INIT))
        record(self.state / "execution-environment.json", {"environment": self.env, "jvmArguments": self.jvm,
            "binding": self.binding, "job": self.job})
        self.command("native-controls", [sys.executable, "-I", "-B", "-S", str(SCRIPTS / "tests/run-audit-command-test.py"),
            "--expected-host", self.profile["hostRole"], "--evidence-dir", str(self.evidence / "native-controls"),
            "--fixture-parent", str(self.state / "fixtures/native-tmp")], 1800)
        self.multicast()

    def start_resource(self):
        cmd = Command(self, "resources", [sys.executable, "-I", "-B", "-S", str(SCRIPTS / "hosted_lock_resources.py"),
            "observe", "--root", str(self.root), "--state", str(self.state), "--stop-file", str(self.state / "resource-stop"),
            "--expected-host", self.profile["hostRole"]], 10000)
        self.resource = cmd
        cmd.start()
        deadline = time.monotonic() + 10
        while not self.resource_ready:
            self.check()
            require(time.monotonic() < deadline, "resource baseline admission timed out")
            time.sleep(.05)

    def multicast(self):
        # Xcode's launcher may be a symlink. The paired Java/Python diagnostic
        # requires the canonical executable; do not relax its admission guard.
        python = Path(sys.executable)
        require(python.is_absolute(), "absolute running Python interpreter required")
        python = python.resolve(strict=True)
        require(python.is_file() and os.access(python, os.X_OK), "regular executable Python interpreter required")
        vendor = self.root / "library/p2p-transport-lan/vendor/jmdns/src/main"
        fixture = self.root / "library/p2p-transport-lan/src/jvmTest/java/dev/p2pkit/transport/lan/internal/jmdns/impl/JmdnsCloseLifecycleFixture.java"
        sources = sorted(vendor.glob("java/**/*.java"))
        require(len(sources) == 60 and all(read(p) for p in sources), "exact sixty vendored sources required")
        resource = vendor / "resources/dev/p2pkit/transport/lan/internal/jmdns/version.properties"
        require(resource.is_file() and fixture.is_file(), "current JmDNS admission inputs missing")
        pin = "5d6298b93a1905c32cda6478808ac14c2d4a47e91535e53c41f7feeb85d946f4"
        metadata = ET.fromstring(read(self.root / "gradle/verification-metadata.xml"))
        pins = metadata.findall("./v:components/v:component[@group='org.slf4j'][@name='slf4j-api'][@version='2.0.7']/"
                                 "v:artifact[@name='slf4j-api-2.0.7.jar']/v:sha256",
                                 {"v": "https://schema.gradle.org/dependency-verification"})
        require([row.get("value") for row in pins] == [pin], "SLF4J source verification pin changed")
        work = self.state / "work/jmdns"
        work.mkdir(mode=0o700)
        for name in ("vendor", "fixture"):
            (work / name).mkdir(mode=0o700)
        jar = work / "slf4j-api-2.0.7.jar"
        self.command("multicast-dependency", ["/usr/bin/curl", "--disable", "--fail", "--silent", "--show-error",
            "--proto", "=https", "--tlsv1.2", "--connect-timeout", "15", "--max-time", "60", "--max-filesize", "1048576",
            "--output", str(jar), "https://repo.maven.apache.org/maven2/org/slf4j/slf4j-api/2.0.7/slf4j-api-2.0.7.jar"], 90)
        require(0 < jar.stat().st_size <= MIB and digest(jar) == pin, "SLF4J download/hash mismatch")
        compiler = [self.env["JAVA_HOME"] + "/bin/javac", "-J-Xmx256m", "-J-XX:ActiveProcessorCount=2"]
        self.command("multicast-vendor-compile", [*compiler, "--release", "8", "-encoding", "UTF-8", "-classpath", str(jar),
            "-d", str(work / "vendor"), *map(str, sources)], 90)
        self.command("multicast-fixture-compile", [*compiler, "--release", "17", "-encoding", "UTF-8",
            "-classpath", os.pathsep.join(map(str, (work / "vendor", jar))), "-d", str(work / "fixture"), str(fixture)], 90)
        command = self.command("multicast-control", [self.env["JAVA_HOME"] + "/bin/java", "-Xms16m", "-Xmx128m",
            "-XX:MaxMetaspaceSize=128m", "-XX:ActiveProcessorCount=2", "-XX:+UseSerialGC",
            "-Dorg.slf4j.simpleLogger.defaultLogLevel=off", "-Dp2pkit.audit.jmdnsStartupPrimitives=true",
            "-Dp2pkit.audit.pythonExecutable=" + str(python), "-cp",
            os.pathsep.join(map(str, (work / "fixture", work / "vendor", vendor / "resources", jar))),
            "dev.p2pkit.transport.lan.internal.jmdns.impl.JmdnsCloseLifecycleFixture", "control"], 45)
        transcript = read(command.directory / "stdout.log", 65536) + read(command.directory / "stderr.log", 65536)
        require(transcript.splitlines().count(b"PASS mode=control") == 1 and b"FAIL mode=" not in transcript and
                b"phase=fixture_rescue_begin" not in transcript, "natural multicast control not admitted")
        record(self.evidence / "multicast-inputs.json", {"files": {str(p.relative_to(self.root)): digest(p) for p in
            [*sources, resource, fixture]}, "dependencySha256": pin, "scope": "STARTUP_CONTROL_NOT_EIGHT_MODE_ACCEPTANCE"})

    def prepare_custody(self):
        self.custody_attempted = True
        write(self.state / "custody-attempted", b"attempted\n")
        argv = ["scripts/prepare-dependency-update.sh", self.binding["base"]]
        self.command("custody-prepare", [sys.executable, str(self.root / CUSTODY), "prepare", "--root", str(self.root),
            "--directory", str(self.state / "custody"), "--home", str(self.home), "--owner-state", str(self.state),
            "--owner-kind", "writer", "--writer-job", self.job, "--scope", "both", "--", *argv])
        request = parse(read(self.state / "custody/request.json"))
        require(request["source"] == self.report["sourceBefore"] and request["command"] == argv and
                request["owner"]["job"] == self.job and request["ownerState"] == str(self.state), "custody reservation differs")
        self.custody_request = request

    def product(self):
        request = self.custody_request
        product = Command(self, "writer", request["command"], WRITER_SECONDS, request["owner"]["productInvocation"])
        stop = None
        try:
            require(product.wait() == 0, "complete maintained writer failed")
        except Exception as error:
            self.fail("writer", error)
        finally:
            try:
                self.safely("pre-stop-drain", lambda: product.drain("pre-stop"))
                if product.row["launchAttempted"]:
                    try:
                        stop = Command(self, "stop", [str(self.root / "gradlew"), "--stop", "--console=plain", "--no-parallel",
                            "--max-workers=2", "-Dorg.gradle.jvmargs=" + self.jvm], STOP_SECONDS, request["owner"]["stopInvocation"])
                        require(stop.wait(True) == 0, "same-home Gradle stop failed")
                    except Exception as error:
                        self.fail("stop", error)
                    finally:
                        if stop is not None:
                            self.safely("stop-drain", lambda: stop.drain("stop-final"))
                            self.safely("stop-close", stop.close)
            finally:
                self.safely("product-drain", lambda: product.drain("product-final"))
                self.safely("product-close", product.close)
                self.report["writer"] = product.row
                self.report["stop"] = stop.row if stop else None

    def collect_custody(self):
        if not self.custody_attempted:
            self.report["transcriptCustody"] = {"result": "NOT_STARTED", "retirement": "NOT_APPLICABLE"}
            return
        snapshot = {"scope": self.report["scope"], "state": str(self.state), "sourceBefore": self.report.get("sourceBefore"),
                    "writer": self.report["writer"] or {}, "stop": self.report["stop"] or {}}
        target = self.state / "custody-owner-snapshot.json"
        if not target.exists():
            record(target, snapshot)
        # A finalized or partly collected original is one-shot. Recovery never
        # rewrites it or substitutes its later cleanup stop for the original stop.
        if not (self.state / "custody/result.json").exists():
            self.command("custody-collect", [sys.executable, str(self.root / CUSTODY), "collect", "--directory",
                str(self.state / "custody"), "--owner-result", str(target)], finalizing=True, allowed=(0, 125))
        result = parse(read(self.state / "custody/result.json"))
        self.report["transcriptCustody"] = result
        if result.get("retirement") == "KNOWN":
            self.command("custody-uninstall", [sys.executable, str(self.root / CUSTODY), "uninstall", "--directory",
                str(self.state / "custody")], finalizing=True)
        require(result.get("result") == "RETAINED" and result.get("retirement") == "KNOWN", "original transcript custody HOLD")

    def retire_simulator(self):
        if self.simulator is None:
            return
        def query():
            document = parse(self.command("simulator-retire-query", ["/usr/bin/xcrun", "simctl", "list", "--json", "devices", "available"],
                                          finalizing=True).text())
            rows = [row for row in document["devices"].get(self.profile["runtime"], []) if row.get("udid") == self.simulator["udid"]]
            require(len(rows) == 1 and rows[0].get("isAvailable") is True, "owned simulator retirement unknown")
            return rows[0]
        before = query()
        if before["state"] != "Shutdown":
            require((self.report.get("writer") or {}).get("launchAttempted") is True or
                    self.report.get("interruptedProductAttempted") is True, "unlaunched simulator changed externally")
            self.command("simulator-shutdown", ["/usr/bin/xcrun", "simctl", "shutdown", self.simulator["udid"]], finalizing=True)
        after = query()
        require(after["state"] == "Shutdown", "owned simulator did not retire")
        self.report["simulatorRetirement"] = {"before": before, "after": after, "status": "KNOWN_SHUTDOWN"}

    def copy_candidates(self, phase):
        paths = [*self.lockfiles, "gradle/verification-metadata.xml"]
        rows, failures = [], []
        for name in paths:
            try:
                target = self.evidence / "candidate" / phase / name
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                raw = read(self.root / name)
                write(target, raw)
                rows.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            except Exception as error:
                failures.append({"path": name, "error": type(error).__name__ + ": " + str(error)})
        record(self.evidence / (phase + "-candidate.json"), {"files": rows, "errors": failures})
        require(not failures, "candidate retention incomplete; all input copies were attempted")

    def retain(self):
        self.safely("candidate-after", lambda: self.copy_candidates("after"))
        after = self.safely("source-after", lambda: self.source("after", True))
        self.report["sourceAfter"] = after
        if after:
            def validate_delta():
                require(after["commit"] == self.binding["commit"] and after["tree"] == self.binding["tree"], "writer changed Git identity")
                changed = self.git("candidate-paths", "diff", "--name-only", "HEAD", finalizing=True).text().splitlines()
                self.report["changedTrackedFiles"] = changed
                require(set(changed) <= set(self.lockfiles + ["gradle/verification-metadata.xml"]), "writer changed noncandidate source")
                require(not self.git("candidate-untracked", "ls-files", "--others", "--exclude-standard",
                                     finalizing=True).text(), "writer left untracked source")
            self.safely("source-delta", validate_delta)
        self.safely("report-retention", lambda: self.api.retain_reports(self.root, self.state, [], {}, self.evidence))
        self.safely("generated-retention", self.retain_generated)
        self.safely("embedded-producer-retention", self.retain_embedded_jmdns)
        if (self.state / "custody").exists():
            self.safely("custody-copy", lambda: copy_tree(self.state / "custody", self.evidence / "custody", 64 * MIB))
        if (self.state / "custody-owner-snapshot.json").exists():
            self.safely("custody-owner-copy", lambda: write(self.evidence / "custody-owner-snapshot.json",
                read(self.state / "custody-owner-snapshot.json")))

    def retain_generated(self):
        files, task_map = set(), []
        outputs = self.api.output_roots(self.root)
        for path in self.task_maps.glob("*.jsonl"):
            for line in read(path, 64 * MIB).splitlines():
                row = parse(line)
                task = row.get("task", {})
                if row.get("event") == "graph" and "abi" in task.get("path", "").lower():
                    for raw in task.get("outputs", []):
                        output = physical(Path(raw))
                        require(any(output == build or build in output.parents for build in outputs), "ABI map escapes generated roots")
                        task_map.append({"task": task["path"], "output": raw})
                        if output.is_file():
                            files.add(output)
                        elif output.is_dir():
                            files.update(self.api.regular_report_files(output, [0]))
        for build in outputs:
            if build.is_dir():
                for path in self.api.regular_report_files(build, [0]):
                    if path.suffix in (".api", ".abi") or (build / "dokka/html") in path.parents:
                        files.add(path)
        rows, total = [], 0
        for source in sorted(files):
            raw = read(source, 64 * MIB)
            total += len(raw)
            require(total <= 256 * MIB and len(rows) < 10000, "generated retention bound")
            relative = source.relative_to(self.root)
            target = self.evidence / "generated" / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            write(target, raw)
            require(digest(source) == digest(target), "generated output changed during retention")
            rows.append({"path": relative.as_posix(), "sha256": digest(target), "bytes": len(raw)})
        record(self.evidence / "generated-manifest.json", {"files": rows, "actualAbiTaskOutputMap": task_map,
            "limitation": "Generated bytes and maps, not independent eight-baseline or release acceptance"})

    def retain_embedded_jmdns(self):
        relative = Path("library/p2p-transport-lan/build/embedded-jmdns/p2pkit-internal-jmdns.jar")
        source = self.root / relative
        result = {"scope": "ACTUAL_PRIVATE_PRODUCER_NOT_OUTER_PUBLICATION", "path": relative.as_posix(),
                  "task": ":p2p-transport-lan:embeddedJmdnsJar", "status": "NOT_GENERATED", "sbom": []}
        try:
            if not source.exists():
                require((self.report.get("writer") or {}).get("waitExitCode") != 0, "successful writer lacks actual JmDNS producer")
                return
            raw = read(source, 8 * MIB)
            target = self.evidence / "generated" / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            write(target, raw)
            jar_hash = digest(target)
            require(digest(source) == jar_hash, "producer changed during retention")
            result.update(status="RETAINED", sha256=jar_hash, bytes=len(raw))
            vendor = "library/p2p-transport-lan/vendor/jmdns"
            names = self.git("producer-inputs", "ls-files", "--", vendor, "build.gradle.kts",
                             "library/p2p-transport-lan/build.gradle.kts", finalizing=True).text().splitlines()
            require(names and len(names) < 1000, "producer source input inventory missing/excessive")
            result["inputs"] = {name: digest(self.root / name) for name in names}
            component = parse(read(self.root / vendor / "PROVENANCE.json"))["component"]["bomRef"]
            # The normal report collector retains the complete JSON/XML. This
            # check binds their private component hash to the actual retained
            # producer; it is not complete SBOM/publication acceptance.
            for suffix in ("json", "xml"):
                path = self.root / ("build/reports/cyclonedx/bom." + suffix)
                if not path.exists():
                    result["sbom"].append({"path": str(path.relative_to(self.root)), "status": "NOT_GENERATED"})
                    require((self.report.get("writer") or {}).get("waitExitCode") != 0, "successful writer lacks aggregate SBOM")
                    continue
                content = read(path)
                if suffix == "json":
                    matches = [row for row in parse(content)["components"] if row.get("bom-ref") == component]
                    require(len(matches) == 1, "SBOM private producer missing/duplicated")
                    hashes = [row["content"] for row in matches[0]["hashes"] if row.get("alg") == "SHA-256"]
                else:
                    require(b"<!DOCTYPE" not in content.upper() and b"<!ENTITY" not in content.upper(), "unadmitted SBOM XML declarations")
                    matches = [row for row in ET.fromstring(content).findall("{*}components/{*}component")
                               if row.get("bom-ref") == component]
                    require(len(matches) == 1, "SBOM private producer missing/duplicated")
                    hashes = [row.text for row in matches[0].findall("{*}hashes/{*}hash") if row.get("alg") == "SHA-256"]
                require(hashes == [jar_hash], "SBOM private producer hash differs from actual generated JAR")
                result["sbom"].append({"path": str(path.relative_to(self.root)), "status": "HASH_MATCH",
                                       "sha256": hashlib.sha256(content).hexdigest()})
        finally:
            record(self.evidence / "embedded-jmdns-manifest.json", result)

    def finish_resource(self):
        if self.resource is None:
            return
        self.resource_stopping = True
        try:
            if self.resource.row["launchAttempted"]:
                write(self.state / "resource-stop", b"")
                # Observer exits normally after joining both observation lanes.
                self.resource.seconds = time.monotonic() - self.resource.row["startedMonotonic"] + 15
                require(self.resource.wait(True) == 0, "resource observer did not retire normally")
        finally:
            try:
                self.resource.drain("resource-final")
                self.resource.close()
            finally:
                self.report["resourceRetirement"] = self.resource.row

    def finalize(self):
        self.safely("custody", self.collect_custody)
        self.safely("simulator", self.retire_simulator)
        self.safely("retention", self.retain)
        self.safely("resource-retirement", self.finish_resource)
        self.report["finalExitCode"] = 0 if not self.errors and (self.report.get("writer") or {}).get("waitExitCode") == 0 else 125
        self.report["candidateStatus"] = "GENERATED_REQUIRES_INDEPENDENT_REVIEW" if self.report["finalExitCode"] == 0 else "HOLD"
        self.report["cleanup"] = "Retained privately until encrypted export validation; no source reset, cache import or publication"
        record(self.evidence / "result.json", self.report)


def copy_tree(source, target, limit):
    physical(source, directory=True)
    require(not target.exists(), "retention target already exists")
    target.mkdir(mode=0o700)
    pending, total, count = [source], 0, 0
    while pending:
        parent = pending.pop()
        for path in sorted(parent.iterdir()):
            count += 1
            require(count <= 20000, "retention entry bound")
            physical(path)
            dest = target / path.relative_to(source)
            if path.is_dir():
                dest.mkdir(mode=0o700)
                pending.append(path)
            else:
                raw = read(path, 64 * MIB)
                total += len(raw)
                require(total <= limit, "retention byte bound")
                write(dest, raw)
                require(digest(path) == digest(dest), "original evidence changed during copy")


def paths(binding):
    temporary = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    physical(temporary, directory=True)
    suffix = binding["runId"] + "-" + binding["runAttempt"]
    return temporary / ("p2pkit-lock-state-" + suffix), temporary / ("p2pkit-lock-export-" + suffix) / "encrypted"


def acquire(state):
    path = physical(state / "controller.lock")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    require(os.fstat(fd).st_nlink == 1, "controller lock has aliases")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        os.close(fd)
        raise
    return fd


def run(root, binding):
    state, output = paths(binding)
    require(not (state == root or root in state.parents or state in root.parents), "state/source must be disjoint")
    state.mkdir(mode=0o700)
    fd = acquire(state)
    runtime = None
    try:
        for name in ("evidence", "evidence/commands", "evidence/task-maps", "gradle-home", "gradle-home/init.d", "konan",
                     "android-user", "tmp", "tmp/java", "tmp/native", "empty-config", "empty-config/gh", "empty-config/curl",
                     "empty-config/gpg", "empty-config/xdg", "work", "fixtures", "fixtures/native-tmp", "recipient-check"):
            (state / name).mkdir(mode=0o700)
        write(state / "recipient.asc", os.environ["P2PKIT_EVIDENCE_PUBLIC_KEY"].encode("ascii"))
        job = uuid.uuid4().hex
        record(state / "context.json", {"schema": 1, "binding": binding, "job": job, "root": str(root),
            "stateIdentity": identity(state), "gradleHomeIdentity": identity(state / "gradle-home"),
            "boundary": "CHILD_CREDENTIAL_NONINHERITANCE_NOT_SAME_USER_SANDBOX",
            "parentSshAgentHookPresent": "SSH_AUTH_SOCK" in os.environ,
            "coldAcquisitionPlan": {"installedJdkSdkXcode": "admit without installing", "firstFetchMaxBytes": MIB,
                "fullGraph": "one unchanged complete preparer; no retry", "observedIngressAbortBytes": 8 * GIB,
                "limitation": "Sampled hosted interface accounting, NOT an absolute wire-byte quota; no local cache upload"}})
        # Recipient validity precedes every native fixture, dependency fetch and build.
        hosted_evidence.validate_recipient(state / "recipient.asc", binding["recipientFingerprint"], state / "recipient-check")
        env = credential_free_environment(dict(os.environ), state, root)
        runtime = Runtime(root, state, binding, env, job=job)
        record(state / "evidence/environment-boundary.json", {"allowedChildKeys": sorted(env),
            "ambientAgentsModified": False, "ambientCredentialValuesReadOrRetained": False,
            "limitation": "No-child Mac snapshot's prior SSH-agent rejection remains unchanged; this is a different child-only boundary"})
        for number in (signal.SIGINT, signal.SIGTERM):
            signal.signal(number, lambda value, _: runtime.cancelled.append(value))
        runtime.start_resource()
        runtime.admit()
        runtime.prepare_custody()
        runtime.check()
        require(runtime.resource_samples["fast"]["pressure"] == 1, "current NORMAL pressure required before full writer")
        record(runtime.evidence / "before-writer-resources.json", runtime.resource_samples)
        runtime.product()
    except Exception as error:
        if runtime is not None:
            runtime.fail("controller", error)
        else:
            record(state / "evidence/bootstrap-failure.json", {"type": type(error).__name__, "message": str(error), "candidateStatus": "HOLD"})
    finally:
        try:
            if runtime is not None:
                runtime.finalize()
        finally:
            os.close(fd)
    return runtime.report["finalExitCode"] if runtime is not None else 125


def quiesce(state, context, phase="seal-quiescence"):
    """A final current native observation, never a replacement for original results."""
    rows, recovered = [], False
    commands = state / "evidence/commands"
    for directory in sorted(commands.iterdir()):
        physical(directory, directory=True)
        start = parse(read(directory / "start.json"))
        require(start["job"] == context["job"] and start["state"] == str(state) and
                start["home"] == str(state / "gradle-home") and start["cwd"] == context["root"], "seal ownership differs")
        if not (directory / "launch-attempt.json").exists():
            # The launch-attempt record is durable before spawn. No subprocess
            # was possible for this directory; a partial baseline is not needed.
            rows.append({"invocation": start["invocation"], "launchAttempted": False})
            continue
        scope = recover_scope(directory, start)
        try:
            before = scope.discover()
            after = scope.drain(grace=5, kill_wait=5) if before else []
            description = scope.description()
            require(not after and not description.get("discoveryErrors"), "cannot seal evidence with unknown active writers")
            rows.append({"invocation": start["invocation"], "observedBefore": before, "survivors": after,
                         "ownership": description})
            recovered = recovered or bool(before)
        finally:
            scope.close()
    record(state / ("evidence/" + phase + ".json"), {"scope": "FINAL_OBSERVATION_NOT_ORIGINAL_EXECUTION",
        "recoveredUnexpectedWorkers": recovered, "candidateHold": recovered, "commands": rows})
    return recovered


def recover_interrupted(root, state, binding, context):
    """Attempt every finalizer, preserving all earlier files and acceptance holds."""
    env = credential_free_environment(dict(os.environ), state, root)
    runtime = Runtime(root, state, binding, env, job=context["job"])
    original_evidence = runtime.evidence
    runtime.evidence = original_evidence / "recovery"
    runtime.evidence.mkdir(mode=0o700)
    runtime.command_index = max([0, *[int(p.name[:3]) for p in runtime.commands.iterdir()
                                      if re.match(r"[0-9]{3}-", p.name)]])
    recovery = {"scope": "INTERRUPTED_OWNER_RECOVERY_NOT_ACCEPTANCE", "candidateStatus": "HOLD",
                "finalExitCode": 125, "errors": runtime.errors}

    def original_records():
        source = original_evidence / "source-before.json"
        if source.exists():
            runtime.report["sourceBefore"] = parse(read(source))
        elif (state / "custody/request.json").exists():
            runtime.report["sourceBefore"] = parse(read(state / "custody/request.json"))["source"]
        for label in ("writer", "stop"):
            path = runtime.commands / label / "command.json"
            if path.exists():
                runtime.report[label] = parse(read(path))
                recovery["original" + label.title()] = runtime.report[label]
        # The pre-writer map is an original observation. Do not infer twelve
        # successful after copies merely because a currently tracked file exists.
        before = original_evidence / "before-candidate.json"
        if before.exists():
            names = [row["path"] for row in parse(read(before))["files"]]
            runtime.lockfiles = [name for name in names if name.endswith("lockfile")]
            require(len(runtime.lockfiles) == len(set(runtime.lockfiles)) == 12 and
                    all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in runtime.lockfiles),
                    "original twelve-lock map incomplete")
        else:
            runtime.lockfiles = runtime.git("recovery-lock-map", "ls-files", "*lockfile", finalizing=True).text().splitlines()
            require(len(runtime.lockfiles) == len(set(runtime.lockfiles)) == 12, "recovery twelve-lock inventory incomplete")
    runtime.safely("recovery-originals", original_records)
    attempted = (runtime.commands / "writer/launch-attempt.json").exists()
    runtime.report["interruptedProductAttempted"] = attempted

    def cleanup_stop():
        saved = parse(read(state / "execution-environment.json"))
        require(saved["binding"] == binding and saved["job"] == runtime.job, "recovery execution binding differs")
        runtime.env, runtime.jvm = saved["environment"], saved["jvmArguments"]
        # A new cleanup ID is explicitly NOT the reserved original stop ID.
        stop = Command(runtime, "recovery-stop", [str(root / "gradlew"), "--stop", "--console=plain", "--no-parallel",
            "--max-workers=2", "-Dorg.gradle.jvmargs=" + runtime.jvm], STOP_SECONDS)
        try:
            require(stop.wait(True) == 0, "recovery same-home stop failed")
        finally:
            runtime.safely("recovery-stop-drain", lambda: stop.drain("recovery-stop-final"))
            runtime.safely("recovery-stop-close", stop.close)
            recovery["recoveryStop"] = stop.row
    if attempted:
        runtime.safely("recovery-stop", cleanup_stop)

    def simulator():
        path = original_evidence / "simulator-before.json"
        if path.exists():
            runtime.simulator = parse(read(path))
            runtime.retire_simulator()
            recovery["simulatorRetirement"] = runtime.report.get("simulatorRetirement")
    runtime.safely("recovery-simulator", simulator)
    runtime.custody_attempted = (state / "custody-attempted").exists() or (state / "custody").exists()
    runtime.safely("recovery-custody", runtime.collect_custody)
    runtime.safely("recovery-retention", runtime.retain)
    recovery["transcriptCustody"] = runtime.report.get("transcriptCustody")
    recovery["sourceAfter"] = runtime.report.get("sourceAfter")
    record(original_evidence / "interrupted-owner.json", recovery)
    # A second observation is necessary for the NEW recovery helpers/stop, not
    # a replacement or repetition claimed as original successful finalization.
    quiesce(state, context, "recovery-final-quiescence")


def seal(root, binding):
    state, output = paths(binding)
    physical(state, directory=True)
    fd = acquire(state)
    try:
        # No successful result is invented if the earlier step was terminated.
        # Recovery scopes below retire only marker-inheriting descendants of the
        # recorded job/state/home; original command/custody results stay untouched.
        context = parse(read(state / "context.json"))
        require(context["binding"] == binding and context["root"] == str(root) and context["stateIdentity"] == identity(state),
                "seal source/run/state binding differs")
        require(context["gradleHomeIdentity"] == identity(state / "gradle-home"), "owned Gradle home was replaced")
        recovered = quiesce(state, context)
        interrupted = not (state / "evidence/result.json").exists() and not (state / "evidence/bootstrap-failure.json").exists()
        if interrupted:
            recover_interrupted(root, state, binding, context)
        # Include the original source/run/acquisition plan without environment secrets.
        write(state / "evidence/controller-context.json", read(state / "context.json"))
        work = state / "recipient-seal"
        work.mkdir(mode=0o700)
        recipient = hosted_evidence.validate_recipient(state / "recipient.asc", binding["recipientFingerprint"], work)
        output.parent.mkdir(mode=0o700)
        manifest = hosted_evidence.export_encrypted(state / "evidence", output, recipient, source_commit=binding["commit"],
            source_tree=binding["tree"], run_id=binding["runId"], run_attempt=binding["runAttempt"])
        record(state / "sealed.json", {"binding": binding, "manifestSha256": digest(output / "manifest.json"),
            "recipientFingerprint": recipient.fingerprint, "encryptionFingerprint": recipient.encryption_fingerprint,
            "artifact": manifest["artifact"], "scope": "ENCRYPTED_CUSTODY_NOT_ACCEPTANCE"})
        return 125 if recovered or interrupted else 0
    finally:
        os.close(fd)


def validate_public(binding):
    state, output = paths(binding)
    physical(output, directory=True)
    require({p.name for p in output.parent.iterdir()} == {"encrypted"}, "unexpected public export content")
    require(stat.S_IMODE(output.stat().st_mode) == 0o700 and {p.name for p in output.iterdir()} == {"evidence.tar.gz.gpg", "manifest.json"},
            "ciphertext-only export directory required")
    manifest = parse(read(output / "manifest.json", MIB))
    sealed = parse(read(state / "sealed.json", MIB))
    require(sealed["binding"] == binding and sealed["recipientFingerprint"] == binding["recipientFingerprint"] and
            sealed["manifestSha256"] == digest(output / "manifest.json") and sealed["artifact"] == manifest.get("artifact"),
            "successful exact recipient seal is required")
    # The encryption module's format is also checked by its own offline controls.
    require(set(manifest) == {"schema", "scope", "source", "github", "artifact"} and manifest["schema"] == 1 and
            manifest["scope"] == "ENCRYPTED_PRIVATE_TEST_EVIDENCE" and
            manifest["source"] == {"commit": binding["commit"], "tree": binding["tree"]} and
            manifest["github"] == {"repository": "p2pKit/P2pKit", "runId": binding["runId"], "runAttempt": binding["runAttempt"]},
            "ciphertext manifest source/run mismatch")
    artifact = output / "evidence.tar.gz.gpg"
    info = artifact.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= 576 * MIB and
            manifest["artifact"] == {"name": artifact.name, "size": info.st_size, "sha256": digest(artifact)}, "ciphertext hash mismatch")
    hosted_evidence._ciphertext_shape(artifact, sealed["encryptionFingerprint"])
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        stream.write("artifacts_ready=true\n")
    return 0


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "seal", "validate-public"))
    args = parser.parse_args(argv)
    root = SCRIPTS.parent
    binding = dispatch(dict(os.environ), root)
    require(processes.host_role() == native_profile(binding["operation"])["hostRole"], "selected native Mac role required")
    if args.action == "run":
        return run(root, binding)
    if args.action == "seal":
        return seal(root, binding)
    return validate_public(binding)


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        # No exception/raw child output belongs in public Actions logs.
        print("RESULT: HOLD — no accepted lock candidate; private evidence/failure retained when available", file=sys.stderr)
        code = 125
    else:
        print("RESULT: controller stage completed" if code == 0 else "RESULT: HOLD — inspect encrypted evidence")
    raise SystemExit(code)
