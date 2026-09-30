#!/usr/bin/env python3
"""Fixed direct Java diagnostic in the original hosted F/D/P/canonical context.

This is not dependency generation, synthetic context qualification, or the
Gradle/JUnit lifecycle gate. The unchanged fixture has the same eight modes and
deadlines. Only an original, known-closed command result can authorize encrypted
diagnostics; neither a PASS line nor a manufactured failure code can do so.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SCRIPT = "scripts/run-hosted-jmdns-startup.py"
WORKFLOW = ".github/workflows/audit-jmdns-startup-context.yml"
JOB = "jmdns_startup"
SCOPE = "DIRECT_JAVA_STARTUP_DIAGNOSTIC_V1"
FAILED_SCOPE = "DIRECT_JAVA_STARTUP_FAILED_PRODUCT_DIAGNOSTICS_V1"
PREFIX = "P2PKIT_JMDNS_STARTUP_"
REF = re.compile(r"refs/heads/work/release-foundation-dependency-context-startup-[A-Za-z0-9-]+\Z")
REQUEST_KEYS = frozenset(("source_sha", "source_tree"))
MODES = ("control", "failed_recovery", "shared_close", "close_wins", "recovery_wins",
         "responder_close", "callback_executor", "cleanup_retry")
PURPOSES = ("startup-prerequisites", "startup-slf4j-download", "startup-vendor-javac",
            "startup-fixture-javac", *("startup-" + mode for mode in MODES))
COMMAND_SECONDS = (300, 90, 90, 90, *(45 for _ in MODES))
NS, MIB = 1_000_000_000, 1024 * 1024
STREAM_LIMIT, RUNTIME_LIMIT, RUNTIME_FILES = 65536, 32 * MIB, 2000
JAVA_FILES = ("release", "bin/java", "bin/javac", "lib/server/libjvm.dylib",
              "lib/libnet.dylib", "lib/libjava.dylib", "lib/libjli.dylib", "lib/modules")
VENDOR = "library/p2p-transport-lan/vendor/jmdns"
VENDOR_TREE = "7462447fba6d8ca22ca4dfb96ed050407ff15a34"
FIXTURE = ("library/p2p-transport-lan/src/jvmTest/java/"
           "dev/p2pkit/transport/lan/internal/jmdns/impl/JmdnsCloseLifecycleFixture.java")
FIXTURE_BLOB = "e279cab7cdbbaefe9a1ad5714432b74d064c318b"
FIXTURE_SHA256 = "67ccfae9489718111a1abdd2a251541d4107575f6114e3e030d034e131659a4e"
FIXTURE_CLASS = "dev.p2pkit.transport.lan.internal.jmdns.impl.JmdnsCloseLifecycleFixture"
RESOURCE = "dev/p2pkit/transport/lan/internal/jmdns/version.properties"
DEPENDENCY_URL = "https://repo.maven.apache.org/maven2/org/slf4j/slf4j-api/2.0.7/slf4j-api-2.0.7.jar"
DEPENDENCY_SHA256 = "5d6298b93a1905c32cda6478808ac14c2d4a47e91535e53c41f7feeb85d946f4"
JVM_ARGUMENTS = ("-Xms16m", "-Xmx128m", "-XX:MaxMetaspaceSize=128m", "-XX:ActiveProcessorCount=2",
                 "-XX:+UseSerialGC", "-Dorg.slf4j.simpleLogger.defaultLogLevel=off")
FORBIDDEN_ENV = ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
                 "P2PKIT_JMDNS_FIXTURE_IPV4")


def module(name, relative):
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


# Reuse scope-neutral source, receipt, public-recipient, clock and file helpers.
# None of the old generator's public commands, prerequisites or guards is called.
maintenance = module("jmdns_startup_maintenance_primitives", "scripts/run-hosted-dependency-update.py")
bridge = module("hosted_dependency_update_context", "scripts/hosted_dependency_update_context.py")
encoded, parsed, digest = maintenance.encoded, maintenance.parsed, maintenance.digest
read_file, write_new = maintenance.read_file, maintenance.write_new
JOB_SECONDS, STEP_SECONDS = maintenance.JOB_SECONDS, maintenance.STEP_SECONDS
STOP_SECONDS, UPLOAD_SECONDS = maintenance.STOP_SECONDS, maintenance.UPLOAD_SECONDS
EXPORT_SECONDS, FINAL_RESERVE = maintenance.EXPORT_SECONDS, maintenance.FINAL_RESERVE
ENTRY_RESERVE = sum(COMMAND_SECONDS) + len(PURPOSES) * (STOP_SECONDS + maintenance.NATIVE_HEADROOM) + FINAL_RESERVE


class StartupError(RuntimeError):
    """Only fixed, non-secret reason codes may leave the private controller."""


def require(value, reason):
    if not value:
        raise StartupError(reason)


def request_data(request, env, event_inputs):
    require(type(request) is dict and set(request) == REQUEST_KEYS and
            all(type(value) is str and maintenance.SHA.fullmatch(value) for value in request.values()) and
            event_inputs == request, "REQUEST_FIELDS")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == maintenance.REPOSITORY and
            env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            env.get("GITHUB_JOB") == JOB and env.get("GITHUB_ACTOR") == maintenance.OWNER and
            env.get("GITHUB_ACTOR_ID") == maintenance.OWNER_ID and
            env.get("GITHUB_TRIGGERING_ACTOR") == maintenance.OWNER, "MANUAL_IDENTITY")
    ref = env.get("GITHUB_REF", "")
    require(REF.fullmatch(ref) and env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA") == request["source_sha"] and
            env.get("GITHUB_WORKFLOW_REF") == maintenance.REPOSITORY + "/" + WORKFLOW + "@" + ref and
            all(maintenance.NUMBER.fullmatch(env.get(key, "")) for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")),
            "SOURCE_IDENTITY")
    return {"repository": maintenance.REPOSITORY, "workflow": WORKFLOW, "job": JOB, "ref": ref,
            "source": request["source_sha"], "sourceTree": request["source_tree"], "runId": env["GITHUB_RUN_ID"],
            "runAttempt": env["GITHUB_RUN_ATTEMPT"], "actor": maintenance.OWNER, "actorId": maintenance.OWNER_ID,
            "triggeringActor": maintenance.OWNER}


def original_request(env):
    request = parsed(env[PREFIX + "REQUEST"].encode("utf-8"), 8192)
    event = parsed(read_file(bridge.physical(env["GITHUB_EVENT_PATH"]), 2 * MIB)[0], 2 * MIB)
    require(type(event) is dict, "EVENT_FIELDS")
    return request, request_data(request, env, event.get("inputs"))


def operation(env, github):
    require(sys.platform == "darwin" and platform.machine() == "arm64" and
            not any(name in env for name in maintenance.NATIVE_OWNER_ENV) and
            not any(env.get(name) for name in FORBIDDEN_ENV), "ORIGINAL_NATIVE_CONTEXT")
    bridge.account()  # Includes real/effective nonroot account and group admission.
    parent = bridge.physical(env[PREFIX + "OPERATION"])
    require(parent.parent == Path(env["RUNNER_TEMP"]).resolve(strict=True) and
            parent.name.startswith("p2pkit-jmdns-startup-"), "OPERATION_PATH")
    identity = bridge.private_directory(parent)
    raw = read_file(parent / "allocation.json", 8192)[0]
    allocation = parsed(raw, 8192)
    require(raw == encoded(allocation), "ALLOCATION_ENCODING")
    bridge.validate_allocation(bridge.STARTUP, allocation, github, maintenance.shared_raw_ns(), time.time_ns())
    require(allocation["startedEpochNs"] < (bridge.POLICY_EXPIRES - JOB_SECONDS) * NS, "POLICY_ENTRY_CUTOFF")
    return parent, allocation, identity


def budget(allocation, step_started, reserve, *, returned_ns=None):
    # Identical job/Step/policy/final-return envelopes; never start a fresh one.
    maintenance.generation_budget(allocation, step_started, reserve, returned_ns=returned_ns)


def command_reserve(index):
    require(type(index) is int and 0 <= index < len(PURPOSES), "COMMAND_INDEX")
    return sum(COMMAND_SECONDS[index:]) + (len(PURPOSES) - index) * (
        STOP_SECONDS + maintenance.NATIVE_HEADROOM) + FINAL_RESERVE


def expected_modes(command_count, *, failed):
    require(type(command_count) is int and type(failed) is bool and
            (1 <= command_count <= len(PURPOSES) if failed else command_count == len(PURPOSES)),
            "COMMAND_RETURN_ROSTER")
    return {mode: ("PASS" if not failed or index + 5 < command_count else
                   "FAIL" if index + 5 == command_count else "NOT_RUN") for index, mode in enumerate(MODES)}


def fixed_commands(java_bin, runtime, sources):
    """Fixed argv DATA, not an input-driven command, mode or timeout interface."""
    require(isinstance(java_bin, Path) and java_bin.is_absolute() and ".." not in java_bin.parts and
            isinstance(runtime, Path) and runtime.is_absolute() and ".." not in runtime.parts and
            runtime != ROOT and ROOT not in runtime.parents and runtime not in ROOT.parents and
            type(sources) is list and len(sources) == 60 and all(type(name) is str for name in sources) and
            len(set(sources)) == 60 and sources == sorted(sources) and
            all(name.startswith(VENDOR + "/src/main/java/") and name.endswith(".java") and
                ".." not in Path(name).parts for name in sources), "FIXED_COMMAND_INPUTS")
    vendor, fixture, resources = (runtime / name for name in ("vendor", "fixture", "resources"))
    dependency = runtime / "slf4j-api-2.0.7.jar"
    compiler = [str(java_bin / "javac"), "-J-Xmx256m", "-J-XX:ActiveProcessorCount=2"]
    classpath = os.pathsep.join(map(str, (fixture, vendor, resources, dependency)))
    return [
        [maintenance.PYTHON, "-I", "-B", "-S", str(ROOT / SCRIPT), "_prerequisites"],
        ["/usr/bin/curl", "--disable", "--fail", "--silent", "--show-error", "--proto", "=https", "--tlsv1.2",
         "--connect-timeout", "15", "--max-time", "60", "--max-filesize", "1048576", "--output", str(dependency),
         DEPENDENCY_URL],
        [*compiler, "--release", "8", "-encoding", "UTF-8", "-classpath", str(dependency), "-d", str(vendor),
         *(str(ROOT / name) for name in sources)],
        [*compiler, "--release", "17", "-encoding", "UTF-8", "-classpath", os.pathsep.join(map(str, (vendor, dependency))),
         "-d", str(fixture), str(ROOT / FIXTURE)],
        *[[str(java_bin / "java"), *JVM_ARGUMENTS, "-cp", classpath, FIXTURE_CLASS, mode] for mode in MODES],
    ]


class CommandFile:
    """One original F descriptor, never passed to D/P or reconstructed by DATA."""

    def __init__(self, env):
        self.path = bridge.physical(env["GITHUB_OUTPUT"])
        require(Path(env["RUNNER_TEMP"]).resolve(strict=True) in self.path.parents and ROOT not in self.path.parents,
                "OUTPUT_PATH")
        self.fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        self.closed, self.emitted = False, False
        try:
            self.before = self.stamp(os.fstat(self.fd))
            require(self.before == self.stamp(self.path.lstat()) and self.before[6] == 0, "OUTPUT_IDENTITY")
        except BaseException:
            self.close()
            raise

    @staticmethod
    def stamp(info):
        maintenance.command_file_identity(info)
        require(0 <= info.st_size <= 1024, "OUTPUT_BOUND")
        return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink,
                info.st_size, info.st_mtime_ns, info.st_ctime_ns]

    def emit(self, key, value):
        require(not self.closed and not self.emitted and key in ("successSha256", "failedProductSha256") and
                type(value) is str and maintenance.HASH.fullmatch(value) and
                self.before == self.stamp(os.fstat(self.fd)) == self.stamp(self.path.lstat()) and
                str(self.path) == os.environ.get("GITHUB_OUTPUT"), "OUTPUT_BINDING")
        raw = (key + "=" + value + "\n").encode("ascii")
        require(os.write(self.fd, raw) == len(raw), "OUTPUT_SHORT")
        os.fsync(self.fd)
        after = self.stamp(os.fstat(self.fd))
        require(after == self.stamp(self.path.lstat()) and after[:6] == self.before[:6] and
                after[6] == len(raw) and read_file(self.path, 1024)[0] == raw, "OUTPUT_CHANGED")
        self.emitted = True
        self.close()
        return {"stat": after, "sha256": digest(raw), "closed": self.closed}

    def close(self):
        if not self.closed:
            os.close(self.fd)
            self.closed = True


def tool_file(path, maximum, *, capture=False):
    """Bound actual installed JDK bytes, allowing root or the admitted user."""
    path = bridge.physical(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        before = os.fstat(stream.fileno())
        stamp = lambda value: [value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid,
                               value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns]
        require(stat.S_ISREG(before.st_mode) and before.st_uid in (0, os.getuid()) and before.st_nlink == 1 and
                not before.st_mode & 0o022 and 0 < before.st_size <= maximum and
                (not capture or maximum <= STREAM_LIMIT), "JDK_FILE_BOUND")
        checksum, size, contents = hashlib.sha256(), 0, bytearray()
        while True:
            block = stream.read(min(MIB, maximum + 1 - size))
            if not block:
                break
            size += len(block)
            require(size <= maximum, "JDK_FILE_BOUND")
            checksum.update(block)
            if capture:
                contents.extend(block)
        require(size == before.st_size and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()),
                "JDK_FILE_CHANGED")
    return {"path": str(path), "stat": stamp(before), "bytes": size, "sha256": checksum.hexdigest()}, bytes(contents)


def tool_snapshot(context):
    values, total = {}, 0
    for major, variable in ((17, "JAVA_HOME"), (21, "P2PKIT_AUDIT_JDK21")):
        original = Path(os.environ[variable])
        require(original.is_absolute(), "JDK_HOME_PATH")
        home = original.resolve(strict=True)
        require(str(home) in context["javaHomes"] and home.is_dir(), "JDK_HOME_NOT_ADMITTED")
        files, release = {}, None
        for relative in JAVA_FILES:
            files[relative], raw = tool_file(home / relative, STREAM_LIMIT if relative == "release" else 256 * MIB,
                                             capture=relative == "release")
            total += files[relative]["bytes"]
            require(total <= 1024 * MIB, "JDK_TOTAL_BOUND")
            if relative == "release":
                release = raw.decode("utf-8")
                require(re.search(r'^JAVA_VERSION="' + str(major) + r'(?:[.\-+][^"\r\n]*)?"$', release, re.M),
                        "JDK_RELEASE_VERSION")
        require(all(os.access(home / "bin" / name, os.X_OK) for name in ("java", "javac")), "JDK_EXECUTABLE")
        values[str(major)] = {"requestedHome": str(original), "home": str(home), "files": files, "release": release}
    require(values["17"]["home"] != values["21"]["home"], "JDK_HOMES_NOT_DISTINCT")
    return values


def prerequisites():
    """Fixed canonical child: tool queries only; no SDK or build preparation."""
    require(sys.platform == "darwin" and platform.machine() == "arm64" and
            all(os.environ.get(name) for name in maintenance.NATIVE_OWNER_ENV) and
            not any(os.environ.get(name) for name in FORBIDDEN_ENV) and
            os.environ.get("DEVELOPER_DIR") == "/Applications/Xcode_26.5.app/Contents/Developer", "PREREQUISITE_CONTEXT")
    runner = module("jmdns_startup_prerequisite_executor", "scripts/run-audit-command.py")
    state, context = runner.context_at(os.environ["P2PKIT_AUDIT_STATE_DIR"])
    require(context["root"] == str(ROOT) and context["host"] == "macos-arm64", "PREREQUISITE_SOURCE")
    before, results = tool_snapshot(context), {}
    queries = []
    for major in (17, 21):
        home = Path(before[str(major)]["home"])
        queries += [("java" + str(major), [str(home / "bin/java"), "-XshowSettings:properties", "-version"]),
                    ("javac" + str(major), [str(home / "bin/javac"), "-version"])]
    queries.append(("xcode", ["/usr/bin/xcodebuild", "-version"]))
    for name, argv in queries:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=45, check=False)
        require(result.returncode == 0 and len(result.stdout) + len(result.stderr) <= STREAM_LIMIT,
                "TOOL_QUERY_FAILED")
        results[name] = {"argv": argv, "stdout": result.stdout.decode("utf-8"), "stderr": result.stderr.decode("utf-8")}
    for major in (17, 21):
        value = results["java" + str(major)]
        text = value["stdout"] + value["stderr"]
        require(re.search(r'\bversion "' + str(major) + r'\.', text) and
                re.findall(r"^\s*os\.arch = ([^\r\n]+)$", text, re.M) in (["aarch64"], ["arm64"]),
                "JAVA_RUNTIME_IDENTITY")
        homes = re.findall(r"^\s*java\.home = ([^\r\n]+)$", text, re.M)
        require(len(homes) == 1 and str(Path(homes[0]).resolve(strict=True)) == before[str(major)]["home"],
                "JAVA_RUNTIME_HOME")
        compiler = results["javac" + str(major)]
        require(re.fullmatch(r"javac " + str(major) + r"\.[^\r\n]+\n", compiler["stdout"] + compiler["stderr"]),
                "JAVAC_VERSION")
    require(results["xcode"]["stdout"].splitlines()[0] == "Xcode 26.5" and tool_snapshot(context) == before,
            "TOOL_IDENTITY_CHANGED")
    print(encoded({"schema": 1, "scope": SCOPE, "source": context["source"], "state": str(state),
                   "jdkFilesSha256": digest(encoded(before)), "queries": results}).decode("ascii"), end="")


def validate_dependency_pin(raw):
    require(type(raw) is bytes and 0 < len(raw) <= maintenance.FILE_LIMIT, "DEPENDENCY_METADATA_BOUND")
    pins = ET.fromstring(raw).findall(
        "./v:components/v:component[@group='org.slf4j'][@name='slf4j-api'][@version='2.0.7']/"
        "v:artifact[@name='slf4j-api-2.0.7.jar']/v:sha256", {"v": maintenance.VERIFICATION_NAMESPACE})
    require([pin.get("value") for pin in pins] == [DEPENDENCY_SHA256], "DEPENDENCY_SOURCE_PIN")


def source_inputs(runner, roster):
    sources = sorted(name for name in roster if name.startswith(VENDOR + "/src/main/java/"))
    require(len(sources) == 60 and all(name.endswith(".java") for name in sources) and
            {ROOT / name for name in sources} == set(runner.regular_report_files(ROOT / VENDOR / "src/main/java", [0])),
            "VENDOR_SOURCE_ROSTER")
    resource = VENDOR + "/src/main/resources/" + RESOURCE
    require(runner.regular_report_files(ROOT / VENDOR / "src/main/resources", [0]) == [ROOT / resource],
            "VENDOR_RESOURCE_ROSTER")
    require(runner.git(ROOT, "rev-parse", "HEAD:" + VENDOR).decode("ascii").strip() == VENDOR_TREE and
            roster[FIXTURE]["gitBlob"] == FIXTURE_BLOB and roster[FIXTURE]["sha256"] == FIXTURE_SHA256,
            "REVIEWED_JAVA_SOURCE_CHANGED")
    verification = "gradle/verification-metadata.xml"
    validate_dependency_pin(read_file(ROOT / verification)[0])
    names = [*sources, resource, FIXTURE, verification, VENDOR + "/PROVENANCE.json", VENDOR + "/NOTICE.txt",
             VENDOR + "/MODIFICATIONS.txt", VENDOR + "/patches/410-lifecycle.patch",
             "library/p2p-transport-lan/build.gradle.kts",
             "library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JmdnsCloseLifecycleTest.kt",
             "gradlew", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties",
             SCRIPT, WORKFLOW, bridge.MODULE, "scripts/run-hosted-dependency-update.py", "scripts/run-audit-command.py",
             "scripts/audit_processes.py", "scripts/hosted_evidence.py", "scripts/hosted_evidence_primitives.py",
             "AGENTS.md", "CLAUDE.md", maintenance.POLICY_PATH]
    require(len(names) == len(set(names)) and all(name in roster for name in names), "INPUT_ROSTER")
    return {"files": {name: roster[name] for name in sorted(names)}, "vendorSources": sources, "resource": resource,
            "fixture": FIXTURE, "fixtureSha256": FIXTURE_SHA256, "vendorTree": VENDOR_TREE,
            "equivalentJavaInputs": {"sourceCommit": "ef0cafa040bc2470d592ef5183deb9e241e83718",
                                    "vendorTree": VENDOR_TREE, "fixtureBlob": FIXTURE_BLOB,
                                    "kotlinSocketRepairExecuted": False},
            "dependency": {"coordinate": "org.slf4j:slf4j-api:2.0.7", "url": DEPENDENCY_URL,
                           "sha256": DEPENDENCY_SHA256}}


def inventory(directory):
    """Finite, private byte/identity roster; generated outputs never enter ROOT."""
    files, directories, pending, total = {}, {}, [directory], 0
    while pending:
        current = pending.pop()
        relative = current.relative_to(directory).as_posix()
        directories[relative] = bridge.private_directory(current)
        for path in sorted(current.iterdir()):
            info = path.lstat()
            require(not path.is_symlink() and len(files) + len(directories) + len(pending) < RUNTIME_FILES,
                    "RUNTIME_MEMBER_BOUND")
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            else:
                require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600, "RUNTIME_FILE_TYPE")
                raw, record = read_file(path, RUNTIME_LIMIT)
                total += len(raw)
                require(total <= RUNTIME_LIMIT, "RUNTIME_BYTE_BOUND")
                files[path.relative_to(directory).as_posix()] = record
    return {"directories": directories, "files": files, "bytes": total}


def validate_transcript(mode, stdout, stderr):
    require(mode in MODES and type(stdout) is bytes and type(stderr) is bytes and
            len(stdout) + len(stderr) <= STREAM_LIMIT, "FIXTURE_OUTPUT_BOUND")
    transcript = stdout.decode("utf-8", errors="replace") + "\n" + stderr.decode("utf-8", errors="replace")
    require(transcript.splitlines().count("PASS mode=" + mode) == 1 and "FAIL mode=" not in transcript and
            "phase=fixture_rescue_begin" not in transcript, "FIXTURE_NATURAL_PASS")


def validate_launch_record(receipt, expected_argv):
    require(type(receipt) is dict and receipt.get("executedArgv") == expected_argv and
            type(receipt.get("productPid")) is int and receipt["productPid"] > 0, "ORIGINAL_LAUNCH_RECORD")


def startup_inputs(endpoint):
    raw = read_file(endpoint.operation / "startup-inputs.json")[0]
    require(digest(raw) == endpoint.inputs["startupInputsSha256"], "STARTUP_INPUT_CHANGED")
    value = parsed(raw)
    require(type(value) is dict and set(value) == {"schema", "scope", "request", "github", "allocation", "sourceBefore",
            "sourceRoster", "sourceInputs", "prefixCaptures", "policySha256", "stepStartedRawNs"} and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and
            value["policySha256"] == maintenance.POLICY_SHA256 and value["github"] == endpoint.inputs["github"] and
            value["request"] == {"source_sha": endpoint.repository_source["commit"],
                                 "source_tree": endpoint.repository_source["tree"]} and
            raw == encoded(value), "STARTUP_INPUT_FIELDS")
    allocation = read_file(endpoint.operation / "allocation.json", 8192)[0]
    require(allocation == encoded(value["allocation"]) and digest(allocation) == endpoint.inputs["allocationSha256"] and
            type(value["stepStartedRawNs"]) is int and
            value["allocation"]["startedMonotonicNs"] <= value["stepStartedRawNs"] < endpoint.deadline_ns <=
            value["stepStartedRawNs"] + STEP_SECONDS * NS, "STARTUP_INPUT_CLOCK")
    require(type(value["prefixCaptures"]) is dict and set(value["prefixCaptures"]) ==
            {"controller.stdout", "controller.stderr"}, "PREFIX_CAPTURE_ROSTER")
    for name, expected in value["prefixCaptures"].items():
        require(read_file(endpoint.operation / name, 256 * MIB)[1] == expected, "PREFIX_CAPTURE_CHANGED")
    return value


def retain_inputs(records, inputs):
    anchor = records / "inputs"
    anchor.mkdir(mode=0o700)
    for name, expected in inputs["files"].items():
        raw, actual = read_file(ROOT / name)
        require(actual == {key: expected[key] for key in actual}, "SOURCE_INPUT_CHANGED")
        target = anchor / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_new(target, raw)


def produce(fd):
    """P alone initializes and calls the unchanged original canonical executor."""
    endpoint = bridge.producer(bridge.STARTUP, fd)
    prepared = startup_inputs(endpoint)
    parent, request = endpoint.operation, prepared["request"]
    allocation, step_started = prepared["allocation"], prepared["stepStartedRawNs"]
    require(not any(name.startswith(("GITHUB_", "ACTIONS_")) or name in ("GH_TOKEN", "GITHUB_TOKEN")
                    for name in os.environ) and not any(os.environ.get(name) for name in FORBIDDEN_ENV),
            "PRODUCER_ENVIRONMENT")
    require(PURPOSES == bridge.STARTUP_PURPOSES, "COMMAND_ROSTER")
    runner = module("jmdns_startup_executor", "scripts/run-audit-command.py")
    with (parent / "producer.stdout").open("x", encoding="utf-8") as out, \
            (parent / "producer.stderr").open("x", encoding="utf-8") as err, \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        require(maintenance.clean_source(runner, ROOT, request["source_sha"], request["source_tree"]) ==
                prepared["sourceBefore"] and maintenance.source_roster(runner, ROOT) == prepared["sourceRoster"] and
                source_inputs(runner, prepared["sourceRoster"]) == prepared["sourceInputs"], "PREPARED_SOURCE_CHANGED")
        budget(allocation, step_started, ENTRY_RESERVE)
        runner.initialize(argparse.Namespace(root=str(ROOT), state=str(parent / "state"),
                                            expected_commit=request["source_sha"], host="macos-arm64"))
        state, context = runner.context_at(str(parent / "state"))
        records = state / "evidence/startup"
        records.mkdir(mode=0o700)
        write_new(records / "startup-inputs.json", encoded(prepared))
        write_new(records / "canonical-context.json", read_file(state / "context.json")[0])
        write_new(records / "gradle-resource-policy.properties", read_file(state / "gradle-home/gradle.properties")[0])
        retain_inputs(records, prepared["sourceInputs"])
        tools = tool_snapshot(context)
        write_new(records / "jdk-before.json", encoded(tools))
        producer_identity = endpoint.identity_record()
        entry = {"schema": 1, "scope": SCOPE, "case": "STARTUP", "binding": endpoint.binding,
                 "caseInputSha256": endpoint.input_sha256, "contextSha256": digest(read_file(state / "context.json")[0]),
                 "contextId": context["id"], "sourceCommit": request["source_sha"], "sourceTree": request["source_tree"],
                 "gradlePolicySha256": context["gradlePropertiesSha256"], "producerIdentity": producer_identity,
                 "enteredMonotonicNs": maintenance.shared_raw_ns()}
        write_new(endpoint.canonical_entry_path, encoded(entry))
        endpoint.ready(endpoint.canonical_entry_path)
        runtime = records / "runtime"
        runtime.mkdir(mode=0o700)
        vendor_classes, fixture_classes, resources = (runtime / name for name in ("vendor", "fixture", "resources"))
        for directory in (vendor_classes, fixture_classes, resources):
            directory.mkdir(mode=0o700)
        resource = resources / RESOURCE
        resource.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_new(resource, read_file(ROOT / prepared["sourceInputs"]["resource"])[0])
        dependency = runtime / "slf4j-api-2.0.7.jar"
        commands = fixed_commands(Path(tools["17"]["home"]) / "bin", runtime,
                                  prepared["sourceInputs"]["vendorSources"])
        write_new(records / "command-plan.json", encoded({"scope": SCOPE, "commands": [
            {"purpose": purpose, "argv": argv, "seconds": seconds, "stopSeconds": STOP_SECONDS}
            for purpose, argv, seconds in zip(PURPOSES, commands, COMMAND_SECONDS)], "readyMillis": 10000,
            "qualification": "NOT_PERFORMED", "startupPrimitives": "NOT_ENABLED"}))
        returns, failed, frozen = [], None, None
        modes = {mode: "NOT_RUN" for mode in MODES}
        try:
            for index, (purpose, argv, seconds) in enumerate(zip(PURPOSES, commands, COMMAND_SECONDS)):
                budget(allocation, step_started, command_reserve(index))
                require(tool_snapshot(context) == tools, "JDK_INPUT_CHANGED")
                if frozen is not None:
                    require(inventory(runtime) == frozen, "RUNTIME_INPUT_CHANGED")
                if index >= 4:
                    modes[MODES[index - 4]] = "ATTEMPTED_PENDING_RECEIPT"
                receipt, receipt_hash = maintenance.owned_command(runner, parent, context, purpose, argv, seconds,
                                                                 command_returns=returns)
                validate_launch_record(receipt, argv)
                require(tool_snapshot(context) == tools, "JDK_INPUT_CHANGED")
                if index == 1:
                    data = read_file(dependency, MIB)[0]
                    require(data and digest(data) == DEPENDENCY_SHA256, "DEPENDENCY_HASH")
                if index == 3:
                    frozen = inventory(runtime)
                    require(any(name.startswith("vendor/") and name.endswith(".class") for name in frozen["files"]) and
                            "fixture/" + FIXTURE_CLASS.replace(".", "/") + ".class" in frozen["files"], "COMPILED_CLASSES")
                    write_new(records / "runtime-before-modes.json", encoded(frozen))
                if index >= 4:
                    mode = MODES[index - 4]
                    after = inventory(runtime)
                    write_new(records / ("runtime-after-" + mode + ".json"), encoded(after))
                    require(after == frozen, "RUNTIME_INPUT_CHANGED")
                    evidence = state / "evidence" / receipt["id"]
                    stdout = read_file(evidence / "product.stdout.log", STREAM_LIMIT)[0]
                    stderr = read_file(evidence / "product.stderr.log", STREAM_LIMIT)[0]
                    validate_transcript(mode, stdout, stderr)
                    modes[mode] = "PASS"
                write_new(records / ("command-" + str(index) + ".json"), encoded({"purpose": purpose,
                    "invocationId": receipt["id"], "receiptSha256": receipt_hash, "productPid": receipt["productPid"],
                    "nativeIdentity": "ORIGINAL_CANONICAL_RECEIPT", "returnedRawNs": returns[-1]["returnedRawNs"]}))
        except maintenance.ClosedProductFailure as original:
            # Only the original execute return with successful stop/native/source/
            # stream/receipt closure can enter this branch. Never synthesize code1
            # for an invalid PASS transcript, changed input, timeout or UNKNOWN.
            require(returns and len(returns) <= len(commands), "COMMAND_RETURN_ROSTER")
            validate_launch_record(original.receipt, commands[len(returns) - 1])
            failed = original
            if len(returns) >= 5:
                modes[MODES[len(returns) - 5]] = "FAIL"
        require(returns and modes == expected_modes(len(returns), failed=failed is not None), "COMMAND_RETURN_ROSTER")
        returned_ns = returns[-1]["returnedRawNs"]
        budget(allocation, step_started, FINAL_RESERVE, returned_ns=returned_ns)
        require(tool_snapshot(context) == tools, "JDK_INPUT_CHANGED")
        after = inventory(runtime)
        require(frozen is None or after == frozen, "RUNTIME_INPUT_CHANGED")
        write_new(records / "runtime-final.json", encoded(after))
        write_new(records / "jdk-after.json", encoded(tools))
        require(maintenance.clean_source(runner, ROOT, request["source_sha"], request["source_tree"]) ==
                prepared["sourceBefore"] and maintenance.source_roster(runner, ROOT) == prepared["sourceRoster"],
                "SOURCE_CHANGED")
        result = {"schema": 1, "scope": SCOPE, "request": request, "github": prepared["github"],
                  "result": "DIRECT_JAVA_MODES_PASSED" if failed is None else "CLOSED_FAILED_PRODUCT",
                  "modes": modes, "commands": returns, "productExitCode": 0 if failed is None else failed.code,
                  "gradleJunitQualification": "NOT_PERFORMED", "kotlinSocketRepairExecuted": False,
                  "runtimeInventorySha256": digest(encoded(after)), "jdkInventorySha256": digest(encoded(tools)),
                  "policySha256": maintenance.POLICY_SHA256}
        write_new(records / "diagnostic-result.json", encoded(result))
        for stream in (out, err):
            stream.flush()
            os.fsync(stream.fileno())
    require(out.closed and err.closed, "PRODUCER_CAPTURE_NOT_CLOSED")
    captures = {}
    for name in ("producer.stdout", "producer.stderr"):
        raw, captures[name] = read_file(parent / name, 256 * MIB)
        write_new(records / name, raw)
    write_new(records / "producer-capture-return.json", encoded({"schema": 1, "scope": SCOPE,
        "binding": endpoint.binding, "files": captures, "writerClosed": True, "closedRawNs": maintenance.shared_raw_ns()}))
    budget(allocation, step_started, EXPORT_SECONDS + UPLOAD_SECONDS, returned_ns=returned_ns)
    write_new(endpoint.producer_result_path, encoded({"schema": 1, "scope": SCOPE, "case": "STARTUP",
        "binding": endpoint.binding, "caseInputSha256": endpoint.input_sha256,
        "canonicalEntrySha256": digest(read_file(endpoint.canonical_entry_path)[0]), "producerIdentity": producer_identity,
        "commands": returns, "code": result["productExitCode"],
        "disposition": "SUCCESS" if failed is None else "CLOSED_FAILED_PRODUCT", "completedRawNs": maintenance.shared_raw_ns()}))
    return endpoint.complete(endpoint.producer_result_path)


def output_snapshot(parent, failed):
    group = "failed-encrypted" if failed else "encrypted"
    outputs = parent / "outputs"
    require(bridge.private_directory(outputs) and set(path.name for path in outputs.iterdir()) == {group},
            "OUTPUT_GROUP_ROSTER")
    directory = outputs / group
    bridge.private_directory(directory)
    require(set(path.name for path in directory.iterdir()) == set(maintenance.ENCRYPTED_FILES), "OUTPUT_FILE_ROSTER")
    return {group + "/" + name: read_file(directory / name, 576 * MIB)[1] for name in maintenance.ENCRYPTED_FILES}


def run():
    env, step_started = dict(os.environ), maintenance.shared_raw_ns()
    request, github = original_request(env)
    parent, allocation, operation_identity = operation(env, github)
    require(time.time_ns() < (bridge.POLICY_EXPIRES - JOB_SECONDS) * NS, "POLICY_ENTRY_CUTOFF")
    budget(allocation, step_started, ENTRY_RESERVE)
    require(ROOT == Path(env["GITHUB_WORKSPACE"]).resolve(strict=True) / "controller" and
            ROOT not in parent.parents and parent not in ROOT.parents, "CHECKOUT_TOPOLOGY")
    for name in ("home", "tmp", "konan", "android-user", "crypto", "outputs"):
        (parent / name).mkdir(mode=0o700)
    for name in ("config", "cache", "gnupg", "gh"):
        (parent / "home" / name).mkdir(mode=0o700)
    safe_environment = maintenance.child_environment(env, parent)
    output, owner = CommandFile(env), None
    try:
        with maintenance.environment(safe_environment):
            runner = module("jmdns_startup_foreground_executor", "scripts/run-audit-command.py")
            exporter = module("jmdns_startup_hosted_evidence", "scripts/hosted_evidence.py")
            with (parent / "controller.stdout").open("x", encoding="utf-8") as out, \
                    (parent / "controller.stderr").open("x", encoding="utf-8") as err, \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                source = maintenance.clean_source(runner, ROOT, request["source_sha"], request["source_tree"])
                roster = maintenance.source_roster(runner, ROOT)
                require(not maintenance.ignored_outputs(runner, ROOT), "FRESH_CHECKOUT_OUTPUTS")
                inputs = source_inputs(runner, roster)
                policy = maintenance.policy_data(read_file(ROOT / maintenance.POLICY_PATH, 96 * 1024)[0],
                                                 time.time(), ENTRY_RESERVE)
                key = parent / "recipient-public.asc"
                write_new(key, policy["recipient"]["publicKey"].encode("ascii"))
                recipient = exporter.validate_recipient(key, maintenance.FINGERPRINT, parent / "crypto")
                require(recipient.fingerprint == maintenance.FINGERPRINT and
                        recipient.encryption_fingerprint == maintenance.ENCRYPTION_FINGERPRINT and
                        recipient.key_sha256 == maintenance.KEY_SHA256 and recipient.expires_at == maintenance.KEY_EXPIRES,
                        "VALIDATED_PUBLIC_RECIPIENT")
                for stream in (out, err):
                    stream.flush()
                    os.fsync(stream.fileno())
            require(out.closed and err.closed, "PREFIX_CAPTURE_NOT_CLOSED")
            prefixes = {name: read_file(parent / name, 256 * MIB)[1] for name in ("controller.stdout", "controller.stderr")}
            prepared = {"schema": 1, "scope": SCOPE, "request": request, "github": github, "allocation": allocation,
                        "sourceBefore": source, "sourceRoster": roster, "sourceInputs": inputs, "prefixCaptures": prefixes,
                        "policySha256": maintenance.POLICY_SHA256, "stepStartedRawNs": step_started}
            prepared_raw = encoded(prepared)
            write_new(parent / "startup-inputs.json", prepared_raw)
        # Restore the original real F environment. Never hand it or Recipient to P.
        owner = bridge.Foreground(bridge.STARTUP, parent, allocation, step_started_ns=step_started)
        case = owner.prepare_case("STARTUP")
        case["startupInputsSha256"] = digest(prepared_raw)
        case_path = parent / "bridge/cases/STARTUP/case-input.json"
        write_new(case_path, encoded(case))
        outcome = owner.run_case("STARTUP", case_path)
        code, disposition = owner.production_result(outcome)
        producer_raw = read_file(case_path.parent / "producer-result.json")[0]
        producer = parsed(producer_raw)
        require(digest(producer_raw) == outcome.record["producerResultSha256"] and producer["code"] == code and
                producer["disposition"] == disposition, "ORIGINAL_PRODUCER_RETURN")
        finished = owner.finish()
        failed = code != 0
        state, records = parent / "state", parent / "state/evidence/startup"
        final = producer["commands"][-1]
        returned_ns = final["returnedRawNs"]
        budget(allocation, step_started, EXPORT_SECONDS + UPLOAD_SECONDS, returned_ns=returned_ns)
        require(bridge.private_directory(parent) == operation_identity and
                read_file(parent / "startup-inputs.json")[0] == prepared_raw, "ORIGINAL_INPUT_CHANGED")
        for name, expected in prefixes.items():
            raw, actual = read_file(parent / name, 256 * MIB)
            require(actual == expected, "PREFIX_CAPTURE_CHANGED")
            write_new(records / name, raw)
        maintenance.retain_bridge_files(parent, records, finished)
        result = parsed(read_file(records / "diagnostic-result.json")[0])
        modes = expected_modes(len(producer["commands"]), failed=failed)
        runtime_final = read_file(records / "runtime-final.json")[0]
        jdk_final = read_file(records / "jdk-after.json")[0]
        require(type(result) is dict and set(result) == {"schema", "scope", "request", "github", "result", "modes",
                "commands", "productExitCode", "gradleJunitQualification", "kotlinSocketRepairExecuted",
                "runtimeInventorySha256", "jdkInventorySha256", "policySha256"} and
                type(result["schema"]) is int and result["schema"] == 1 and result["scope"] == SCOPE and result["request"] == request and
                result["github"] == github and result["commands"] == producer["commands"] and
                type(result["productExitCode"]) is int and result["productExitCode"] == code and result["modes"] == modes and
                result["result"] == ("CLOSED_FAILED_PRODUCT" if failed else "DIRECT_JAVA_MODES_PASSED") and
                result["gradleJunitQualification"] == "NOT_PERFORMED" and result["kotlinSocketRepairExecuted"] is False and
                result["runtimeInventorySha256"] == digest(runtime_final) and inventory(records / "runtime") == parsed(runtime_final) and
                result["jdkInventorySha256"] == digest(jdk_final) and
                result["policySha256"] == maintenance.POLICY_SHA256, "DIAGNOSTIC_RESULT_CHANGED")
        with maintenance.environment(safe_environment):
            require(maintenance.clean_source(runner, ROOT, request["source_sha"], request["source_tree"]) == source and
                    maintenance.source_roster(runner, ROOT) == roster, "SOURCE_CHANGED")
            budget(allocation, step_started, EXPORT_SECONDS + UPLOAD_SECONDS, returned_ns=returned_ns)
            group = "failed-encrypted" if failed else "encrypted"
            manifest = exporter.export_encrypted(state / "evidence", parent / "outputs" / group, recipient,
                source_commit=request["source_sha"], source_tree=request["source_tree"],
                run_id=github["runId"], run_attempt=github["runAttempt"], timeout_seconds=EXPORT_SECONDS)
            exported_ns = maintenance.shared_raw_ns()
            require(manifest == parsed(read_file(parent / "outputs" / group / "manifest.json", MIB)[0]),
                    "EXPORT_MANIFEST_CHANGED")
            budget(allocation, step_started, UPLOAD_SECONDS)
            files = output_snapshot(parent, failed)
            seal = {"schema": 1, "scope": FAILED_SCOPE if failed else SCOPE, "request": request, "github": github,
                    "allocation": allocation, "operationIdentity": operation_identity, "account": bridge.account(),
                    "policySha256": maintenance.POLICY_SHA256, "startupInputsSha256": digest(prepared_raw),
                    "result": result["result"], "files": files,
                    "exportManifestSha256": digest(encoded(manifest)), "producerReturn":
                    "FAILED_PRODUCT_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN" if failed else
                    "SUCCESS_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN", "productExitCode": code,
                    "purpose": final["purpose"], "receiptSha256": final["receiptSha256"],
                    "stepStartedRawNs": step_started, "commandReturnedRawNs": returned_ns,
                    "exportReturnedRawNs": exported_ns, "uploadEndRawNs": min(exported_ns + UPLOAD_SECONDS * NS,
                        allocation["startedMonotonicNs"] + JOB_SECONDS * NS,
                        allocation["startedMonotonicNs"] + bridge.POLICY_EXPIRES * NS - allocation["startedEpochNs"])}
            seal_raw = encoded(seal)
            write_new(parent / ("startup-failed-product.json" if failed else "startup-success.json"), seal_raw)
        key = "failedProductSha256" if failed else "successSha256"
        command = output.emit(key, digest(seal_raw))
        write_new(parent / "step-return.json", encoded({"schema": 1, "scope": SCOPE, "sealSha256": digest(seal_raw),
            "commandFile": command, "intendedExitCode": code, "returnedRawNs": maintenance.shared_raw_ns()}))
        print("DIAGNOSTIC: " + ("original failed product; encrypted originals only; no retry or qualification" if failed else
                                "eight direct Java modes passed; Gradle/JUnit qualification NOT_PERFORMED"))
        return code
    except BaseException:
        if owner is not None and not owner.finished:
            owner.abort()
        raise
    finally:
        output.close()


SEAL_KEYS = frozenset(("schema", "scope", "request", "github", "allocation", "operationIdentity", "account", "policySha256", "startupInputsSha256",
    "result", "files", "exportManifestSha256", "producerReturn", "productExitCode", "purpose", "receiptSha256",
    "stepStartedRawNs", "commandReturnedRawNs", "exportReturnedRawNs", "uploadEndRawNs"))


def validate_return_data(value, env, request, github, allocation, identity, account, now, *, failed):
    """Closed DATA checks only; run() owns the actual exporter and native return."""
    require(env.get(PREFIX + "OUTCOME") == ("failure" if failed else "success") and
            not env.get(PREFIX + ("SUCCESS_SHA256" if failed else "FAILED_SHA256")), "ORIGINAL_STEP_OUTCOME")
    require(type(value) is dict and set(value) == SEAL_KEYS and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == (FAILED_SCOPE if failed else SCOPE) and value["request"] == request and
            value["github"] == github and value["allocation"] == allocation and value["operationIdentity"] == identity and
            value["account"] == account and value["policySha256"] == maintenance.POLICY_SHA256 and
            value["result"] == ("CLOSED_FAILED_PRODUCT" if failed else "DIRECT_JAVA_MODES_PASSED") and
            value["producerReturn"] == ("FAILED_PRODUCT_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN" if failed else
                                        "SUCCESS_AFTER_KNOWN_COMMAND_AND_EXPORT_RETURN") and
            type(value["productExitCode"]) is int and
            (1 <= value["productExitCode"] <= 123 if failed else value["productExitCode"] == 0) and
            value["purpose"] in (PURPOSES if failed else (PURPOSES[-1],)) and
            all(type(value[name]) is str and maintenance.HASH.fullmatch(value[name])
                for name in ("exportManifestSha256", "receiptSha256", "startupInputsSha256")), "RETURN_BINDING")
    clocks = ("stepStartedRawNs", "commandReturnedRawNs", "exportReturnedRawNs", "uploadEndRawNs")
    require(all(type(value[name]) is int and value[name] > 0 for name in clocks) and type(now) is int and
            allocation["startedMonotonicNs"] <= value["stepStartedRawNs"] <= value["commandReturnedRawNs"] <=
            value["exportReturnedRawNs"] <= now < value["uploadEndRawNs"] <=
            min(value["exportReturnedRawNs"] + UPLOAD_SECONDS * NS,
                allocation["startedMonotonicNs"] + JOB_SECONDS * NS,
                allocation["startedMonotonicNs"] + bridge.POLICY_EXPIRES * NS - allocation["startedEpochNs"]) and
            value["exportReturnedRawNs"] < value["stepStartedRawNs"] + STEP_SECONDS * NS and
            value["exportReturnedRawNs"] - value["commandReturnedRawNs"] <
            (maintenance.FINALIZE_SECONDS + EXPORT_SECONDS) * NS, "ORIGINAL_RETURN_CLOCKS")
    group = "failed-encrypted" if failed else "encrypted"
    require(type(value["files"]) is dict and set(value["files"]) ==
            {group + "/" + name for name in maintenance.ENCRYPTED_FILES}, "RETURN_FILE_ROSTER")
    return value


def validate_step_return(value, seal, seal_hash, *, failed):
    key = "failedProductSha256" if failed else "successSha256"
    require(type(value) is dict and set(value) == {"schema", "scope", "sealSha256", "commandFile", "intendedExitCode",
            "returnedRawNs"} and type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and
            value["sealSha256"] == seal_hash and type(value["intendedExitCode"]) is int and
            value["intendedExitCode"] == seal["productExitCode"] and type(value["returnedRawNs"]) is int and
            seal["exportReturnedRawNs"] <= value["returnedRawNs"] <
            min(seal["stepStartedRawNs"] + STEP_SECONDS * NS, seal["uploadEndRawNs"]), "ORIGINAL_STEP_RETURN")
    record = value["commandFile"]
    raw = (key + "=" + seal_hash + "\n").encode("ascii")
    require(type(record) is dict and set(record) == {"stat", "sha256", "closed"} and record["closed"] is True and
            type(record["stat"]) is list and len(record["stat"]) == 9 and
            all(type(item) is int for item in record["stat"]) and record["stat"][6] == len(raw) and
            record["sha256"] == digest(raw), "ORIGINAL_OUTPUT_CLOSE")


def guard_upload(*, after=False, failed=False):
    env = dict(os.environ)
    request, github = original_request(env)
    parent, allocation, identity = operation(env, github)
    expected = env.get(PREFIX + ("FAILED_SHA256" if failed else "SUCCESS_SHA256"), "")
    require(maintenance.HASH.fullmatch(expected), "RETURN_HASH")
    name, opposite = (("startup-failed-product.json", "startup-success.json") if failed else
                      ("startup-success.json", "startup-failed-product.json"))
    raw = read_file(parent / name, MIB)[0]
    require(digest(raw) == expected and not os.path.lexists(parent / opposite), "RETURN_EXCLUSIVITY")
    seal = parsed(raw, MIB)
    require(raw == encoded(seal), "RETURN_ENCODING")
    validate_return_data(seal, env, request, github, allocation, identity, bridge.account(), maintenance.shared_raw_ns(), failed=failed)
    maintenance.budget(allocation, 0 if after else UPLOAD_SECONDS)
    step = parsed(read_file(parent / "step-return.json", STREAM_LIMIT)[0], STREAM_LIMIT)
    validate_step_return(step, seal, expected, failed=failed)
    require(step["returnedRawNs"] <= maintenance.shared_raw_ns(), "STEP_RETURN_ORDER")
    with maintenance.environment(maintenance.child_environment(env, parent)):
        runner = module("jmdns_startup_upload_executor", "scripts/run-audit-command.py")
        maintenance.clean_source(runner, ROOT, request["source_sha"], request["source_tree"])
        prepared_raw = read_file(parent / "startup-inputs.json")[0]
        require(digest(prepared_raw) == seal["startupInputsSha256"], "UPLOAD_INPUT_CHANGED")
        prepared = parsed(prepared_raw)
        require(maintenance.source_roster(runner, ROOT) == prepared["sourceRoster"], "UPLOAD_SOURCE_CHANGED")
    files = output_snapshot(parent, failed)
    require(files == seal["files"], "UPLOAD_BYTES_CHANGED")
    group = "failed-encrypted" if failed else "encrypted"
    require(digest(read_file(parent / "outputs" / group / "manifest.json", MIB)[0]) == seal["exportManifestSha256"],
            "UPLOAD_MANIFEST_CHANGED")
    before_path = parent / ("before-failed-upload.json" if failed else "before-upload.json")
    if not after:
        write_new(before_path, encoded({"schema": 1, "scope": seal["scope"], "sealSha256": expected,
            "filesSha256": digest(encoded(files)), "returnedRawNs": maintenance.shared_raw_ns()}))
        print("DIAGNOSTIC: original closed export admitted; ciphertext and manifest only")
    else:
        before = parsed(read_file(before_path, STREAM_LIMIT)[0], STREAM_LIMIT)
        require(type(before) is dict and set(before) == {"schema", "scope", "sealSha256", "filesSha256", "returnedRawNs"} and
                type(before["schema"]) is int and before["schema"] == 1 and before["scope"] == seal["scope"] and
                before["sealSha256"] == expected and before["filesSha256"] == digest(encoded(files)) and
                type(before["returnedRawNs"]) is int and step["returnedRawNs"] <= before["returnedRawNs"] <=
                maintenance.shared_raw_ns(), "ORIGINAL_UPLOAD_GUARD")
        require(env.get(PREFIX + "UPLOAD_OUTCOME") == "success" and
                maintenance.NUMBER.fullmatch(env.get(PREFIX + "ARTIFACT_ID", "")) and
                maintenance.HASH.fullmatch(env.get(PREFIX + "ARTIFACT_DIGEST", "")), "ACTUAL_UPLOAD_RETURN")
        write_new(parent / ("after-failed-upload.json" if failed else "after-upload.json"), encoded({"schema": 1,
            "scope": seal["scope"], "sealSha256": expected, "artifactId": env[PREFIX + "ARTIFACT_ID"],
            "artifactDigest": env[PREFIX + "ARTIFACT_DIGEST"], "github": github, "retentionDays": 14,
            "outsideCiphertext": True, "remoteReadbackRequired": True, "returnedRawNs": maintenance.shared_raw_ns()}))
        print("DIAGNOSTIC: ciphertext upload returned; independent evidence review remains required; " +
              ("original product and job remain FAILED" if failed else "not Gradle/JUnit qualification"))
    require(maintenance.shared_raw_ns() < seal["uploadEndRawNs"], "UPLOAD_DEADLINE")
    return 0


def main():
    os.umask(0o077)
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "_service":
            return bridge.service(bridge.STARTUP, Path(sys.argv[2]))
        if len(sys.argv) == 3 and sys.argv[1] == "_produce":
            require(re.fullmatch(r"[1-9][0-9]{0,4}", sys.argv[2]) and 3 <= int(sys.argv[2]) <= 65535,
                    "PRODUCER_DESCRIPTOR")
            return produce(int(sys.argv[2]))
        require(len(sys.argv) == 2 and sys.argv[1] in ("run", "_prerequisites", "before-upload", "after-upload",
                                                    "before-failed-upload", "after-failed-upload"), "FIXED_COMMAND")
        command = sys.argv[1]
        if command == "run":
            return run()
        if command == "_prerequisites":
            prerequisites()
            return 0
        return guard_upload(after=command.startswith("after-"), failed="-failed-" in command)
    except BaseException as error:
        reason = str(error) if isinstance(error, (StartupError, maintenance.UpdateError)) and \
            re.fullmatch(r"[A-Z0-9_]{1,80}", str(error)) else "PRIVATE_FAILURE"
        if isinstance(error, bridge.ContextError):
            safe = bridge.public_error(error)
            if re.fullmatch(r"[A-Z0-9_/]{1,160}", safe):
                reason = safe
        print("DIAGNOSTIC: REFUSED — " + reason + "; preserve private originals; no retry or partial acceptance",
              file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
