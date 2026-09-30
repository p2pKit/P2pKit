#!/usr/bin/env python3
"""Four fixed synthetic native controls for the maintained dependency bridge.

This is not a build, dependency generator, cache admission or release gate.
The original foreground alone retains its Recipient and command-file handle.
Q3/Q4 must be real production refusals; missing D returns stay missing.
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
import select
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SCRIPT = "scripts/run-hosted-dependency-context-qualification.py"
WORKFLOW = ".github/workflows/dependency-update-context-qualification.yml"
REPOSITORY = "p2pKit/P2pKit"
OWNER, OWNER_ID = "Apdelrahman1911", "104788132"
SCOPE = "MANUAL_DEPENDENCY_CONTEXT_QUALIFICATION_V1"
RESULT = "FOUR_FIXED_SYNTHETIC_NATIVE_CONTROLS_PASSED"
CASES = ("Q1", "Q2", "Q3", "Q4")
REQUEST_KEYS = frozenset(("source_sha", "source_tree"))
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
INVOCATION = re.compile(r"[0-9a-f]{32}\Z")
NUMBER = re.compile(r"[1-9][0-9]{0,19}\Z")
REF = re.compile(r"refs/heads/work/release-foundation-dependency-context-[A-Za-z0-9-]+\Z")
PREFIX = "P2PKIT_DEPENDENCY_CONTEXT_"
CLOCK_SCHEMA = 2
CLOCK_DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"
NS, MIB = 1_000_000_000, 1024 * 1024
JOB_SECONDS, STEP_SECONDS = 2460, 1740
PREPARE_SECONDS, FIXTURE_SECONDS, SUITE_SECONDS, CASE_SECONDS = 120, 120, 1200, 300
ABORT_SECONDS, FREEZE_SECONDS, EXPORT_SECONDS, UPLOAD_SECONDS = 120, 60, 120, 420
PRODUCT_SECONDS, STOP_SECONDS, READY_SECONDS, ADMIN_SECONDS = 20, 5, 15, 10
FRAME_BYTES, STREAM_BYTES = 16384, 65536
EVIDENCE_BYTES, EVIDENCE_MEMBERS, CIPHERTEXT_BYTES = 512 * MIB, 10000, 576 * MIB
POLICY_PATH = ".github/test-evidence-recipient.json"
POLICY_SHA256 = "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521"
KEY_SHA256 = "5dcb108725ffb2a9c99f4e61e35c3473d34776530effca7385282faf62b86aaf"
FINGERPRINT = "0A996D2BC19518FB50071A95D3FDADA57CFB7E1F"
ENCRYPTION_FINGERPRINT = "4D7CF63A16AFC0BDDC82F3E686D7D3D9A7B44350"
KEY_EXPIRES = 1821484800
POLICY_EXPIRES, LATEST_ENTRY = 1791158400, 1791145800
OWNER_ENV = ("P2PKIT_AUDIT_JOB_ID", "P2PKIT_AUDIT_OWNERSHIP_CHAIN", "P2PKIT_AUDIT_OWNERSHIP_DOMAINS",
             "P2PKIT_AUDIT_STATE_DIR", "GRADLE_USER_HOME")
JVM_ARGUMENTS = "-Xmx2048m -XX:MaxMetaspaceSize=768m -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8"
CANCELLATION_ERRORS = ["AuditError: Invocation cancellation requested",
                       "Invocation cancellation cannot be a successful product result"]


def module(name, relative):
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


bridge = module("hosted_dependency_update_context", "scripts/hosted_dependency_update_context.py")
encoded, parsed = bridge.encoded, bridge.parsed
digest, read_file, write_new = bridge.digest, bridge.read_file, bridge.write_new
physical, private_directory = bridge.physical, bridge.private_directory
shared_raw_ns = bridge.shared_raw_ns


class QualificationError(RuntimeError):
    """Only source-defined non-secret reason codes can reach public output."""


def require(value, reason):
    if not value:
        raise QualificationError(reason)


def integer(value, low=1, high=(1 << 64) - 1):
    return type(value) is int and low <= value <= high


def left(end_ns):
    remaining = end_ns - shared_raw_ns()
    require(remaining > 0, "ORIGINAL_DEADLINE")
    return remaining / NS


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


def child_environment(parent):
    require(not any(key in os.environ for key in OWNER_ENV), "ENCLOSING_OWNER")
    return {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(parent / "home"),
            "TMPDIR": str(parent / "tmp"), "LANG": "C", "LC_ALL": "C", "TZ": "UTC",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
            "__CF_USER_TEXT_ENCODING": f"0x{os.getuid():X}:0:0",
            "DEVELOPER_DIR": "/Applications/Xcode_26.5.app/Contents/Developer",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}


def validate_request(request, env, event_inputs):
    require(type(request) is dict and set(request) == REQUEST_KEYS and
            all(type(value) is str and SHA.fullmatch(value) for value in request.values()), "REQUEST_FIELDS")
    require(type(event_inputs) is dict and event_inputs == request, "REQUEST_EVENT")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPOSITORY and
            env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            env.get("GITHUB_JOB") == "dependency_context_qualification" and env.get("GITHUB_ACTOR") == OWNER and
            env.get("GITHUB_ACTOR_ID") == OWNER_ID and env.get("GITHUB_TRIGGERING_ACTOR") == OWNER,
            "MANUAL_IDENTITY")
    ref = env.get("GITHUB_REF", "")
    require(type(ref) is str and REF.fullmatch(ref) and
            env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA") == request["source_sha"] and
            env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@" + ref, "SOURCE_IDENTITY")
    require(all(type(env.get(key)) is str and NUMBER.fullmatch(env[key])
                for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")), "RUN_IDENTITY")
    require(not any(key in env for key in OWNER_ENV), "ENCLOSING_OWNER")
    return {"repository": REPOSITORY, "workflow": WORKFLOW, "job": "dependency_context_qualification", "ref": ref,
            "source": request["source_sha"], "sourceTree": request["source_tree"],
            "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"],
            "actor": OWNER, "actorId": OWNER_ID, "triggeringActor": OWNER}


def original_request(env):
    raw = env.get(PREFIX + "REQUEST", "")
    require(type(raw) is str and 0 < len(raw.encode("utf-8")) <= FRAME_BYTES, "REQUEST_BOUND")
    request = parsed(raw.encode("utf-8"))
    event = parsed(read_file(physical(env["GITHUB_EVENT_PATH"]), 2 * MIB), 2 * MIB)
    require(type(event) is dict and type(event.get("inputs")) is dict, "REQUEST_EVENT")
    return request, validate_request(request, env, event["inputs"])


def validate_allocation(allocation, request, github, now_ns, wall_ns):
    keys = {"schema", "clockDomain", "scope", "source", "sourceTree", "runId", "runAttempt",
            "startedMonotonicNs", "startedEpochNs"}
    require(type(allocation) is dict and set(allocation) == keys and type(allocation["schema"]) is int and
            allocation["schema"] == CLOCK_SCHEMA and allocation["clockDomain"] == CLOCK_DOMAIN and
            allocation["scope"] == SCOPE and allocation["source"] == request["source_sha"] and
            allocation["sourceTree"] == request["source_tree"] and allocation["runId"] == github["runId"] and
            allocation["runAttempt"] == github["runAttempt"], "ALLOCATION_IDENTITY")
    require(all(integer(value) for value in (now_ns, wall_ns, allocation["startedMonotonicNs"],
                                            allocation["startedEpochNs"])), "ALLOCATION_CLOCK")
    elapsed = now_ns - allocation["startedMonotonicNs"]
    require(0 <= elapsed < JOB_SECONDS * NS and
            abs(wall_ns - allocation["startedEpochNs"] - elapsed) <= 60 * NS, "ALLOCATION_DEADLINE")
    return allocation["startedMonotonicNs"] + JOB_SECONDS * NS


def operation_paths(env):
    require(sys.platform == "darwin" and platform.machine() == "arm64" and
            env.get("RUNNER_OS") == "macOS" and env.get("RUNNER_ARCH") == "ARM64", "NATIVE_HOST")
    operation = physical(env[PREFIX + "OPERATION"])
    require(operation.parent == physical(env["RUNNER_TEMP"]) and
            re.fullmatch(r"p2pkit-dependency-context-[A-Za-z0-9_-]+", operation.name) and
            ROOT not in operation.parents and operation not in ROOT.parents, "OPERATION_PATH")
    return operation, private_directory(operation)


def validate_policy(raw, now, reserve):
    require(digest(raw) == POLICY_SHA256 and type(now) in (int, float) and math.isfinite(now) and
            integer(reserve, 0, JOB_SECONDS), "OWNER_POLICY_PIN")
    value = parsed(raw, 96 * 1024)
    require(type(value) is dict and set(value) == {"schema", "repository", "purpose", "retrievalOwner",
            "retentionDays", "notBefore", "expiresAt", "recipient"} and type(value["schema"]) is int and
            value["schema"] == 1 and value["repository"] == REPOSITORY and
            value["purpose"] == "P2PKIT_TEST_TRANSCRIPTS" and value["retrievalOwner"] == OWNER and
            type(value["retentionDays"]) is int and value["retentionDays"] == 14 and
            integer(value["notBefore"]) and type(value["expiresAt"]) is int and
            value["expiresAt"] == POLICY_EXPIRES and value["expiresAt"] - value["notBefore"] == 14 * 86400 and
            value["notBefore"] <= now and now + reserve < POLICY_EXPIRES, "OWNER_POLICY_WINDOW")
    key = value["recipient"]
    require(type(key) is dict and set(key) == {"publicKey", "fingerprint", "sha256"} and
            type(key["publicKey"]) is str and key["fingerprint"] == FINGERPRINT and key["sha256"] == KEY_SHA256 and
            digest(key["publicKey"].encode("ascii")) == KEY_SHA256, "OWNER_PUBLIC_KEY")
    return value


def file_pin(path, maximum, end_ns, *, owners=None, executable=False):
    path = physical(str(path))
    allowed = (os.getuid(),) if owners is None else owners
    left(end_ns)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid in allowed and before.st_nlink == 1 and
                not before.st_mode & 0o022 and 0 <= before.st_size <= maximum and
                (not executable or before.st_mode & 0o111), "FILE_PIN")
        hasher, size = hashlib.sha256(), 0
        while True:
            left(end_ns)
            raw = stream.read(min(MIB, maximum + 1 - size))
            if not raw:
                break
            size += len(raw)
            require(size <= maximum, "FILE_BOUND")
            hasher.update(raw)
        def stamp(info):
            return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink,
                    info.st_size, info.st_mtime_ns, info.st_ctime_ns]
        require(size == before.st_size and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()),
                "FILE_CHANGED")
    return {"path": str(path), "stat": stamp(before), "size": size, "sha256": hasher.hexdigest()}


class CommandFile:
    """One original F command-file descriptor; never passed to shared/D/P."""

    def __init__(self, env):
        self.path = physical(env["GITHUB_OUTPUT"])
        require(physical(env["RUNNER_TEMP"]) in self.path.parents and ROOT not in self.path.parents, "OUTPUT_PATH")
        self.fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        self.closed, self.emitted = False, False
        self.stamp = self._stamp(os.fstat(self.fd))
        require(self.stamp == self._stamp(self.path.lstat()) and self.stamp[6] == 0, "OUTPUT_IDENTITY")

    @staticmethod
    def _stamp(info):
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
                not info.st_mode & 0o022 and 0 <= info.st_size <= STREAM_BYTES, "OUTPUT_FILE")
        return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink,
                info.st_size, info.st_mtime_ns, info.st_ctime_ns]

    def emit(self, values):
        require(not self.closed and not self.emitted and type(values) is dict and
                set(values) in ({"qualificationSha256"}, {"uploadAllowed"}) and
                all(type(value) is str and HASH.fullmatch(value) for value in values.values()) and
                str(self.path) == os.environ.get("GITHUB_OUTPUT") and
                self.stamp == self._stamp(os.fstat(self.fd)) == self._stamp(self.path.lstat()), "OUTPUT_BINDING")
        raw = "".join(key + "=" + value + "\n" for key, value in values.items()).encode("ascii")
        require(os.write(self.fd, raw) == len(raw), "OUTPUT_SHORT")
        os.fsync(self.fd)
        after = self._stamp(os.fstat(self.fd))
        require(after == self._stamp(self.path.lstat()) and after[:6] == self.stamp[:6] and
                after[6] == len(raw) and read_file(self.path) == raw, "OUTPUT_CHANGED")
        self.emitted = True
        self.close()
        return {"stat": after, "sha256": digest(raw), "closed": self.closed}

    def close(self):
        if not self.closed:
            os.close(self.fd)
            self.closed = True


# This literal, not a test-suite import or an environment mode, is the only
# synthetic canonical workload. It cannot spawn children, contact a network,
# choose a command, run Java/Gradle, or enter the productive generation profile.
FIXTURE = r'''#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time

SCOPE = "MANUAL_DEPENDENCY_CONTEXT_QUALIFICATION_V1"
CASES = ("Q1", "Q2", "Q3", "Q4")
JVM = "-Xmx2048m -XX:MaxMetaspaceSize=768m -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8"

def require(value):
    if not value:
        raise ValueError("FIXTURE_REFUSED")

def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")

def parsed(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result
    require(type(raw) is bytes and 0 < len(raw) <= 16384)
    value = json.loads(raw, object_pairs_hook=unique, parse_float=lambda _: require(False),
                       parse_constant=lambda _: require(False))
    pending, nodes = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        require(nodes <= 4096 and depth <= 32)
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        else:
            require(item is None or type(item) in (str, int, bool))
    return value

def integer(value, low=0, high=(1 << 64) - 1):
    return type(value) is int and low <= value <= high

def shape(value, keys):
    return type(value) is dict and set(value) == set(keys.split())

def hexadecimal(value, length):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value)

def identity(value):
    require(shape(value, "pid parentPid uniqueId parentUniqueId pidVersion startSeconds startMicroseconds uid realUid gid realGid status") and
            all(integer(item) for item in value.values()) and value["pid"] > 0 and value["uniqueId"] > 0 and
            value["status"] in (1, 2, 3, 4))

def validate_account(value):
    require(shape(value, "uid euid gid egid groups") and
            all(integer(value[key], 0, (1 << 32) - 1) for key in ("uid", "euid", "gid", "egid")) and
            value["uid"] == value["euid"] != 0 and value["gid"] == value["egid"] and
            type(value["groups"]) is list and len(value["groups"]) <= 256 and
            all(integer(item, 0, (1 << 32) - 1) for item in value["groups"]) and
            value["groups"] == sorted(set(value["groups"])))

def physical(value):
    path = Path(value)
    require(path.is_absolute() and str(path) == value and not value.startswith("//") and ".." not in path.parts)
    require(all(not part.is_symlink() for part in (path, *path.parents)))
    return path

def read_file(path):
    path = physical(str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1 and
                not before.st_mode & 0o022 and 0 < before.st_size <= 16384)
        raw = source.read(16385)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(len(raw) == before.st_size and stamp(before) == stamp(os.fstat(source.fileno())) == stamp(path.lstat()))
    return raw

def write_new(path, value):
    path = physical(str(path))
    raw = encoded(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output:
        require(output.write(raw) == len(raw))
        output.flush()
        os.fsync(output.fileno())
    require(read_file(path) == raw)

def now():
    require(sys.platform == "darwin" and callable(getattr(time, "clock_gettime_ns", None)) and
            type(getattr(time, "CLOCK_MONOTONIC_RAW", None)) is int)
    value = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
    require(type(value) is int and 0 < value < 2 ** 64)
    return value

def account():
    value = dict(uid=os.getuid(), euid=os.geteuid(), gid=os.getgid(), egid=os.getegid(), groups=sorted(set(os.getgroups())))
    validate_account(value)
    return value

def main():
    os.umask(0o077)
    state = physical(os.environ["P2PKIT_AUDIT_STATE_DIR"])
    case, operation = state.name, state.parent.parent
    require(case in CASES and state.parent.name == "states")
    root = physical(str(Path(__file__).parent))
    require(root == operation / "fixture" and physical(os.getcwd()) == root)
    directory = operation / "bridge" / "cases" / case
    info = directory.lstat()
    require(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700 and info.st_uid == os.getuid())
    inputs_raw, entry_raw, context_raw = (read_file(directory / "case-input.json"),
                                         read_file(directory / "canonical-entry.json"), read_file(state / "context.json"))
    inputs, entry, context = parsed(inputs_raw), parsed(entry_raw), parsed(context_raw)
    require(shape(inputs, "schema scope case binding github allocationSha256 repositorySource fixtureSourceSha256 caseDirectoryIdentity foreground account caseStartNs caseEndNs") and
            integer(inputs["schema"], 1, 1) and inputs["scope"] == SCOPE and inputs["case"] == case and
            inputs_raw == encoded(inputs) and hexadecimal(inputs["binding"], 64) and
            hexadecimal(inputs["allocationSha256"], 64) and hexadecimal(inputs["fixtureSourceSha256"], 64) and
            inputs["fixtureSourceSha256"] == hashlib.sha256(read_file(operation / "fixture-source.json")).hexdigest() and
            type(inputs["caseDirectoryIdentity"]) is list and len(inputs["caseDirectoryIdentity"]) == 2 and
            all(integer(item) for item in inputs["caseDirectoryIdentity"]) and
            inputs["caseDirectoryIdentity"] == [info.st_dev, info.st_ino] and
            integer(inputs["caseStartNs"], 1) and integer(inputs["caseEndNs"], 1) and
            inputs["caseStartNs"] <= now() < inputs["caseEndNs"] <= inputs["caseStartNs"] + 300 * 1000000000)
    validate_account(inputs["account"])
    identity(inputs["foreground"])
    require(inputs["account"] == account())
    repository, github = inputs["repositorySource"], inputs["github"]
    require(shape(repository, "commit tree") and all(hexadecimal(value, 40) for value in repository.values()) and
            shape(github, "repository workflow job ref source sourceTree runId runAttempt actor actorId triggeringActor") and
            all(type(value) is str for value in github.values()) and github["repository"] == "p2pKit/P2pKit" and
            github["workflow"] == ".github/workflows/dependency-update-context-qualification.yml" and
            github["job"] == "dependency_context_qualification" and
            re.fullmatch(r"refs/heads/work/release-foundation-dependency-context-[A-Za-z0-9-]+", github["ref"]) and
            github["source"] == repository["commit"] and github["sourceTree"] == repository["tree"] and
            all(re.fullmatch(r"[1-9][0-9]{0,19}", github[key]) for key in ("runId", "runAttempt")) and
            github["actor"] == github["triggeringActor"] == "Apdelrahman1911" and github["actorId"] == "104788132")
    require(shape(context, "schema root expectedCommit tree source host gradleHome createdUtc id gradlePropertiesSha256 javaHomes preexistingOutputPaths") and
            integer(context["schema"], 1, 1) and context["root"] == str(root) and context["host"] == "macos-arm64" and
            context["gradleHome"] == str(state / "gradle-home") and hexadecimal(context["id"], 32) and
            hexadecimal(context["gradlePropertiesSha256"], 64) and hexadecimal(context["expectedCommit"], 40) and
            hexadecimal(context["tree"], 40) and context["javaHomes"] == [] and context["preexistingOutputPaths"] == [] and
            type(context["createdUtc"]) is str and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00", context["createdUtc"]) and
            context["source"] == dict(commit=context["expectedCommit"], tree=context["tree"], status="", diffSha256=hashlib.sha256(b"").hexdigest()))
    require(shape(entry, "schema scope case binding caseInputSha256 contextSha256 contextId invocationId fixtureSourceCommit fixtureSourceTree gradlePolicySha256 producerIdentity enteredMonotonicNs") and
            entry_raw == encoded(entry) and integer(entry["schema"], 1, 1) and entry["scope"] == SCOPE and
            entry["case"] == case and entry["binding"] == inputs["binding"] and
            entry["caseInputSha256"] == hashlib.sha256(inputs_raw).hexdigest() and
            entry["contextSha256"] == hashlib.sha256(context_raw).hexdigest() and
            entry["contextId"] == context["id"] and entry["fixtureSourceCommit"] == context["expectedCommit"] and
            entry["fixtureSourceTree"] == context["tree"] and integer(entry["enteredMonotonicNs"], 1) and
            inputs["caseStartNs"] <= entry["enteredMonotonicNs"] <= now() and
            entry["gradlePolicySha256"] == context["gradlePropertiesSha256"] and
            hashlib.sha256(read_file(state / "gradle-home" / "gradle.properties")).hexdigest() == context["gradlePropertiesSha256"])
    identity(entry["producerIdentity"])
    invocation = entry["invocationId"]
    require(hexadecimal(invocation, 32))
    domains = parsed(os.environ["P2PKIT_AUDIT_OWNERSHIP_DOMAINS"].encode("ascii"))
    expected_domain = dict(id=invocation, job=context["id"], state=str(state), home=str(state / "gradle-home"))
    require(os.environ["P2PKIT_AUDIT_JOB_ID"] == context["id"] and
            os.environ["P2PKIT_AUDIT_OWNERSHIP_CHAIN"] == invocation and domains == [expected_domain] and
            os.environ["GRADLE_USER_HOME"] == str(state / "gradle-home"))
    ownership = dict(jobId=context["id"], chain=invocation, domains=domains, state=str(state), home=str(state / "gradle-home"))
    if sys.argv[1:] == ["--stop", "--console=plain", "--no-parallel", "--max-workers=2", "-Dorg.gradle.jvmargs=" + JVM]:
        write_new(state / "stop-observation.json", dict(schema=1, scope=SCOPE, case=case, binding=inputs["binding"],
            contextId=context["id"], invocationId=invocation, pid=os.getpid(), parentPid=os.getppid(), account=account(),
            ownership=ownership, argv=sys.argv[1:], observedRawNs=now()))
        print("FIXTURE_STOP_CLOSED", flush=True)
        print("FIXTURE_STOP_CAPTURE", file=sys.stderr, flush=True)
        return 0
    require(sys.argv[1:] == ["--product", case])
    default = signal.getsignal(signal.SIGTERM) == signal.SIG_DFL
    blocked = signal.SIGTERM in signal.pthread_sigmask(signal.SIG_BLOCK, [])
    require(default and not blocked and os.getppid() == entry["producerIdentity"]["pid"])
    ready = dict(schema=1, scope=SCOPE, case=case, binding=inputs["binding"], contextId=context["id"],
        invocationId=invocation, pid=os.getpid(), parentPid=os.getppid(), account=account(), ownership=ownership,
        sourceSha256=hashlib.sha256(read_file(physical(str(Path(__file__))))).hexdigest(),
        sigtermDefault=default, sigtermBlocked=blocked, readyMonotonicNs=now())
    ready_raw = encoded(ready)
    print("FIXTURE_PRODUCT_ACTIVE", flush=True)
    print("FIXTURE_PRODUCT_CAPTURE", file=sys.stderr, flush=True)
    write_new(directory / "product-ready.json", ready)
    release_path = directory / "product-release.json"
    while now() < inputs["caseEndNs"]:
        if os.path.lexists(release_path):
            require(case in ("Q1", "Q2"))
            release = parsed(read_file(release_path))
            require(type(release) is dict and set(release) == {"schema", "scope", "case", "binding", "readySha256", "releasedMonotonicNs"} and
                    type(release["schema"]) is int and release["schema"] == 1 and release["scope"] == SCOPE and
                    release["case"] == case and release["binding"] == inputs["binding"] and
                    release["readySha256"] == hashlib.sha256(ready_raw).hexdigest() and
                    type(release["releasedMonotonicNs"]) is int and
                    ready["readyMonotonicNs"] <= release["releasedMonotonicNs"] <= now())
            return 0 if case == "Q1" else 23
        time.sleep(0.01)
    return 124

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("FIXTURE_REFUSED", file=sys.stderr)
        raise SystemExit(125)
'''


# A failed/unknown original Git pipe or wait is retained and blocks all export.
# This list is not a cleanup capability and never grants successful closure.
_UNCLOSED_GIT = []


def git_capture(root, arguments, end_ns, env, *, empty=None):
    """Only the fixed Git call sites below; no CLI, callback or inherited config."""
    require(type(arguments) is tuple and arguments and
            all(type(value) is str and "\0" not in value for value in arguments), "GIT_ARGUMENTS")
    argv = ["/usr/bin/git", "--no-replace-objects", "--no-optional-locks", "-c", "core.autocrlf=false",
            "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", "-c", "gc.auto=0",
            "-c", "maintenance.auto=false"]
    if empty is not None:
        private_directory(empty, empty=True)
        argv += ["-c", "core.hooksPath=" + str(empty)]
    argv += ["-C", str(physical(root)), *arguments]
    end = min(end_ns, shared_raw_ns() + ADMIN_SECONDS * NS)
    left(end)
    started = shared_raw_ns()
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=env, close_fds=True)
    streams, buffers, eof = [process.stdout, process.stderr], [bytearray(), bytearray()], [False, False]
    try:
        process.stdin.close()
        for stream in streams:
            os.set_blocking(stream.fileno(), False)
        while not all(eof):
            readable, _, _ = select.select([stream for index, stream in enumerate(streams) if not eof[index]],
                                           [], [], min(0.05, left(end)))
            for stream in readable:
                index = streams.index(stream)
                raw = os.read(stream.fileno(), STREAM_BYTES)
                if raw:
                    buffers[index].extend(raw)
                    require(len(buffers[index]) <= STREAM_BYTES, "GIT_CAPTURE_BOUND")
                else:
                    eof[index] = True
        code = process.wait(timeout=left(end))
        for stream in streams:
            stream.close()
        require(process.stdin.closed and all(stream.closed for stream in streams), "GIT_CAPTURE_CLOSE")
        returned = shared_raw_ns()
        left(end)
    except BaseException:
        # An external timeout alone is not a known wait/EOF/close. No subsequent
        # fixture, case, seal or upload is admitted after this sticky failure.
        _UNCLOSED_GIT.append((process, streams))
        raise
    result = {"argv": argv, "code": code, "stdout": bytes(buffers[0]), "stderr": bytes(buffers[1]),
              "startedRawNs": started, "returnedRawNs": returned, "waitReturned": True,
              "stdinClosed": process.stdin.closed, "stdoutEof": eof[0], "stderrEof": eof[1],
              "stdoutClosed": streams[0].closed, "stderrClosed": streams[1].closed}
    require(type(code) is int and code == 0, "GIT_RETURN")
    return result


def git_stdout(root, arguments, end_ns, env, *, empty=None, records=None):
    value = git_capture(root, arguments, end_ns, env, empty=empty)
    if records is not None:
        records.append({**{key: item for key, item in value.items() if key not in ("stdout", "stderr")},
                        "stdoutHex": value["stdout"].hex(), "stderrHex": value["stderr"].hex()})
    return value["stdout"]


def source_snapshot(root, end_ns, env, *, empty=None, records=None):
    def git(*arguments):
        return git_stdout(root, arguments, end_ns, env, empty=empty, records=records)
    commit = git("rev-parse", "HEAD").decode("ascii").strip()
    tree = git("rev-parse", "HEAD^{tree}").decode("ascii").strip()
    status = git("status", "--porcelain=v1", "--untracked-files=all").decode("utf-8")
    diff = git("diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames")
    require(SHA.fullmatch(commit) and SHA.fullmatch(tree) and status == "" and diff == b"", "SOURCE_CLEAN")
    return {"commit": commit, "tree": tree, "status": status, "diffSha256": digest(diff)}


def repository_source(request, end_ns, env):
    value = source_snapshot(ROOT, end_ns, env)
    require(value["commit"] == request["source_sha"] and value["tree"] == request["source_tree"], "CHECKOUT_IDENTITY")
    require(git_stdout(ROOT, ("remote", "get-url", "origin"), end_ns, env).strip() in
            (b"https://github.com/p2pKit/P2pKit", b"https://github.com/p2pKit/P2pKit.git"), "CHECKOUT_ORIGIN")
    config = git_stdout(ROOT, ("config", "--local", "--list"), end_ns, env).lower()
    require(b"extraheader=" not in config and b"credential." not in config, "CHECKOUT_CREDENTIALS")
    return value


def fixture_bytes(interpreter):
    path = interpreter["path"]
    require(type(path) is str and str(physical(path)) == path, "FIXTURE_INTERPRETER")
    wrapper = ('#!/bin/sh\nexec ' + shlex.quote(path) + ' -I -B -S "${0%/*}/fixture.py" "$@"\n').encode("ascii")
    return {"fixture.py": FIXTURE.encode("ascii"), "gradlew": wrapper}


def fixture_roster(root, interpreter, end_ns, env, empty, records=None):
    private_directory(root)
    require({path.name for path in root.iterdir()} == {"fixture.py", "gradlew", ".git"}, "FIXTURE_PATH_ROSTER")
    private_directory(root / ".git")
    expected = fixture_bytes(interpreter)
    tracked = git_stdout(root, ("ls-files", "--stage", "-z"), end_ns, env, empty=empty, records=records)
    roster = {}
    for item in tracked.split(b"\0"):
        if not item:
            continue
        metadata, raw_name = item.split(b"\t", 1)
        mode, blob, stage = metadata.decode("ascii").split(" ")
        name = raw_name.decode("ascii")
        require(name in expected and name not in roster and stage == "0" and SHA.fullmatch(blob) and
                mode == ("100755" if name == "gradlew" else "100644"), "FIXTURE_TRACKED_ROSTER")
        data = read_file(root / name, FRAME_BYTES)
        info = (root / name).lstat()
        require(data == expected[name] and stat.S_IMODE(info.st_mode) == (0o755 if name == "gradlew" else 0o644),
                "FIXTURE_SOURCE_BYTES")
        roster[name] = {"mode": mode, "bytes": len(data), "sha256": digest(data)}
    require(set(roster) == set(expected) and
            git_stdout(root, ("remote",), end_ns, env, empty=empty, records=records) == b"" and
            git_stdout(root, ("tag", "--list"), end_ns, env, empty=empty, records=records) == b"",
            "FIXTURE_NO_REMOTE_OR_TAG")
    return roster


def prepare_fixture(context):
    end = min(shared_raw_ns() + FIXTURE_SECONDS * NS,
              context.step_end - (SUITE_SECONDS + ABORT_SECONDS + FREEZE_SECONDS + EXPORT_SECONDS) * NS,
              context.job_end, context.policy_end)
    left(end)
    root, empty = context.operation / "fixture", context.operation / "git-empty"
    root.mkdir(mode=0o700)
    empty.mkdir(mode=0o700)
    (context.operation / "states").mkdir(mode=0o700)
    env = {**context.environment, "GIT_AUTHOR_NAME": "Audit Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "Audit Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
           "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
           "GIT_ATTR_NOSYSTEM": "1", "GIT_DEFAULT_HASH": "sha1"}
    records = []
    for name, raw in fixture_bytes(context.interpreter).items():
        write_new(root / name, raw)
        os.chmod(root / name, 0o755 if name == "gradlew" else 0o644, follow_symlinks=False)
    for arguments in (("init", "--quiet", "--object-format=sha1", "--template=" + str(empty)),
                      ("add", "--", "fixture.py", "gradlew"),
                      ("commit", "--quiet", "--no-gpg-sign", "-m", "Synthetic dependency context fixture")):
        git_stdout(root, arguments, end, env, empty=empty, records=records)
    source = source_snapshot(root, end, env, empty=empty, records=records)
    roster = fixture_roster(root, context.interpreter, end, env, empty, records)
    setup_raw = encoded({"schema": 1, "scope": SCOPE, "syntheticIdentity": "Audit Fixture <fixture@example.invalid>",
                         "returns": records, "result": "ORIGINAL_GIT_RETURNS_CLOSED"})
    write_new(context.operation / "fixture-setup-returns.json", setup_raw)
    record = {"schema": 1, "scope": SCOPE, "sourceCommit": source["commit"], "sourceTree": source["tree"],
              "sourceFiles": roster, "repositorySourceCommit": context.request["source_sha"],
              "repositorySourceTree": context.request["source_tree"],
              "interpreterSha256": context.interpreter["sha256"], "setupReturnsSha256": digest(setup_raw)}
    write_new(context.operation / "fixture-source.json", encoded(record))
    context.fixture, context.fixture_source, context.fixture_environment = root, record, env
    context.fixture_source_raw, context.fixture_empty = encoded(record), empty
    left(end)
    return record


def fixture_binding(operation, repository, interpreter):
    raw = read_file(operation / "fixture-source.json", STREAM_BYTES)
    value = parsed(raw, STREAM_BYTES)
    keys = {"schema", "scope", "sourceCommit", "sourceTree", "sourceFiles", "repositorySourceCommit",
            "repositorySourceTree", "interpreterSha256", "setupReturnsSha256"}
    require(raw == encoded(value) and type(value) is dict and set(value) == keys and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == SCOPE and SHA.fullmatch(value["sourceCommit"]) and
            SHA.fullmatch(value["sourceTree"]) and value["repositorySourceCommit"] == repository["commit"] and
            value["repositorySourceTree"] == repository["tree"] and
            value["interpreterSha256"] == interpreter["sha256"] and
            digest(read_file(operation / "fixture-setup-returns.json", 4 * MIB)) == value["setupReturnsSha256"],
            "FIXTURE_BINDING")
    expected = fixture_bytes(interpreter)
    require(type(value["sourceFiles"]) is dict and set(value["sourceFiles"]) == set(expected), "FIXTURE_SOURCE_ROSTER")
    for name, expected_raw in expected.items():
        require(value["sourceFiles"][name] == {"mode": "100755" if name == "gradlew" else "100644",
                "bytes": len(expected_raw), "sha256": digest(expected_raw)} and
                read_file(operation / "fixture" / name, FRAME_BYTES) == expected_raw, "FIXTURE_ORIGINAL_SOURCE")
    return raw, value


def canonical_failure_predicates(group, code, receipt, context, entry, case):
    """Failure-only labels; the unchanged original requires decide acceptance."""
    if group == "CANONICAL_RETURN":
        checks = (("CASE_SUPPORTED", case in CASES), ("RETURN_CODE_TYPE", type(code) is int),
                  ("RECEIPT_TYPE", type(receipt) is dict))
    elif group == "CANONICAL_RECEIPT":
        expected_code, product_code = (0, 0) if case == "Q1" else (23, 23) if case == "Q2" else (125, -15)
        argv = [str(Path(sys.executable).resolve()), "-I", "-B", "-S", str(Path(context["root"]) / "fixture.py"),
                "--product", case]
        checks = (
            ("RETURN_CODE", code == expected_code),
            ("SCHEMA", type(receipt.get("schema")) is int and receipt["schema"] == 1),
            ("INVOCATION_ID", receipt.get("id") == entry["invocationId"]),
            ("JOB_ID", receipt.get("jobId") == context["id"]),
            ("COMMAND_KIND", receipt.get("kind") == "command"),
            ("PURPOSE", receipt.get("purpose") == "dependency-context-" + case.lower()),
            ("PRODUCT_ARGV", receipt.get("requestedArgv") == receipt.get("executedArgv") == argv),
            ("CONTROLLER_PID", receipt.get("controllerPid") == entry["producerIdentity"]["pid"]),
            ("CWD", receipt.get("cwd") == context["root"]),
            ("WRAPPER", receipt.get("wrapper") == str(Path(context["root"]) / "gradlew")),
            ("HOST", receipt.get("host") == "macos-arm64"),
            ("GRADLE_HOME", receipt.get("gradleHome") == context["gradleHome"]),
            ("SOURCE_SNAPSHOTS", receipt.get("sourceBefore") == receipt.get("sourceAfter") == context["source"]),
            ("SOURCE_UNCHANGED", receipt.get("sourceUnchanged") is True),
            ("PRODUCT_PID", type(receipt.get("productPid")) is int and receipt["productPid"] > 0),
            ("PRODUCT_EXIT", type(receipt.get("productExitCode")) is int and receipt["productExitCode"] == product_code),
            ("STOP_EXIT", type(receipt.get("stopExitCode")) is int and receipt["stopExitCode"] == 0),
            ("FINAL_EXIT", type(receipt.get("finalExitCode")) is int and receipt["finalExitCode"] == code),
            ("OWNED_SURVIVORS", receipt.get("ownedSurvivors") == []),
            ("OWNERSHIP_DISCOVERY", type(receipt.get("ownership")) is dict and receipt["ownership"].get("discoveryErrors") == []))
    elif group == "CANONICAL_STOP":
        checks = (("STOP_ARGV", receipt.get("stopArgv") == [str(Path(context["root"]) / "gradlew"), "--stop", "--console=plain",
                  "--no-parallel", "--max-workers=2", "-Dorg.gradle.jvmargs=" + JVM_ARGUMENTS]),)
    elif group == "CANONICAL_CLOSED_PRODUCT":
        checks = (("ERRORS_EMPTY", receipt.get("errors") == []), ("CANCEL_SIGNALS_ABSENT", "cancelledSignals" not in receipt),
                  ("CANCEL_REQUEST_ABSENT", "cancelRequested" not in receipt))
    elif group == "CANONICAL_CANCELLATION":
        checks = (("CANCELLATION_ERRORS", receipt.get("errors") == CANCELLATION_ERRORS),
                  ("CANCEL_SIGNALS", receipt.get("cancelledSignals") == [15]),
                  ("CANCEL_REQUEST", receipt.get("cancelRequested") is False))
    else:
        raise QualificationError("FAILURE_DIAGNOSTIC_GROUP")
    return tuple(label for label, passed in checks if not passed)


def validate_canonical_result(code, receipt, context, entry, case):
    """Pure exact DATA checks; the call-site must supply its ORIGINAL return."""
    group = "CANONICAL_RETURN"
    try:
        require(case in CASES and type(code) is int and type(receipt) is dict, "CANONICAL_RETURN")
        expected_code, product_code = (0, 0) if case == "Q1" else (23, 23) if case == "Q2" else (125, -15)
        invocation = entry["invocationId"]
        argv = [str(Path(sys.executable).resolve()), "-I", "-B", "-S", str(Path(context["root"]) / "fixture.py"),
                "--product", case]
        group = "CANONICAL_RECEIPT"
        require(code == expected_code and type(receipt.get("schema")) is int and receipt["schema"] == 1 and
                receipt.get("id") == invocation and receipt.get("jobId") == context["id"] and
                receipt.get("kind") == "command" and receipt.get("purpose") == "dependency-context-" + case.lower() and
                receipt.get("requestedArgv") == receipt.get("executedArgv") == argv and
                receipt.get("controllerPid") == entry["producerIdentity"]["pid"] and
                receipt.get("cwd") == context["root"] and receipt.get("wrapper") == str(Path(context["root"]) / "gradlew") and
                receipt.get("host") == "macos-arm64" and receipt.get("gradleHome") == context["gradleHome"] and
                receipt.get("sourceBefore") == receipt.get("sourceAfter") == context["source"] and
                receipt.get("sourceUnchanged") is True and
                all(type(receipt.get(key)) is int for key in ("productPid", "productExitCode", "stopExitCode", "finalExitCode")) and
                receipt["productPid"] > 0 and receipt["productExitCode"] == product_code and receipt["stopExitCode"] == 0 and
                receipt["finalExitCode"] == code and receipt.get("ownedSurvivors") == [] and
                type(receipt.get("ownership")) is dict and receipt["ownership"].get("discoveryErrors") == [],
                "CANONICAL_RECEIPT")
        group = "CANONICAL_STOP"
        require(receipt.get("stopArgv") == [str(Path(context["root"]) / "gradlew"), "--stop", "--console=plain",
                "--no-parallel", "--max-workers=2", "-Dorg.gradle.jvmargs=" + JVM_ARGUMENTS], "CANONICAL_STOP")
        if case in ("Q1", "Q2"):
            # The unchanged executor emits these fields only for actual cancellation.
            # Normal original receipts must omit them, not gain synthesized defaults.
            group = "CANONICAL_CLOSED_PRODUCT"
            require(receipt.get("errors") == [] and "cancelledSignals" not in receipt and
                    "cancelRequested" not in receipt, "CANONICAL_CLOSED_PRODUCT")
            return "SUCCESS" if case == "Q1" else "CLOSED_FAILED_PRODUCT"
        group = "CANONICAL_CANCELLATION"
        require(receipt.get("errors") == CANCELLATION_ERRORS and receipt.get("cancelledSignals") == [15] and
                receipt.get("cancelRequested") is False, "CANONICAL_CANCELLATION")
        return "INFRASTRUCTURE_REFUSAL"
    except QualificationError as error:
        with contextlib.suppress(BaseException):
            error._qualification_failure_predicates = canonical_failure_predicates(group, code, receipt, context, entry, case)
        raise


def produce(fd):
    endpoint = bridge.producer(bridge.QUALIFICATION, fd)
    try:
        # All stdout/stderr, including initialize's private state path, is already
        # captured by the original P endpoint. No extra Step or owner is fabricated.
        interpreter = bridge.checked_interpreter(endpoint.deadline_ns)
        fixture_raw, fixture = fixture_binding(endpoint.operation, endpoint.repository_source, interpreter)
        require(endpoint.case in CASES and endpoint.inputs["fixtureSourceSha256"] == digest(fixture_raw) and
                endpoint.canonical_root == endpoint.operation / "fixture" and
                endpoint.state == endpoint.operation / "states" / endpoint.case, "PRODUCER_FIXTURE_INPUT")
        runner = module("dependency_context_canonical_executor", "scripts/run-audit-command.py")
        require(runner.JVM_ARGUMENTS == JVM_ARGUMENTS, "CANONICAL_RESOURCE_POLICY")
        left(endpoint.deadline_ns)
        initialized = runner.initialize(argparse.Namespace(root=str(endpoint.canonical_root), state=str(endpoint.state),
                                        expected_commit=fixture["sourceCommit"], host="macos-arm64"))
        require(type(initialized) is int and initialized == 0, "CANONICAL_INITIALIZER_RETURN")
        state, context = runner.context_at(str(endpoint.state))
        left(endpoint.deadline_ns)
        context_raw = read_file(state / "context.json", STREAM_BYTES)
        policy_raw = read_file(state / "gradle-home" / "gradle.properties", STREAM_BYTES)
        require(context["expectedCommit"] == fixture["sourceCommit"] and context["tree"] == fixture["sourceTree"] and
                context["gradlePropertiesSha256"] == digest(policy_raw), "CANONICAL_FIXTURE_SOURCE")
        invocation, original_identity = uuid.uuid4().hex, endpoint.identity_record()
        entry = {"schema": 1, "scope": SCOPE, "case": endpoint.case, "binding": endpoint.binding,
                 "caseInputSha256": endpoint.input_sha256, "contextSha256": digest(context_raw),
                 "contextId": context["id"], "invocationId": invocation, "fixtureSourceCommit": fixture["sourceCommit"],
                 "fixtureSourceTree": fixture["sourceTree"], "gradlePolicySha256": digest(policy_raw),
                 "producerIdentity": original_identity, "enteredMonotonicNs": shared_raw_ns()}
        entry_raw = encoded(entry)
        write_new(endpoint.canonical_entry_path, entry_raw)
        endpoint.ready(endpoint.canonical_entry_path)
        purpose = "dependency-context-" + endpoint.case.lower()
        argv = [interpreter["path"], "-I", "-B", "-S", str(endpoint.canonical_root / "fixture.py"), "--product", endpoint.case]
        args = argparse.Namespace(cwd=str(endpoint.canonical_root), wrapper=str(endpoint.canonical_root / "gradlew"),
            id=invocation, purpose=purpose, kind="command", argv=argv, timeout=PRODUCT_SECONDS,
            stop_timeout=STOP_SECONDS, receipt=None)
        # The existing canonical call creates/retains its own original child markers.
        # This selector is local to P, not serialized current authority from F/D.
        with environment({**os.environ, "P2PKIT_AUDIT_STATE_DIR": str(state)}):
            code = runner.execute(args)
            returned_raw_ns = shared_raw_ns()  # Immediate ORIGINAL return, before any receipt read.
        receipt_raw = read_file(state / "evidence" / invocation / "receipt.json", 32 * MIB)
        receipt = parsed(receipt_raw, 32 * MIB)
        disposition = validate_canonical_result(code, receipt, context, entry, endpoint.case)
        require(read_file(state / "context.json", STREAM_BYTES) == context_raw and
                read_file(state / "gradle-home" / "gradle.properties", STREAM_BYTES) == policy_raw and
                read_file(endpoint.canonical_entry_path, STREAM_BYTES) == entry_raw, "PRODUCER_ORIGINALS_CHANGED")
        left(endpoint.deadline_ns)
        result = {"schema": 1, "scope": SCOPE, "case": endpoint.case, "binding": endpoint.binding,
                  "caseInputSha256": endpoint.input_sha256, "canonicalEntrySha256": digest(entry_raw),
                  "producerIdentity": original_identity, "commands": [{"invocationId": invocation, "purpose": purpose,
                  "receiptSha256": digest(receipt_raw), "code": code, "returnedRawNs": returned_raw_ns}],
                  "code": code, "disposition": disposition, "completedRawNs": shared_raw_ns()}
        write_new(endpoint.producer_result_path, encoded(result))
        # complete closes original P captures BEFORE its final delivery attempt. In
        # Q4 the already closed canonical125 originals survive the lost-D EPIPE.
        return endpoint.complete(endpoint.producer_result_path)
    except BaseException as error:
        with contextlib.suppress(BaseException):
            bridge.record_failure(bridge.QUALIFICATION, endpoint.directory, endpoint.prepared, "P", error)
        raise


BRIDGE_RECORD_KEYS = frozenset(("schema", "scope", "case", "binding", "caseInputSha256", "canonicalEntrySha256",
    "producerResultSha256", "native", "action", "closure", "lossAnnotations", "caseStartNs", "caseEndNs",
    "closedMonotonicNs"))
NATIVE_KEYS = frozenset(("foreground", "service", "producerBirth", "producer", "serviceSession", "producerSession",
    "product", "producerNative", "serviceNative", "productNative", "registrations", "signalReturns"))
CLOSURE_KEYS = frozenset(("producerWait", "producerPipeEof", "producerPipeCaptures", "producerRecords",
    "serviceFinalFrame", "serviceCaptures", "producerNativeExit", "serviceNativeExit", "controlEof", "controlClosed",
    "registrationAbsent", "rootObjectsRemoved", "adminClosed", "soleWritersRetired", "nativeRetention"))
ACTION_KEYS = frozenset(("kind", "canonicalEntrySha256", "canonicalStartSha256", "productReadySha256",
                       "startedRawNs", "returnedRawNs", "returnedValue"))
Q4_LOSSES = {"producerWait": "ABSENT_D_DIED", "producerPipeEof": "ABSENT_D_DIED",
             "serviceFinalFrame": "ABSENT_D_DIED", "producerPipeCaptures": "INCOMPLETE_D_DIED",
             "serviceCaptures": "INCOMPLETE_D_DIED"}


def native_status(row, identity, expected_code):
    require(type(row) is dict and set(row) == {"event", "status", "observedRawNs"} and
            integer(row["observedRawNs"]), "NATIVE_EVENT_RECORD")
    event, status = row["event"], row["status"]
    require(type(event) is dict and set(event) == {"ident", "filter", "flags", "fflags", "data"} and
            all(type(value) is int for value in event.values()) and event["ident"] == identity["pid"] and
            event["filter"] == -5 and event["fflags"] & 0x80000000 and event["fflags"] & 0x04000000 and
            not event["flags"] & 0x4000, "NATIVE_ORIGINAL_EVENT")
    require(type(status) is dict and set(status) == {"rawStatus", "kind", "value", "popenCode"} and
            type(status["rawStatus"]) is int and type(status["value"]) is int and
            type(status["popenCode"]) is int and status["rawStatus"] == event["data"] and
            status["popenCode"] == expected_code, "NATIVE_STATUS")
    if expected_code >= 0:
        require(status["kind"] == "EXITED" and status["value"] == expected_code and
                os.WIFEXITED(status["rawStatus"]) and os.WEXITSTATUS(status["rawStatus"]) == expected_code,
                "NATIVE_EXIT_STATUS")
    else:
        require(status["kind"] == "SIGNALED" and status["value"] == -expected_code and
                os.WIFSIGNALED(status["rawStatus"]) and os.WTERMSIG(status["rawStatus"]) == -expected_code,
                "NATIVE_SIGNAL_STATUS")


def validate_registration(row, identity, action_started):
    require(type(row) is dict and set(row) == {"observer", "observation"} and row["observer"] in ("F", "D"),
            "REGISTRATION_OBSERVER")
    value = row["observation"]
    require(type(value) is dict and set(value) == {"identity", "startedMonotonicNs", "returnedMonotonicNs", "requested",
                                                "receipts", "recheckedMonotonicNs"}, "REGISTRATION_RECORD")
    bridge.same_identity(value["identity"], identity)
    require(all(integer(value[key]) for key in ("startedMonotonicNs", "returnedMonotonicNs", "recheckedMonotonicNs")) and
            value["startedMonotonicNs"] <= value["returnedMonotonicNs"] <= value["recheckedMonotonicNs"] <= action_started and
            value["requested"] == {"ident": identity["pid"], "filter": -5, "flags": 0x1 | 0x4 | 0x40,
                                   "fflags": 0x80000000 | 0x04000000}, "REGISTRATION_BEFORE_ACTION")
    require(type(value["receipts"]) is list and len(value["receipts"]) == 1, "REGISTRATION_RECEIPT")
    receipt = value["receipts"][0]
    require(type(receipt) is dict and set(receipt) == {"ident", "filter", "flags", "fflags", "data"} and
            all(type(item) is int for item in receipt.values()) and receipt["ident"] == identity["pid"] and
            receipt["filter"] == -5 and receipt["flags"] & 0x4000 and receipt["data"] == 0,
            "REGISTRATION_ORIGINAL_RETURN")


def validate_signal(row, signaler, identity, number):
    require(type(row) is dict and set(row) == {"signaler", "observation", "orphan"} and
            row["signaler"] == signaler, "SIGNAL_ORIGINAL_SENDER")
    value = row["observation"]
    require(type(value) is dict and set(value) == {"identity", "signal", "returnedCode", "startedMonotonicNs",
            "returnedMonotonicNs"} and type(value["signal"]) is int and value["signal"] == number and
            type(value["returnedCode"]) is int and value["returnedCode"] == 0 and
            integer(value["startedMonotonicNs"]) and integer(value["returnedMonotonicNs"]) and
            value["startedMonotonicNs"] <= value["returnedMonotonicNs"], "SIGNAL_ORIGINAL_RETURN")
    bridge.same_identity(value["identity"], identity)
    return value


def validate_case_records(case, record, entry, producer, receipt, context, start, ready):
    """Fixed original-observation DATA assessor; never a production authority."""
    require(case in CASES and type(record) is dict and set(record) == BRIDGE_RECORD_KEYS and
            type(record["schema"]) is int and record["schema"] == 1 and record["scope"] == SCOPE and
            record["case"] == case and all(type(record[key]) is str and HASH.fullmatch(record[key]) for key in
                ("binding", "caseInputSha256", "canonicalEntrySha256", "producerResultSha256")), "BRIDGE_RESULT_RECORD")
    require(type(entry) is dict and set(entry) == bridge.CANONICAL_ENTRY_KEYS | {
            "invocationId", "fixtureSourceCommit", "fixtureSourceTree"} and type(entry["schema"]) is int and
            entry["schema"] == 1 and entry["scope"] == SCOPE and entry["case"] == case and
            entry["binding"] == record["binding"] and entry["caseInputSha256"] == record["caseInputSha256"] and
            entry["contextId"] == context["id"] and INVOCATION.fullmatch(entry["invocationId"]) and
            entry["fixtureSourceCommit"] == context["source"]["commit"] and
            entry["fixtureSourceTree"] == context["source"]["tree"] and
            entry["gradlePolicySha256"] == context["gradlePropertiesSha256"], "CANONICAL_ENTRY_RECORD")
    require(type(producer) is dict and set(producer) == bridge.PRODUCER_RESULT_KEYS and
            type(producer["schema"]) is int and producer["schema"] == 1 and producer["scope"] == SCOPE and
            producer["case"] == case and producer["binding"] == record["binding"] and
            producer["caseInputSha256"] == record["caseInputSha256"] and
            producer["canonicalEntrySha256"] == record["canonicalEntrySha256"] and
            producer["producerIdentity"] == entry["producerIdentity"] and
            type(producer["commands"]) is list and len(producer["commands"]) == 1 and
            integer(producer["completedRawNs"]), "PRODUCER_RESULT_RECORD")
    command = producer["commands"][0]
    require(type(command) is dict and set(command) == {"invocationId", "purpose", "receiptSha256", "code", "returnedRawNs"} and
            command["invocationId"] == entry["invocationId"] and command["purpose"] == "dependency-context-" + case.lower() and
            type(command["receiptSha256"]) is str and HASH.fullmatch(command["receiptSha256"]) and
            type(command["code"]) is int and command["code"] == producer["code"] and integer(command["returnedRawNs"]) and
            command["returnedRawNs"] <= producer["completedRawNs"], "PRODUCER_COMMAND_RECORD")
    disposition = validate_canonical_result(producer["code"], receipt, context, entry, case)
    require(producer["disposition"] == disposition, "PRODUCER_DISPOSITION")
    expected_code = 0 if case == "Q1" else 23 if case == "Q2" else 125
    native, action, closure = record["native"], record["action"], record["closure"]
    require(type(native) is dict and set(native) == NATIVE_KEYS and type(action) is dict and
            set(action) == ACTION_KEYS and type(closure) is dict and set(closure) == CLOSURE_KEYS,
            "BRIDGE_ORIGINAL_ROSTERS")
    for role in ("foreground", "service", "producerBirth", "producer", "product"):
        bridge.same_identity(native[role], native[role])
    bridge.same_identity(native["producer"], entry["producerIdentity"])
    p, d, k = native["producer"], native["service"], native["product"]
    require(p["parentPid"] == d["pid"] and p["parentUniqueId"] == d["uniqueId"] and
            k["parentPid"] == p["pid"] and k["parentUniqueId"] == p["uniqueId"] and
            receipt["productPid"] == k["pid"] and len({p["pid"], d["pid"], k["pid"], native["foreground"]["pid"]}) == 4,
            "ORIGINAL_PRODUCT_LINEAGE")
    require(all(native["producerBirth"][key] == p[key] for key in
            bridge.IDENTITY_KEYS - {"pidVersion", "status"}), "PRODUCER_BIRTH_JOIN")
    for identity in (p, d, k):
        require(identity["uid"] == identity["realUid"] == native["foreground"]["uid"] and
                identity["gid"] == identity["realGid"] == native["foreground"]["gid"], "NATIVE_ACCOUNT")
    require(native["producerSession"] == {"pid": p["pid"], "sessionId": p["pid"], "processGroupId": p["pid"]} and
            type(native["serviceSession"]) is dict and set(native["serviceSession"]) == {"pid", "sessionId", "processGroupId"} and
            native["serviceSession"]["pid"] == d["pid"] and
            all(integer(value) for value in native["serviceSession"].values()) and
            native["serviceSession"]["sessionId"] != p["pid"] and
            native["serviceSession"]["processGroupId"] != p["pid"], "ORIGINAL_PRODUCER_SESSION")
    native_status(native["producerNative"], p, expected_code)
    native_status(native["serviceNative"], d, -9 if case == "Q4" else expected_code)
    native_status(native["productNative"], k, -15 if case in ("Q3", "Q4") else expected_code)
    expected_action = "RELEASE" if case in ("Q1", "Q2") else "F_WRITE_EOF" if case == "Q3" else "D_SIGKILL"
    require(action["kind"] == expected_action and
            all(type(action[key]) is str and HASH.fullmatch(action[key]) for key in
                ("canonicalEntrySha256", "canonicalStartSha256", "productReadySha256")) and
            action["canonicalEntrySha256"] == record["canonicalEntrySha256"] and
            all(integer(action[key]) for key in ("startedRawNs", "returnedRawNs")) and
            (type(action["returnedValue"]) is int and action["returnedValue"] == 0 if case == "Q4"
             else action["returnedValue"] is None), "ORIGINAL_ACTION")
    require(all(integer(record[key]) for key in ("caseStartNs", "caseEndNs", "closedMonotonicNs")) and
            integer(entry["enteredMonotonicNs"]) and integer(ready["readyMonotonicNs"]) and
            record["caseStartNs"] <= entry["enteredMonotonicNs"] <= ready["readyMonotonicNs"] <=
            action["startedRawNs"] <= action["returnedRawNs"] <= record["closedMonotonicNs"] < record["caseEndNs"] <=
            record["caseStartNs"] + CASE_SECONDS * NS and
            action["startedRawNs"] <= command["returnedRawNs"] <= producer["completedRawNs"] <= record["closedMonotonicNs"],
            "ORIGINAL_CASE_TIMING")
    # P/D may react while F's initiating syscall is returning. Require genuine
    # causal starts, not a fabricated order between independent process returns.
    # F's own later native observations do remain after F's action return.
    require(producer["completedRawNs"] <= native["producerNative"]["observedRawNs"] and
            action["returnedRawNs"] <= native["productNative"]["observedRawNs"] <= record["closedMonotonicNs"] and
            action["returnedRawNs"] <= native["producerNative"]["observedRawNs"] <= record["closedMonotonicNs"] and
            action["returnedRawNs"] <= native["serviceNative"]["observedRawNs"] <= record["closedMonotonicNs"],
            "ORIGINAL_TERMINAL_ORDER")
    require(type(ready) is dict and set(ready) == {"schema", "scope", "case", "binding", "contextId", "invocationId",
            "pid", "parentPid", "account", "ownership", "sourceSha256", "sigtermDefault", "sigtermBlocked", "readyMonotonicNs"} and
            type(ready["schema"]) is int and ready["schema"] == 1 and ready["scope"] == SCOPE and ready["case"] == case and
            ready["binding"] == record["binding"] and ready["contextId"] == context["id"] and
            ready["invocationId"] == entry["invocationId"] and type(ready["pid"]) is int and ready["pid"] == k["pid"] and
            type(ready["parentPid"]) is int and ready["parentPid"] == p["pid"] and
            ready["sigtermDefault"] is True and ready["sigtermBlocked"] is False and
            ready["sourceSha256"] == digest(FIXTURE.encode("ascii")), "ORIGINAL_PRODUCT_READY")
    state = str(Path(context["gradleHome"]).parent)
    require(ready["ownership"] == {"jobId": context["id"], "chain": entry["invocationId"],
            "domains": [{"id": entry["invocationId"], "job": context["id"], "state": state, "home": context["gradleHome"]}],
            "state": state, "home": context["gradleHome"]}, "ORIGINAL_PRODUCT_OWNER_MARKERS")
    bridge.validate_account(ready["account"])
    bridge.identity_account(k, ready["account"])
    # The canonical start record is intentionally the pre-spawn original, not
    # a reconstructed final receipt. Its available source/context joins suffice.
    for key in ("schema", "id", "purpose", "kind", "requestedArgv", "cwd", "wrapper", "host", "jobId", "gradleHome", "controllerPid"):
        require(start.get(key) == receipt[key], "ORIGINAL_CANONICAL_START")
    require(all(start.get(key) is None for key in ("sourceBefore", "sourceAfter", "productExitCode", "stopExitCode")) and
            "productPid" not in start and "executedArgv" not in start, "CANONICAL_START_NOT_RECONSTRUCTED")
    registrations = native["registrations"]
    expected_watches = {("F", identity["pid"]): identity for identity in (d, p, k)}
    if case != "Q4":
        expected_watches.update({("D", identity["pid"]): identity for identity in (native["foreground"], p)})
    require(type(registrations) is list and len(registrations) == len(expected_watches), "ORIGINAL_REGISTRATIONS")
    seen_watches = set()
    for row in registrations:
        require(type(row) is dict and set(row) == {"observer", "observation"} and type(row["observer"]) is str and
                type(row["observation"]) is dict and type(row["observation"].get("identity")) is dict and
                type(row["observation"]["identity"].get("pid")) is int, "REGISTRATION_OBSERVER")
        key = row["observer"], row["observation"]["identity"]["pid"]
        require(key in expected_watches and key not in seen_watches, "ORIGINAL_WATCH_ROSTER")
        validate_registration(row, expected_watches[key], action["startedRawNs"])
        seen_watches.add(key)
    require(seen_watches == set(expected_watches), "ORIGINAL_WATCH_ROSTER")
    signals = native["signalReturns"]
    require(type(signals) is list, "SIGNAL_ROSTER")
    if case in ("Q1", "Q2"):
        require(signals == [], "UNEXPECTED_SIGNAL")
    elif case == "Q3":
        require(len(signals) == 1 and signals[0]["orphan"] is None, "EOF_SIGNAL_ROSTER")
        sent = validate_signal(signals[0], "D", p, 15)
        require(action["startedRawNs"] <= sent["startedMonotonicNs"] <= command["returnedRawNs"] and
                sent["returnedMonotonicNs"] <= native["serviceNative"]["observedRawNs"], "EOF_REACTION_ORDER")
    else:
        require(len(signals) == 2 and signals[0]["orphan"] is None, "D_LOSS_SIGNAL_ROSTER")
        injected = validate_signal(signals[0], "F", d, 9)
        cancelled = validate_signal(signals[1], "F", p, 15)
        orphan = signals[1]["orphan"]
        require(type(orphan) is dict and set(orphan) == {"originalParentPid", "originalParentUniqueId", "currentParentPid",
                "currentParentUniqueId", "serviceExitObservedRawNs", "checkedRawNs"} and
                all(integer(value) for value in orphan.values()) and orphan["originalParentPid"] == p["parentPid"] and
                orphan["originalParentUniqueId"] == p["parentUniqueId"] and
                (orphan["currentParentPid"], orphan["currentParentUniqueId"]) in
                ((d["pid"], d["uniqueId"]), (1, d["parentUniqueId"])) and
                orphan["serviceExitObservedRawNs"] == native["serviceNative"]["observedRawNs"], "ORIGINAL_ORPHAN_JOIN")
        require(action["startedRawNs"] <= injected["startedMonotonicNs"] <= injected["returnedMonotonicNs"] <=
                action["returnedRawNs"] <= orphan["serviceExitObservedRawNs"] <= orphan["checkedRawNs"] <=
                cancelled["startedMonotonicNs"] <= command["returnedRawNs"] and
                cancelled["returnedMonotonicNs"] <= native["producerNative"]["observedRawNs"],
                "ACTUAL_D_EXIT_BEFORE_ORPHAN_SIGNAL")
    losses = Q4_LOSSES if case == "Q4" else {}
    require(record["lossAnnotations"] == losses and closure["producerRecords"] == "CLOSED" and
            closure["nativeRetention"] == "HELD_UNTIL_SUITE_FINISH", "ORIGINAL_CLOSURE_CLASSIFICATION")
    for key in ("producerNativeExit", "serviceNativeExit", "controlEof", "controlClosed", "registrationAbsent",
                "rootObjectsRemoved", "adminClosed", "soleWritersRetired"):
        require(closure[key] is True, "ORIGINAL_REQUIRED_CLOSURE")
    if case == "Q4":
        require(all(closure[key] == value for key, value in Q4_LOSSES.items()), "D_LOSS_NOT_FAKE_CLOSED")
    else:
        require(type(closure["producerWait"]) is int and closure["producerWait"] == expected_code and
                closure["producerPipeEof"] is True and closure["producerPipeCaptures"] == "CLOSED" and
                closure["serviceCaptures"] == "CLOSED" and closure["serviceFinalFrame"] == "RECEIVED",
                "ORIGINAL_NORMAL_CLOSURE")
    return disposition


def validate_service_final(case, frame, record, producer):
    """Join the actual F8 return; never supply one for the killed D in Q4."""
    require(case in ("Q1", "Q2", "Q3"), "D_LOSS_HAS_NO_FINAL_FRAME")
    final = bridge.validate_frame(frame, 8, record["binding"])
    require(type(final) is dict and set(final) == {"case", "producerCode", "producerStreams", "serviceStreams",
            "resultFrame", "tracePrefix", "producerControlEof", "producerWait", "nativeClosed", "capturesClosed",
            "signalReturns", "registrations", "producerNative", "foregroundLoss", "startForward"} and
            final["case"] == case and type(final["producerCode"]) is int and final["producerCode"] == producer["code"] and
            all(final[key] is True for key in ("producerControlEof", "producerWait", "nativeClosed", "capturesClosed")) and
            final["signalReturns"] == [row for row in record["native"]["signalReturns"] if row["signaler"] == "D"] and
            final["registrations"] == [row for row in record["native"]["registrations"] if row["observer"] == "D"],
            "ORIGINAL_SERVICE_FINAL")
    result = bridge.validate_frame(final["resultFrame"], 7, record["binding"])
    require(type(result) is dict and set(result) == {"case", "producerResultSha256", "producerCapturesSha256", "code"} and
            result["case"] == case and type(result["code"]) is int and result["code"] == producer["code"] and
            result["producerResultSha256"] == record["producerResultSha256"] and
            type(result["producerCapturesSha256"]) is str and HASH.fullmatch(result["producerCapturesSha256"]),
            "ORIGINAL_SERVICE_RESULT_FRAME")
    trace = final["tracePrefix"]
    require(type(trace) is list and len(trace) == 7, "ORIGINAL_SERVICE_FRAME_TRACE")
    for serial, row in enumerate(trace, 1):
        _, direction, kind = bridge.FRAME_ROSTER[serial - 1]
        require(type(row) is dict and set(row) == {"serial", "direction", "kind", "sha256"} and
                type(row["serial"]) is int and row["serial"] == serial and row["direction"] == direction and
                row["kind"] == kind and type(row["sha256"]) is str and HASH.fullmatch(row["sha256"]),
                "ORIGINAL_SERVICE_FRAME_TRACE")
    require(trace[-1] == bridge.frame_record(final["resultFrame"]), "ORIGINAL_SERVICE_RESULT_TRACE")
    native_status(final["producerNative"], record["native"]["producer"], producer["code"])
    require(final["producerNative"]["event"] == record["native"]["producerNative"]["event"] and
            final["producerNative"]["status"] == record["native"]["producerNative"]["status"] and
            producer["completedRawNs"] <= final["producerNative"]["observedRawNs"] <= record["closedMonotonicNs"],
            "ORIGINAL_SERVICE_NATIVE_JOIN")
    forward = final["startForward"]
    require(type(forward) is dict and set(forward) == {"startedMonotonicNs", "returnedMonotonicNs"} and
            all(integer(value) for value in forward.values()) and
            record["caseStartNs"] <= forward["startedMonotonicNs"] <= forward["returnedMonotonicNs"] <=
            record["native"]["serviceNative"]["observedRawNs"], "ORIGINAL_START_FORWARD")
    loss = final["foregroundLoss"]
    if case == "Q3":
        sent = record["native"]["signalReturns"][0]["observation"]
        require(type(loss) is dict and set(loss) == {"kind", "observedRawNs"} and loss["kind"] == "WRITE_EOF" and
                integer(loss["observedRawNs"]) and record["action"]["startedRawNs"] <= loss["observedRawNs"] <=
                sent["startedMonotonicNs"], "ORIGINAL_D_EOF_REACTION")
    else:
        require(loss is None, "UNEXPECTED_FOREGROUND_LOSS")
    return final


def assess_case(owner, outcome, case):
    # The actual shared validator runs against its retained original object;
    # expected-negative diagnosis cannot bypass or feed JSON back into it.
    refused, production = False, None
    try:
        production = owner.production_result(outcome)
    except bridge.ProductionRefusal:
        refused = True
    require(refused == (case in ("Q3", "Q4")), "PRODUCTION_VALIDATOR_DISPOSITION")
    if not refused:
        require(production == ((0, "SUCCESS") if case == "Q1" else (23, "CLOSED_FAILED_PRODUCT")),
                "PRODUCTION_ORIGINAL_RETURN")
    directory = owner.operation / "bridge" / "cases" / case
    record = outcome.record
    def own_record(name, maximum=32 * MIB):
        raw = read_file(directory / name, maximum)
        value = parsed(raw, maximum)
        require(raw == encoded(value), "CLOSED_RECORD_ENCODING")
        return raw, value
    bridge_raw, saved = own_record("bridge-result.json")
    require(saved == record and record["case"] == case, "ORIGINAL_OUTCOME_RECORD")
    input_raw, inputs = own_record("case-input.json", FRAME_BYTES)
    entry_raw, entry = own_record("canonical-entry.json", FRAME_BYTES)
    producer_raw, producer = own_record("producer-result.json", FRAME_BYTES)
    ready_raw, ready = own_record("product-ready.json", FRAME_BYTES)
    state = owner.operation / "states" / case
    context_raw, policy_raw = read_file(state / "context.json", STREAM_BYTES), read_file(state / "gradle-home/gradle.properties", STREAM_BYTES)
    context = parsed(context_raw, STREAM_BYTES)
    invocation = entry["invocationId"]
    require(type(invocation) is str and INVOCATION.fullmatch(invocation), "ORIGINAL_INVOCATION_ID")
    receipt_raw = read_file(state / "evidence" / invocation / "receipt.json", 32 * MIB)
    receipt = parsed(receipt_raw, 32 * MIB)
    start_raw = read_file(state / "evidence" / invocation / "start.json", STREAM_BYTES)
    start = parsed(start_raw, STREAM_BYTES)
    require(record["caseInputSha256"] == digest(input_raw) and
            record["canonicalEntrySha256"] == digest(entry_raw) and
            record["producerResultSha256"] == digest(producer_raw) and
            entry["contextSha256"] == digest(context_raw) and entry["gradlePolicySha256"] == digest(policy_raw) and
            producer["commands"][0]["receiptSha256"] == digest(receipt_raw) and
            record["action"]["canonicalStartSha256"] == digest(start_raw) and
            record["action"]["productReadySha256"] == digest(ready_raw) and
            inputs["binding"] == record["binding"] and inputs["caseStartNs"] == record["caseStartNs"] and
            inputs["caseEndNs"] == record["caseEndNs"] and inputs["foreground"] == record["native"]["foreground"] and
            inputs["account"] == ready["account"], "CASE_ORIGINAL_FILE_JOINS")
    validate_case_records(case, record, entry, producer, receipt, context, start, ready)
    action_raw, action = own_record("action-observation.json", STREAM_BYTES)
    native_raw, native = own_record("native-observations.json")
    require(action == record["action"] and native == record["native"], "ORIGINAL_OBSERVATION_FILES")
    if case == "Q4":
        require(not os.path.lexists(directory / "service-final.json"), "D_LOSS_HAS_NO_FINAL_FRAME")
    else:
        _final_raw, frame = own_record("service-final.json", FRAME_BYTES)
        final = validate_service_final(case, frame, record, producer)
        require(final["resultFrame"]["payload"]["producerCapturesSha256"] ==
                digest(read_file(directory / "producer-captures.json", FRAME_BYTES)), "ORIGINAL_P_CAPTURE_BINDING")
        bridge.verify_capture_rows(directory, final["producerStreams"], ("producer-pipe.stdout", "producer-pipe.stderr"), pipes=True)
        bridge.verify_capture_rows(directory, final["serviceStreams"], ("service.stdout", "service.stderr"))
    stop_raw = read_file(state / "stop-observation.json", FRAME_BYTES)
    stop = parsed(stop_raw)
    require(stop_raw == encoded(stop) and type(stop) is dict and set(stop) == {"schema", "scope", "case", "binding", "contextId",
            "invocationId", "pid", "parentPid", "account", "ownership", "argv", "observedRawNs"} and
            type(stop["schema"]) is int and stop["schema"] == 1 and stop["scope"] == SCOPE and stop["case"] == case and
            stop["binding"] == record["binding"] and stop["contextId"] == entry["contextId"] and
            stop["invocationId"] == invocation and integer(stop["pid"]) and stop["parentPid"] == record["native"]["producer"]["pid"] and
            stop["account"] == ready["account"] and stop["ownership"] == ready["ownership"] and
            stop["argv"] == receipt["stopArgv"][1:] and integer(stop["observedRawNs"]) and
            ready["readyMonotonicNs"] < stop["observedRawNs"] <= producer["commands"][0]["returnedRawNs"],
            "ORIGINAL_WRAPPER_STOP")
    release = directory / "product-release.json"
    if case in ("Q1", "Q2"):
        release_raw, value = own_record("product-release.json", FRAME_BYTES)
        require(set(value) == {"schema", "scope", "case", "binding", "readySha256", "releasedMonotonicNs"} and
                type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and
                value["case"] == case and value["binding"] == record["binding"] and value["readySha256"] == digest(ready_raw) and
                integer(value["releasedMonotonicNs"]) and record["action"]["startedRawNs"] <= value["releasedMonotonicNs"] <=
                record["action"]["returnedRawNs"], "ORIGINAL_PRODUCT_RELEASE")
    else:
        require(not os.path.lexists(release), "CANCELLATION_NO_RELEASE")
    result = {"schema": 1, "scope": SCOPE, "case": case, "binding": record["binding"],
              "caseInputSha256": digest(input_raw), "actualAction": record["action"]["kind"],
              "actionObservationSha256": digest(action_raw), "nativeObservationsSha256": digest(native_raw),
              "canonicalReceiptSha256": digest(receipt_raw), "canonicalEntrySha256": digest(entry_raw),
              "producerRecordsSha256": digest(producer_raw), "bridgeResultSha256": digest(bridge_raw),
              "productionDisposition": "REFUSED" if refused else "normal-fixture" if case == "Q1" else "failed-product-fixture",
              "controlResult": "PASS", "lossAnnotations": record["lossAnnotations"],
              "sourceAfterSha256": digest(encoded(receipt["sourceAfter"])), "closedMonotonicNs": shared_raw_ns()}
    require(result["closedMonotonicNs"] < record["caseEndNs"], "ASSESSMENT_CASE_DEADLINE")
    write_new(directory / "case-result.json", encoded(result))
    return result


class Qualification:
    def __init__(self):
        self.started, self.env = shared_raw_ns(), dict(os.environ)
        self.owner, self.output, self.recipient, self.recipient_original = None, None, None, None
        self.owner_finished, self.export_called = False, False
        self.case_results = []


def prepare(context):
    context.request, context.github = original_request(context.env)
    context.operation, context.operation_identity = operation_paths(context.env)
    require({path.name for path in context.operation.iterdir()} == {"allocation.json"}, "FRESH_OPERATION")
    allocation_raw = read_file(context.operation / "allocation.json", FRAME_BYTES)
    context.allocation = parsed(allocation_raw)
    require(allocation_raw == encoded(context.allocation), "ALLOCATION_ENCODING")
    now, wall = shared_raw_ns(), time.time_ns()
    context.job_end = validate_allocation(context.allocation, context.request, context.github, now, wall)
    context.policy_end = (context.allocation["startedMonotonicNs"] + POLICY_EXPIRES * NS -
                          context.allocation["startedEpochNs"])
    context.step_end = min(context.started + STEP_SECONDS * NS, context.job_end - UPLOAD_SECONDS * NS,
                           context.policy_end - UPLOAD_SECONDS * NS)
    require(now <= context.step_end and left(context.job_end) >= STEP_SECONDS + UPLOAD_SECONDS and
            wall < LATEST_ENTRY * NS, "QUALIFIER_ENTRY_RESERVE")
    end = min(context.started + PREPARE_SECONDS * NS, context.step_end)
    context.output = CommandFile(context.env)
    for name in ("home", "tmp", "crypto", "outputs", "evidence"):
        (context.operation / name).mkdir(mode=0o700)
        private_directory(context.operation / name, empty=True)
    context.evidence = context.operation / "evidence"
    context.environment = child_environment(context.operation)
    captures = []
    for name in ("foreground-prefix.stdout", "foreground-prefix.stderr"):
        fd = os.open(context.operation / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        captures.append(os.fdopen(fd, "w", encoding="utf-8"))
    with captures[0] as output, captures[1] as error, contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
        context.source = repository_source(context.request, end, context.environment)
        context.account = bridge.account()
        context.interpreter = bridge.checked_interpreter(end)
        policy_raw = read_file(ROOT / POLICY_PATH, 96 * 1024)
        policy = validate_policy(policy_raw, time.time(), JOB_SECONDS)
        public_key = context.operation / "recipient-public.asc"
        write_new(public_key, policy["recipient"]["publicKey"].encode("ascii"))
        executable = shutil.which("gpg")
        require(executable is not None, "PUBLIC_GPG_UNAVAILABLE")
        context.gpg = file_pin(Path(executable).resolve(strict=True), 64 * MIB, end,
                               owners=(0, os.getuid()), executable=True)
        module("hosted_evidence_primitives", "scripts/hosted_evidence_primitives.py")
        context.exporter = module("dependency_context_public_evidence", "scripts/hosted_evidence.py")
        # The existing public validator's 60s + bounded cleanup must fit the
        # ORIGINAL prepare window. No key operation or clock is reconstructed.
        require(left(end) >= 70, "RECIPIENT_VALIDATION_RESERVE")
        context.recipient = context.exporter.validate_recipient(public_key, FINGERPRINT, context.operation / "crypto")
        left(end)
        require(context.recipient.fingerprint == FINGERPRINT and context.recipient.key_sha256 == KEY_SHA256 and
                context.recipient.encryption_fingerprint == ENCRYPTION_FINGERPRINT and
                context.recipient.expires_at == KEY_EXPIRES and context.recipient.work_dir == context.operation / "crypto" and
                str(context.recipient.executable) == context.gpg["path"], "VALIDATED_PUBLIC_RECIPIENT")
        context.recipient_original = context.recipient
        context.recipient_work = private_directory(context.recipient.work_dir)
        context.recipient_home = private_directory(context.recipient.home)
        context.recipient_files = {name: file_pin(context.recipient.work_dir / name, STREAM_BYTES, end)
                                   for name in ("recipient.asc", "recipient.gpg")}
        for stream in (output, error):
            stream.flush()
            os.fsync(stream.fileno())
    require(all(stream.closed for stream in captures), "FOREGROUND_PREFIX_CLOSE")
    context.prefix = {name: file_pin(context.operation / name, STREAM_BYTES, end)
                      for name in ("foreground-prefix.stdout", "foreground-prefix.stderr")}
    write_new(context.operation / "foreground-prefix.json", encoded({"schema": 1, "scope": SCOPE,
        "github": context.github, "allocationSha256": digest(allocation_raw), "source": context.source,
        "account": context.account, "interpreter": context.interpreter, "policySha256": POLICY_SHA256,
        "recipientValidationReturned": True, "captures": context.prefix, "capturesClosed": True,
        "stepStartedRawNs": context.started, "stepEndRawNs": context.step_end, "jobEndRawNs": context.job_end,
        "returnedRawNs": shared_raw_ns()}))
    # No native owner/service/fixture exists before the original public
    # Recipient and actual prefix capture closure above. The shared constructor
    # is passive; its prepare_case acquires the sole F native observer.
    context.owner = bridge.Foreground(bridge.QUALIFICATION, context.operation, context.allocation,
                                      step_started_ns=context.started)
    require(context.owner.step_end_ns == min(context.started + STEP_SECONDS * NS, context.job_end, context.policy_end) and
            context.owner.job_end_ns == context.job_end and context.owner.policy_end_ns == context.policy_end,
            "SHARED_ORIGINAL_ENDS")
    left(end)


def validate_finish(finished, context):
    require(type(finished) is dict and set(finished) == {"schema", "scope", "github", "repositorySource", "allocationSha256",
            "cases", "sentinel", "nativeClosed", "closedMonotonicNs", "evidenceFiles"} and
            type(finished["schema"]) is int and finished["schema"] == 1 and finished["scope"] == SCOPE and
            finished["github"] == context.github and finished["repositorySource"] == {
                "commit": context.request["source_sha"], "tree": context.request["source_tree"]} and
            finished["allocationSha256"] == digest(encoded(context.allocation)) and
            finished["cases"] == [{"case": row["case"], "bridgeResultSha256": row["bridgeResultSha256"]}
                                   for row in context.case_results] and
            [row["case"] for row in context.case_results] == list(CASES) and finished["nativeClosed"] is True and
            integer(finished["closedMonotonicNs"]) and finished["closedMonotonicNs"] < context.step_end,
            "ORIGINAL_SUITE_FINISH")
    sentinel = finished["sentinel"]
    require(type(sentinel) is dict and set(sentinel) == {"identity", "survivalObservations", "waitCode", "streams", "closed"} and
            type(sentinel["waitCode"]) is int and sentinel["waitCode"] == 0 and sentinel["closed"] is True and
            type(sentinel["survivalObservations"]) is list and len(sentinel["survivalObservations"]) == 2,
            "ORIGINAL_SENTINEL_CLOSE")
    bridge.same_identity(sentinel["identity"], sentinel["identity"])
    bridge.identity_account(sentinel["identity"], context.account)
    terminal_raw = read_file(context.operation / "bridge/sentinel/native-exit.json", STREAM_BYTES)
    terminal = parsed(terminal_raw, STREAM_BYTES)
    require(terminal_raw == encoded(terminal), "ORIGINAL_SENTINEL_TERMINAL_ENCODING")
    native_status(terminal, sentinel["identity"], 0)
    bridge.verify_capture_rows(context.operation / "bridge/sentinel", sentinel["streams"],
                               ("sentinel.stdout", "sentinel.stderr"), pipes=True)
    require(all(read_file(context.operation / "bridge/sentinel" / name, STREAM_BYTES) == b""
                for name in ("sentinel.stdout", "sentinel.stderr")) and
            terminal["observedRawNs"] <= finished["closedMonotonicNs"], "ORIGINAL_SENTINEL_EMPTY_CLOSE")
    for case, observation in zip(("Q3", "Q4"), sentinel["survivalObservations"]):
        require(type(observation) is dict and set(observation) == {"case", "identity", "observedRawNs"} and
                observation["case"] == case and integer(observation["observedRawNs"]), "SENTINEL_ORIGINAL_SURVIVAL")
        bridge.same_identity(observation["identity"], sentinel["identity"])
        record = parsed(read_file(context.operation / "bridge/cases" / case / "bridge-result.json", 32 * MIB), 32 * MIB)
        require(record["native"]["producerNative"]["observedRawNs"] <= observation["observedRawNs"] <=
                terminal["observedRawNs"] and sentinel["identity"]["pid"] not in
                {record["native"][role]["pid"] for role in ("foreground", "service", "producer", "product")},
                "SENTINEL_NONMEMBER_SURVIVED")
        require(sentinel["identity"]["parentPid"] == record["native"]["foreground"]["pid"] and
                sentinel["identity"]["parentUniqueId"] == record["native"]["foreground"]["uniqueId"],
                "ORIGINAL_SENTINEL_FOREGROUND_PARENT")
    require(type(finished["evidenceFiles"]) is list and 0 < len(finished["evidenceFiles"]) < EVIDENCE_MEMBERS,
            "BRIDGE_EVIDENCE_ROSTER")


def copy_original(source, destination, end_ns, roster):
    source, destination = physical(source), physical(destination)
    before = file_pin(source, 32 * MIB, end_ns)
    require(len(roster) < EVIDENCE_MEMBERS and sum(row["bytes"] for row in roster.values()) + before["size"] <= EVIDENCE_BYTES,
            "EVIDENCE_ROSTER_BOUND")
    name = str(destination)
    if name in roster:
        require(roster[name]["bytes"] == before["size"] and roster[name]["sha256"] == before["sha256"],
                "DUPLICATE_EVIDENCE_CHANGED")
        return
    missing = []
    parent = destination.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    private_directory(parent)
    for path in reversed(missing):
        path.mkdir(mode=0o700)
        private_directory(path)
    raw = read_file(source, 32 * MIB)
    require(len(raw) == before["size"] and digest(raw) == before["sha256"], "ORIGINAL_COPY_SOURCE")
    write_new(destination, raw)
    require(file_pin(source, 32 * MIB, end_ns) == before, "ORIGINAL_COPY_CHANGED")
    roster[name] = {"bytes": len(raw), "sha256": digest(raw)}


def collect_evidence(context, finished, end_ns):
    roster = {}
    for name in ("allocation.json", "foreground-prefix.json", "foreground-prefix.stdout", "foreground-prefix.stderr",
                 "fixture-source.json", "fixture-setup-returns.json", "bridge-finish.json"):
        copy_original(context.operation / name, context.evidence / name, end_ns, roster)
    for name in ("fixture.py", "gradlew"):
        copy_original(context.fixture / name, context.evidence / "fixture" / name, end_ns, roster)
    names = set()
    for row in finished["evidenceFiles"]:
        require(type(row) is dict and set(row) == {"path", "bytes", "sha256"} and type(row["path"]) is str and
                re.fullmatch(r"bridge/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+", row["path"]) and
                ".." not in Path(row["path"]).parts and row["path"] not in names and
                integer(row["bytes"], 0, 32 * MIB) and type(row["sha256"]) is str and HASH.fullmatch(row["sha256"]),
                "BRIDGE_CLOSED_FILE")
        names.add(row["path"])
        actual = file_pin(context.operation / row["path"], 32 * MIB, end_ns)
        require(actual["size"] == row["bytes"] and actual["sha256"] == row["sha256"], "BRIDGE_ORIGINAL_FILE_CHANGED")
        copy_original(context.operation / row["path"], context.evidence / row["path"], end_ns, roster)
    for case in CASES:
        for name in ("case-input.json", "canonical-entry.json", "producer-result.json", "producer-captures.json",
                     "producer-controller.stdout", "producer-controller.stderr", "product-ready.json", "case-result.json",
                     "action-observation.json", "native-observations.json", "bridge-result.json"):
            relative = Path("bridge/cases") / case / name
            copy_original(context.operation / relative, context.evidence / relative, end_ns, roster)
        if case in ("Q1", "Q2"):
            relative = Path("bridge/cases") / case / "product-release.json"
            copy_original(context.operation / relative, context.evidence / relative, end_ns, roster)
        state = context.operation / "states" / case
        for name in ("context.json", "gradle-home/gradle.properties", "stop-observation.json"):
            copy_original(state / name, context.evidence / "states" / case / name, end_ns, roster)
        entries = 0
        for current, directories, files in os.walk(state / "evidence", topdown=True, followlinks=False):
            private_directory(Path(current))
            directories.sort()
            files.sort()
            entries += 1 + len(directories) + len(files)
            require(entries <= EVIDENCE_MEMBERS and all(re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", name)
                    for name in (*directories, *files)), "CANONICAL_EVIDENCE_NAMES")
            for directory in directories:
                private_directory(Path(current) / directory)
            for name in files:
                original = Path(current) / name
                copy_original(original, context.evidence / "states" / case / original.relative_to(state), end_ns, roster)
    rows = [{"path": str(Path(name).relative_to(context.evidence)), **value} for name, value in sorted(roster.items())]
    # One-way binding: this roster covers original evidence, not itself or the
    # following qualification summary. The final seal hashes the entire freeze.
    roster_record = {"schema": 1, "scope": SCOPE, "files": rows,
                     "excludes": ["evidence-roster.json", "qualification.json"]}
    roster_raw = encoded(roster_record)
    write_new(context.evidence / "evidence-roster.json", roster_raw)
    qualification = {"schema": 1, "scope": SCOPE, "github": context.github,
        "repositorySource": {"commit": context.request["source_sha"], "tree": context.request["source_tree"]},
        "fixtureSource": context.fixture_source, "allocationSha256": digest(encoded(context.allocation)),
        "caseResults": [{"case": row["case"], "sha256": digest(encoded(row))} for row in context.case_results],
        "sentinel": finished["sentinel"], "policySha256": POLICY_SHA256, "evidenceRosterSha256": digest(roster_raw),
        "result": RESULT}
    qualification_raw = encoded(qualification)
    write_new(context.evidence / "qualification.json", qualification_raw)
    return digest(qualification_raw)


def freeze_evidence(root, end_ns):
    files, directories, total = [], [], 0
    for current, children, names in os.walk(root, topdown=True, followlinks=False):
        directory = physical(current)
        private_directory(directory)
        directories.append(directory)
        children.sort()
        names.sort()
        require(len(files) + len(directories) + len(children) + len(names) <= EVIDENCE_MEMBERS, "FREEZE_MEMBERS")
        for name in names:
            require(re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", name), "FREEZE_FILENAME")
            path = directory / name
            pin = file_pin(path, EVIDENCE_BYTES, end_ns)
            total += pin["size"]
            require(total <= EVIDENCE_BYTES, "FREEZE_BYTES")
            files.append((path, pin))
    require(files and len(files) + len(directories) <= EVIDENCE_MEMBERS, "FREEZE_ROSTER")
    frozen = []
    for path, before in files:
        left(end_ns)
        os.chmod(path, 0o400, follow_symlinks=False)
        after = file_pin(path, EVIDENCE_BYTES, end_ns)
        require(after["sha256"] == before["sha256"] and after["size"] == before["size"] and
                after["stat"][:2] == before["stat"][:2] and stat.S_IMODE(after["stat"][2]) == 0o400, "FREEZE_CHANGED")
        frozen.append({"path": str(path.relative_to(root)), "stat": after["stat"], "bytes": after["size"],
                       "sha256": after["sha256"]})
    for path in reversed(directories):
        os.chmod(path, 0o500, follow_symlinks=False)
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o500,
                "FREEZE_DIRECTORY")
    left(end_ns)
    return {"files": frozen, "directories": [str(path.relative_to(root)) for path in directories], "bytes": total}


def output_snapshot(operation, github, end_ns, *, expected_manifest=None):
    outputs, directory = operation / "outputs", operation / "outputs/encrypted"
    private_directory(outputs)
    require({path.name for path in outputs.iterdir()} == {"encrypted"}, "EXCLUSIVE_ENCRYPTED_OUTPUT")
    identity = private_directory(directory)
    require({path.name for path in directory.iterdir()} == {"evidence.tar.gz.gpg", "manifest.json"}, "ENCRYPTED_ROSTER")
    raw = read_file(directory / "manifest.json", STREAM_BYTES)
    manifest = parsed(raw, STREAM_BYTES)
    require(raw == encoded(manifest) and type(manifest) is dict and set(manifest) == {"schema", "scope", "source", "github", "artifact"} and
            type(manifest["schema"]) is int and manifest["schema"] == 1 and
            manifest["scope"] == "ENCRYPTED_PRIVATE_TEST_EVIDENCE" and
            manifest["source"] == {"commit": github["source"], "tree": github["sourceTree"]} and
            manifest["github"] == {"repository": REPOSITORY, "runId": github["runId"], "runAttempt": github["runAttempt"]} and
            (expected_manifest is None or manifest == expected_manifest), "ENCRYPTED_MANIFEST")
    artifact = manifest["artifact"]
    require(type(artifact) is dict and set(artifact) == {"name", "size", "sha256"} and
            artifact["name"] == "evidence.tar.gz.gpg" and integer(artifact["size"], 1, CIPHERTEXT_BYTES) and
            type(artifact["sha256"]) is str and HASH.fullmatch(artifact["sha256"]), "ENCRYPTED_ARTIFACT")
    files = {name: file_pin(directory / name, bound, end_ns) for name, bound in
             (("evidence.tar.gz.gpg", CIPHERTEXT_BYTES), ("manifest.json", STREAM_BYTES))}
    require(files["evidence.tar.gz.gpg"]["size"] == artifact["size"] and
            files["evidence.tar.gz.gpg"]["sha256"] == artifact["sha256"] and
            files["manifest.json"]["sha256"] == digest(raw), "ENCRYPTED_BYTES")
    return {"identity": identity, "files": files}


def finish_export(context, finished):
    require(context.owner_finished and context.recipient is context.recipient_original and
            context.recipient_original is not None and not context.export_called and not _UNCLOSED_GIT and
            context.output is not None and not context.output.closed, "EXPORT_ORIGINAL_CUSTODY")
    validate_finish(finished, context)
    end = min(shared_raw_ns() + FREEZE_SECONDS * NS, context.step_end - EXPORT_SECONDS * NS,
              context.job_end - (EXPORT_SECONDS + UPLOAD_SECONDS) * NS)
    left(end)
    request, github = original_request(context.env)
    require(request == context.request and github == context.github and bridge.account() == context.account and
            private_directory(context.operation) == context.operation_identity and
            repository_source(request, end, context.environment) == context.source and
            bridge.checked_interpreter(end) == context.interpreter, "FREEZE_SOURCE_CHANGED")
    fixture_raw, fixture = fixture_binding(context.operation, {"commit": request["source_sha"], "tree": request["source_tree"]},
                                           context.interpreter)
    require(fixture_raw == context.fixture_source_raw and fixture == context.fixture_source and
            source_snapshot(context.fixture, end, context.fixture_environment, empty=context.fixture_empty) == {
                "commit": fixture["sourceCommit"], "tree": fixture["sourceTree"], "status": "", "diffSha256": digest(b"")} and
            fixture_roster(context.fixture, context.interpreter, end, context.fixture_environment, context.fixture_empty) ==
            fixture["sourceFiles"], "FREEZE_FIXTURE_CHANGED")
    validate_policy(read_file(ROOT / POLICY_PATH, 96 * 1024), time.time(), EXPORT_SECONDS + UPLOAD_SECONDS)
    require(private_directory(context.recipient.work_dir) == context.recipient_work and
            private_directory(context.recipient.home) == context.recipient_home and
            {name: file_pin(context.recipient.work_dir / name, STREAM_BYTES, end) for name in context.recipient_files} ==
            context.recipient_files and
            file_pin(Path(context.gpg["path"]), 64 * MIB, end, owners=(0, os.getuid()), executable=True) == context.gpg,
            "ORIGINAL_RECIPIENT_CHANGED")
    write_new(context.operation / "bridge-finish.json", encoded(finished))
    qualification_hash = collect_evidence(context, finished, end)
    frozen = freeze_evidence(context.evidence, end)
    export_end = min(shared_raw_ns() + EXPORT_SECONDS * NS, context.step_end,
                     context.job_end - UPLOAD_SECONDS * NS, context.policy_end - UPLOAD_SECONDS * NS)
    seconds = min(EXPORT_SECONDS, math.floor(left(export_end) - 10))
    require(seconds > 0, "EXPORT_CLEANUP_RESERVE")
    context.export_called = True
    manifest = context.exporter.export_encrypted(context.evidence, context.operation / "outputs/encrypted",
        context.recipient_original, source_commit=request["source_sha"], source_tree=request["source_tree"],
        run_id=github["runId"], run_attempt=github["runAttempt"], max_bytes=EVIDENCE_BYTES,
        max_members=EVIDENCE_MEMBERS, timeout_seconds=seconds)
    returned = shared_raw_ns()  # Only an actual complete public API return reaches this line.
    left(export_end)
    encrypted = output_snapshot(context.operation, github, export_end, expected_manifest=manifest)
    seal = {"schema": 1, "scope": SCOPE, "result": RESULT, "github": github, "source": context.source,
        "allocation": context.allocation, "operationIdentity": context.operation_identity, "account": context.account,
        "policySha256": POLICY_SHA256, "policyExpires": POLICY_EXPIRES, "qualificationSha256": qualification_hash,
        "evidenceSha256": digest(encoded(frozen)), "exportReturnedRawNs": returned, "stepStartedRawNs": context.started,
        "stepEndRawNs": context.step_end, "jobEndRawNs": context.job_end,
        "uploadEndRawNs": min(returned + UPLOAD_SECONDS * NS, context.job_end, context.policy_end), "encrypted": encrypted}
    seal_raw = encoded(seal)
    write_new(context.operation / "qualification-return.json", seal_raw)
    seal_hash = digest(seal_raw)
    output = context.output.emit({"qualificationSha256": seal_hash})
    step = {"schema": 1, "scope": SCOPE, "sealSha256": seal_hash, "commandFile": output,
            "outputCloseReturned": True, "intendedExitCode": 0, "returnedRawNs": shared_raw_ns()}
    left(context.step_end)
    write_new(context.operation / "step-return.json", encoded(step))
    return seal


def qualify():
    context = Qualification()
    try:
        prepare(context)
        prepare_fixture(context)
        suite_end = None
        for case in CASES:
            inputs = context.owner.prepare_case(case)
            inputs["fixtureSourceSha256"] = digest(context.fixture_source_raw)
            if suite_end is None:
                suite_end = min(inputs["caseStartNs"] + SUITE_SECONDS * NS,
                                context.step_end - (ABORT_SECONDS + FREEZE_SECONDS + EXPORT_SECONDS) * NS)
            require(inputs["caseEndNs"] <= suite_end, "SHARED_SUITE_ORIGINAL_END")
            directory = context.operation / "bridge/cases" / case
            write_new(directory / "case-input.json", encoded(inputs))
            outcome = context.owner.run_case(case, directory / "case-input.json")
            context.case_results.append(assess_case(context.owner, outcome, case))
            left(suite_end)
        finished = context.owner.finish()
        context.owner_finished = True
        left(suite_end)
        finish_export(context, finished)
        print("RESULT: PASS — four fixed synthetic native controls; productive/bootstrap/ordinary/Release qualification remains required")
        return 0
    except BaseException:
        if context.owner is not None and not context.owner_finished:
            # Exactly one shared exceptional-abort attempt. It never resumes a
            # case, rewrites a primary error, or makes an unexpected failure seal.
            try:
                context.owner.abort()
            except BaseException:
                pass
        raise
    finally:
        if context.output is not None:
            context.output.close()


SEAL_KEYS = frozenset(("schema", "scope", "result", "github", "source", "allocation", "operationIdentity", "account",
    "policySha256", "policyExpires", "qualificationSha256", "evidenceSha256", "exportReturnedRawNs", "stepStartedRawNs",
    "stepEndRawNs", "jobEndRawNs", "uploadEndRawNs", "encrypted"))


def validate_seal(seal, github, allocation, identity, now_ns):
    require(type(seal) is dict and set(seal) == SEAL_KEYS and type(seal["schema"]) is int and seal["schema"] == 1 and
            seal["scope"] == SCOPE and seal["result"] == RESULT and seal["github"] == github and
            seal["allocation"] == allocation and seal["operationIdentity"] == identity and
            seal["policySha256"] == POLICY_SHA256 and type(seal["policyExpires"]) is int and
            seal["policyExpires"] == POLICY_EXPIRES and
            all(type(seal[key]) is str and HASH.fullmatch(seal[key]) for key in ("qualificationSha256", "evidenceSha256")),
            "QUALIFICATION_SEAL")
    keys = ("exportReturnedRawNs", "stepStartedRawNs", "stepEndRawNs", "jobEndRawNs", "uploadEndRawNs")
    require(all(integer(seal[key]) for key in keys) and integer(now_ns) and
            allocation["startedMonotonicNs"] <= seal["stepStartedRawNs"] <= seal["exportReturnedRawNs"] <
            seal["stepEndRawNs"] <= seal["stepStartedRawNs"] + STEP_SECONDS * NS and
            seal["jobEndRawNs"] == allocation["startedMonotonicNs"] + JOB_SECONDS * NS and
            seal["exportReturnedRawNs"] <= now_ns < seal["uploadEndRawNs"] <=
            min(seal["exportReturnedRawNs"] + UPLOAD_SECONDS * NS, seal["jobEndRawNs"]), "ORIGINAL_SEAL_CLOCKS")
    require(seal["source"] == {"commit": github["source"], "tree": github["sourceTree"],
                               "status": "", "diffSha256": digest(b"")}, "SEAL_SOURCE")
    bridge.validate_account(seal["account"])
    return seal


def validate_command_return(record, seal_hash, key):
    require(type(record) is dict and set(record) == {"stat", "sha256", "closed"} and record["closed"] is True and
            type(record["stat"]) is list and len(record["stat"]) == 9 and
            all(type(value) is int for value in record["stat"]) and type(record["sha256"]) is str and
            HASH.fullmatch(record["sha256"]), "ORIGINAL_COMMAND_FILE_CLOSE")
    raw = (key + "=" + seal_hash + "\n").encode("ascii")
    require(record["sha256"] == digest(raw) and record["stat"][6] == len(raw), "ORIGINAL_COMMAND_FILE_BYTES")


def validate_artifact_return(env, seal_hash):
    require(env.get(PREFIX + "UPLOAD_ALLOWED") == seal_hash and env.get(PREFIX + "UPLOAD_OUTCOME") == "success" and
            type(env.get(PREFIX + "ARTIFACT_ID")) is str and NUMBER.fullmatch(env[PREFIX + "ARTIFACT_ID"]) and
            type(env.get(PREFIX + "ARTIFACT_DIGEST")) is str and HASH.fullmatch(env[PREFIX + "ARTIFACT_DIGEST"]),
            "ORIGINAL_UPLOAD_RETURN")
    return {"artifactId": env[PREFIX + "ARTIFACT_ID"], "artifactDigest": env[PREFIX + "ARTIFACT_DIGEST"]}


def upload_guard(*, after=False):
    env, started = dict(os.environ), shared_raw_ns()
    request, github = original_request(env)
    operation, identity = operation_paths(env)
    allocation_raw = read_file(operation / "allocation.json", FRAME_BYTES)
    allocation = parsed(allocation_raw)
    require(allocation_raw == encoded(allocation), "UPLOAD_ALLOCATION_ENCODING")
    job_end = validate_allocation(allocation, request, github, started, time.time_ns())
    require(env.get(PREFIX + "STEP_OUTCOME") == "success", "QUALIFIER_STEP_NOT_SUCCESSFUL")
    seal_hash = env.get(PREFIX + "QUALIFICATION_SHA256", "")
    require(type(seal_hash) is str and HASH.fullmatch(seal_hash), "QUALIFICATION_OUTPUT_HASH")
    seal_raw = read_file(operation / "qualification-return.json", STREAM_BYTES)
    seal = parsed(seal_raw, STREAM_BYTES)
    require(seal_raw == encoded(seal) and digest(seal_raw) == seal_hash, "ORIGINAL_SEAL_CHANGED")
    validate_seal(seal, github, allocation, identity, started)
    end = min(started + 60 * NS, job_end, seal["uploadEndRawNs"], started + POLICY_EXPIRES * NS - time.time_ns())
    left(end)
    require(bridge.account() == seal["account"] and
            repository_source(request, end, child_environment(operation)) == seal["source"], "UPLOAD_SOURCE_CHANGED")
    # Public policy bytes/time only. Never validate another Recipient, decrypt,
    # re-export, append evidence, or reconstruct a native owner in these Steps.
    validate_policy(read_file(ROOT / POLICY_PATH, 96 * 1024), time.time(), 0)
    step_raw = read_file(operation / "step-return.json", STREAM_BYTES)
    step = parsed(step_raw, STREAM_BYTES)
    require(step_raw == encoded(step) and type(step) is dict and set(step) == {"schema", "scope", "sealSha256", "commandFile",
            "outputCloseReturned", "intendedExitCode", "returnedRawNs"} and type(step["schema"]) is int and step["schema"] == 1 and
            step["scope"] == SCOPE and step["sealSha256"] == seal_hash and step["outputCloseReturned"] is True and
            type(step["intendedExitCode"]) is int and step["intendedExitCode"] == 0 and integer(step["returnedRawNs"]) and
            seal["exportReturnedRawNs"] <= step["returnedRawNs"] < seal["stepEndRawNs"] and
            step["returnedRawNs"] <= started, "ORIGINAL_QUALIFIER_STEP_RETURN")
    validate_command_return(step["commandFile"], seal_hash, "qualificationSha256")
    require(output_snapshot(operation, github, end) == seal["encrypted"], "UPLOAD_ORIGINAL_BYTES_CHANGED")
    if not after:
        output = CommandFile(env)
        try:
            command = output.emit({"uploadAllowed": seal_hash})
        finally:
            output.close()
        write_new(operation / "before-upload.json", encoded({"schema": 1, "scope": SCOPE, "sealSha256": seal_hash,
            "encryptedSha256": digest(encoded(seal["encrypted"])), "commandFile": command,
            "returnedRawNs": shared_raw_ns(), "outsideCiphertext": True}))
    else:
        before_raw = read_file(operation / "before-upload.json", STREAM_BYTES)
        before = parsed(before_raw, STREAM_BYTES)
        require(before_raw == encoded(before) and type(before) is dict and set(before) == {"schema", "scope", "sealSha256",
                "encryptedSha256", "commandFile", "returnedRawNs", "outsideCiphertext"} and
                type(before["schema"]) is int and before["schema"] == 1 and before["scope"] == SCOPE and
                before["sealSha256"] == seal_hash and before["encryptedSha256"] == digest(encoded(seal["encrypted"])) and
                before["outsideCiphertext"] is True and integer(before["returnedRawNs"]) and
                step["returnedRawNs"] <= before["returnedRawNs"] <= started, "ORIGINAL_BEFORE_UPLOAD")
        validate_command_return(before["commandFile"], seal_hash, "uploadAllowed")
        artifact = validate_artifact_return(env, seal_hash)
        write_new(operation / "after-upload.json", encoded({"schema": 1, "scope": SCOPE, "sealSha256": seal_hash,
            "artifact": artifact, "github": github, "retentionDays": 14, "outsideCiphertext": True,
            "remoteReadbackRequired": True, "returnedRawNs": shared_raw_ns()}))
        print("RESULT: PASS — exact encrypted qualifier set uploaded; independent GitHub/original-evidence readback still required")
    left(end)
    return 0


def main():
    os.umask(0o077)
    try:
        require(len(sys.argv) in (2, 3), "FIXED_COMMAND")
        command = sys.argv[1]
        if command in ("qualify", "before-upload", "after-upload"):
            require(len(sys.argv) == 2, "FIXED_COMMAND")
            return qualify() if command == "qualify" else upload_guard(after=command == "after-upload")
        if command == "_service":
            require(len(sys.argv) == 3, "FIXED_PRIVATE_SERVICE")
            return bridge.service(bridge.QUALIFICATION, physical(sys.argv[2]))
        if command == "_produce":
            require(len(sys.argv) == 3 and re.fullmatch(r"[1-9][0-9]{0,5}", sys.argv[2]) and
                    3 <= int(sys.argv[2]) <= 65535, "FIXED_PRIVATE_PRODUCER")
            return produce(int(sys.argv[2]))
        raise QualificationError("FIXED_COMMAND")
    except BaseException as error:
        if type(error) is QualificationError and re.fullmatch(r"[A-Z0-9_]{1,80}", str(error)):
            reason = str(error)
        elif isinstance(error, bridge.ContextError):
            reason = bridge.public_error(error)
        else:
            reason = "PRIVATE_FAILURE"
        print("P2PKIT_DEPENDENCY_CONTEXT_FAILURE|" + reason + "; no seal, retry, or qualification", file=sys.stderr)
        with contextlib.suppress(BaseException):
            hint = bridge.public_failure_hint(error)
            if hint is not None:
                print("P2PKIT_DEPENDENCY_CONTEXT_DIAGNOSTIC|" + hint, file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
