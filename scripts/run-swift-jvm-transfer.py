#!/usr/bin/env python3
"""One real Swift UI/JVM CLI bidirectional secure-v2 transfer under the audit executor.

All compilation must finish first. This controller never builds, replaces the
protocol peer, injects consent, or signals numeric PIDs. The existing executor
owns descendant drain, same-home Gradle stop, source checks and final cleanup.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
TARGET = "p2pkit-sample-jvm-transfer-tests"
CASE = "SwiftJvmTransferUITests/testBidirectionalSecure204800ByteTransferWithJvmPeer()"
SIZE = 204800
MIB = 1024 * 1024
OWNERSHIP = ("P2PKIT_AUDIT_JOB_ID", "P2PKIT_AUDIT_OWNERSHIP_CHAIN", "P2PKIT_AUDIT_OWNERSHIP_DOMAINS",
             "P2PKIT_AUDIT_STATE_DIR", "GRADLE_USER_HOME")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_executor():
    # Reuse admission/path/source contracts, not another process-ownership engine.
    spec = importlib.util.spec_from_file_location("swift_jvm_audit_executor", ROOT / "scripts/run-audit-command.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def peer_target(document):
    """Accept the two documented xctestrun layouts, never guess a test target."""
    require(type(document) is dict, "xctestrun root is not a dictionary")
    if "TestConfigurations" in document:
        configurations = document["TestConfigurations"]
        require(type(configurations) is list and len(configurations) == 1,
                "Expected exactly one peer test configuration")
        configuration = configurations[0]
        require(type(configuration) is dict and configuration.get("IsEnabled", True) is True,
                "Peer test configuration is disabled or malformed")
        targets = configuration.get("TestTargets")
        require(type(targets) is list and len(targets) == 1, "Expected exactly one peer test target")
        target = targets[0]
        require(type(target) is dict and target.get("BlueprintName") == TARGET, "Wrong peer test target")
    else:
        names = [name for name in document if not name.startswith("__")]
        require(names == [TARGET], "Unexpected legacy xctestrun target set")
        target = document[TARGET]
    require(type(target) is dict and target.get("IsUITestBundle") is True, "Peer target is not a UI test bundle")
    require(all(type(target.get(name)) is str and target[name] for name in
                ("TestBundlePath", "TestHostPath", "UITargetAppPath")), "Missing prepared XCTest paths")
    require(not target.get("SkipTestIdentifiers"), "Prepared peer case has a skip selector")
    only = target.get("OnlyTestIdentifiers", [])
    require(only in ([], [CASE], [CASE.removesuffix("()")]), "Unexpected prepared test selector")
    return target


def inject_fixture(document, fixture, environment):
    target = peer_target(document)
    previous = target.setdefault("EnvironmentVariables", {})
    require(type(previous) is dict and all(type(k) is str and type(v) is str for k, v in previous.items()),
            "Malformed XCTest environment")
    added = {**{name: environment[name] for name in OWNERSHIP}, **fixture}
    require(all(key not in previous or previous[key] == value for key, value in added.items()),
            "Prepared XCTest environment conflicts with this invocation")
    previous.update(added)
    return target


def walk(value):
    if type(value) is dict:
        yield value
        for child in value.values():
            yield from walk(child)
    elif type(value) is list:
        for child in value:
            yield from walk(child)


def assess_case(objects):
    """Require the exact native method, not an empty run or unrelated green suite."""
    cases = []
    for document in objects:
        for target in walk(document):
            if target.get("_type", {}).get("_name") != "ActionTestableSummary":
                continue
            require(target.get("targetName", {}).get("_value") == TARGET, "Unexpected executed target")
            for case in walk(target.get("tests", {})):
                if case.get("_type", {}).get("_name") == "ActionTestMetadata":
                    cases.append((case.get("identifier", {}).get("_value"),
                                  case.get("testStatus", {}).get("_value")))
    require(cases == [(CASE, "Success")], "Exact Swift/JVM method did not execute once with Success")
    return {"identifier": TARGET + "/" + CASE, "status": "Success"}


def selected(rows, name, **fields):
    return [row for row in rows if row.get("eventName") == name and
            all(row.get(key) == value for key, value in fields.items())]


def connected_owner(rows, *, swift):
    connection_event, negotiation_event = "connection.state.changed", "protocol.secure_v2.negotiated"
    states = selected(rows, connection_event)
    connections = [row for row in states if row.get("currentState") == "Connected"]
    negotiated = selected(rows, negotiation_event)
    observations = 1 if swift else 2
    require(len(negotiated) == len(connections) == observations, "Unexpected endpoint connection/negotiation observations")
    keys = ("sdkSessionId", "connectionId", "peerId", "protocolVersion")
    identity = tuple(negotiated[0].get(key) for key in keys)
    require(all(type(value) is str and value for value in identity[:3]) and identity[3] == "secure-v2",
            "Secure connection lacks endpoint ownership/protocol identity")
    require(all(tuple(row.get(key) for key in keys) == identity for row in states + negotiated),
            "Endpoint connection/negotiation owner differs")
    require(all(row.get("currentState") == "secure-v2" and row.get("previousState") is None and
                row.get("outcome") == ("SUCCESS" if swift else None) and
                row.get("details", {}) == ({} if swift else {"feature": "file-commit-sha256-v1"})
                for row in negotiated), "Negotiation identity/result differs")
    require(all(row.get("outcome") == (None if swift else "SUCCESS") for row in connections),
            "Connected result differs")
    if swift:
        connected_at = states.index(connections[0])
        require(all(row.get("currentState") in ("Idle", "Connecting", "Handshaking") for row in states[:connected_at]) and
                all(row.get("currentState") == "Closed" for row in states[connected_at + 1:]),
                "Swift connection rearmed or reconnected")
    else:
        # Main.registerSession publishes its initial Connected snapshot, then
        # StateFlow immediately emits that same value. Each call records a
        # negotiation. These two observations must not hide a rearm/reconnect.
        lifecycle = [(row.get("eventName"), row.get("previousState"), row.get("currentState"), row.get("outcome"))
                     for row in rows if row.get("eventName") in (connection_event, negotiation_event)]
        initial = [(connection_event, None, "Connected", "SUCCESS"),
                   (negotiation_event, None, "secure-v2", None),
                   (connection_event, "Connected", "Connected", "SUCCESS"),
                   (negotiation_event, None, "secure-v2", None)]
        require(lifecycle in (initial, initial + [(connection_event, "Connected", "Closed", "CANCELLATION")]),
                "CLI observations are not its initial snapshot/StateFlow sequence with optional final Close")
    return identity[:2]


def transfer_evidence(rows, transfer_id, checksum, *, receiver, swift):
    owner = connected_owner(rows, swift=swift)
    direction = "RECEIVED" if receiver else "SENT"
    required = ["file.receiver.sha256" if receiver else "file.sender.sha256"]
    # The CLI receiver reports its terminal Completed through durable.committed;
    # unlike Swift it does not emit a second transfer.completed. Its sender's
    # terminal observer uses LOCAL direction; its prepared hash is SENT.
    if swift or not receiver:
        required.append("transfer.completed")
    if receiver:
        required += ["transfer.offer.received", "transfer.offer.accepted", "transfer.durable.committed"]
    evidence = []
    for name in required:
        matches = selected(rows, name, transferId=transfer_id)
        require(len(matches) == 1, "Missing/duplicate transfer-scoped " + name)
        row = matches[0]
        expected_direction = "LOCAL" if not swift and name == "transfer.completed" else direction
        require(tuple(row.get(key) for key in ("sdkSessionId", "connectionId")) == owner and
                row.get("payloadSizeBytes") == SIZE and row.get("direction") == expected_direction and
                row.get("protocolVersion") == "secure-v2", "Transfer source/owner/size/direction differs")
        if name.endswith(".sha256"):
            require(row.get("details", {}).get("sha256") == checksum, "Endpoint file SHA-256 differs")
        if name in ("transfer.completed", "transfer.durable.committed"):
            require(row.get("outcome") == "SUCCESS", "Non-success terminal transfer")
            expected_state = "durably-persisted" if swift and name == "transfer.durable.committed" else "Completed"
            require(row.get("currentState") == expected_state, "Unexpected terminal state")
        evidence.append(row)
    require(not any(row.get("transferId") == transfer_id and row.get("eventName") in
                    ("transfer.failed", "transfer.cancelled", "transfer.offer.rejected") for row in rows),
            "Transfer also recorded a failure/cancellation/rejection")
    return {"sdkSessionId": owner[0], "connectionId": owner[1], "events": evidence}


def pattern(multiplier, offset):
    return bytes((index * multiplier + offset) & 255 for index in range(SIZE))


class Experiment:
    def __init__(self, args):
        self.audit = load_executor()
        from audit_processes import ownership_domains
        self.state, self.context = self.audit.context_at(os.environ.get("P2PKIT_AUDIT_STATE_DIR", ""))
        require(self.context["host"] in ("macos-arm64", "macos-x64"), "Native macOS audit context required")
        domains = ownership_domains(os.environ.get(OWNERSHIP[1], ""), os.environ.get(OWNERSHIP[2], ""))
        require(domains and domains[-1]["job"] == self.context["id"] == os.environ.get(OWNERSHIP[0]) and
                domains[-1]["state"] == str(self.state) and domains[-1]["home"] == self.context["gradleHome"] ==
                os.environ.get("GRADLE_USER_HOME"), "Missing/mismatched active executor ownership")
        self.ownership_domain = dict(domains[-1])
        require(Path(self.context["root"]) == ROOT and self.audit.source_snapshot(ROOT) == self.context["source"],
                "Source differs from the admitted clean build")
        for key in ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
            require(not os.environ.get(key, "").strip(), "Inherited JVM option conflicts with bounded ownership: " + key)
        self.derived = Path(args.derived_data)
        require(self.derived == self.state / "work/swift-ui/DerivedData", "Use the existing owned Swift UI work root")
        self.audit.reject_symlinks(self.derived)
        require(self.derived.is_dir(), "Missing prepared DerivedData")
        require(re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", args.simulator),
                "An exact simulator UDID is required")
        self.udid = args.simulator
        self.directory = self.derived.parent / "jvm-transfer"
        self.audit.reject_symlinks(self.directory)
        self.directory.mkdir(mode=0o700, exist_ok=False)
        self.identity = self.directory.stat().st_dev, self.directory.stat().st_ino
        self.nonce = uuid.uuid4().hex
        self.name = "jvm-" + self.nonce + ".bin"
        self.home = self.directory / "home"
        self.home.mkdir(mode=0o700)
        self.cli, self.xcode, self.xctestrun = None, None, None
        self.inbox, self.received_identity = None, None
        self.deadline = time.monotonic() + 360
        self.last_resource = 0.0
        self.record = {"schema": 1, "source": self.context["source"], "nonce": self.nonce, "result": "FAIL",
                       "case": TARGET + "/" + CASE, "bytesPerDirection": SIZE, "commands": [], "resources": [],
                       "transfers": [], "cleanupErrors": [], "unresolvedChildren": [],
                       "limits": "Same-codebase JVM/Swift host-simulator integration, not independent #133, physical, "
                                 "hostile-network, process-death durability or professional crypto validation. "
                                 "Swift pins the CLI; CLI incoming peers retain the authenticated same-AppId development policy."}

    def read(self, path, limit=2 * MIB, missing=False):
        self.audit.reject_symlinks(path)
        try:
            with path.open("rb") as stream:
                require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "Nonregular evidence/file")
                data = stream.read(limit + 1)
        except FileNotFoundError:
            if missing:
                return b""
            raise
        require(len(data) <= limit, "Evidence/file exceeded its bound: " + path.name)
        return data

    def checksum(self, path, limit=512 * MIB):
        self.audit.reject_symlinks(path)
        require(path.is_file(), "Expected regular prepared artifact")
        return self.audit.file_digest(path, limit)

    def write(self, name, value):
        self.audit.write_new_json(self.directory / name, value)

    def guard(self):
        now = time.monotonic()
        require(now < self.deadline, "Integration exceeded 360 seconds")
        require(self.cli is None or self.cli.poll() is None, "JVM CLI exited before graceful quit")
        require(self.xcode is None or self.xcode.poll() in (None, 0), "Native XCTest failed")
        for name, limit in (("cli.stdout.log", 2 * MIB), ("cli.stderr.log", 2 * MIB), ("xcodebuild.log", 16 * MIB)):
            path = self.directory / name
            if path.exists():
                require(path.stat().st_size <= limit, "Log exceeds integration bound: " + name)
        if now - self.last_resource >= 10:
            free = shutil.disk_usage(self.directory).free
            self.record["resources"].append({"monotonicSeconds": now, "freeDiskBytes": free,
                                             "controllerPeakRssBytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
            self.last_resource = now
            require(free >= 2 * 1024 ** 3, "Less than 2GiB free during integration")

    def await_condition(self, description, predicate, seconds=30):
        end = min(self.deadline, time.monotonic() + seconds)
        while True:
            self.guard()
            result = predicate()
            if result:
                return result
            require(time.monotonic() < end, "Timeout: " + description)
            time.sleep(0.1)

    def output(self):
        return self.read(self.directory / "cli.stdout.log").decode("utf-8")

    def command(self, value, expression=None):
        self.guard()
        offset = len(self.output())
        self.record["commands"].append({"command": value, "monotonicSeconds": time.monotonic()})
        self.cli.stdin.write((value + "\n").encode())
        self.cli.stdin.flush()
        if expression:
            return self.await_condition(value.split(" ", 1)[0], lambda:
                                        re.search(expression, self.output()[offset:], re.M | re.S))
        return offset

    def events(self, swift=False, final=False):
        if swift:
            require(self.inbox is not None, "Simulator container is not bound")
            directory = self.inbox.parent.parent / "Library/Application Support/P2pKitTestDiagnostics"
            names = ["events.3.jsonl", "events.2.jsonl", "events.1.jsonl", "events.jsonl"]
        else:
            directory, names = self.directory, ["events.jsonl"]
            require(not list(directory.glob("events.jsonl.[0-9]*")), "Unexpected CLI rotation; completeness unproven")
        rows, originals = [], []
        for name in names:
            raw = self.read(directory / name, missing=True)
            if raw and not raw.endswith(b"\n"):
                require(not final, "Incomplete final diagnostic JSONL")
                raw = raw.rsplit(b"\n", 1)[0] + b"\n" if b"\n" in raw else b""
            for line in raw.splitlines():
                row = json.loads(line, object_pairs_hook=self.audit.unique_object)
                require(type(row) is dict, "Malformed diagnostic record")
                if row.get("testSessionId") != self.nonce:
                    require(swift, "CLI diagnostic session differs")
                    continue
                require(row.get("gitCommitSha") == self.context["expectedCommit"] and row.get("testId") == "SWIFT-JVM" and
                        row.get("platform") == ("ios" if swift else "jvm-cli"), "Runtime diagnostic source/test/platform differs")
                rows.append(row)
                originals.append(line)
        indexes = [row.get("index") for row in rows]
        require(all(type(index) is int for index in indexes) and len(set(indexes)) == len(indexes),
                "Missing/duplicate diagnostic event indexes")
        if final:
            require(rows, "No real diagnostics for this test session")
            if swift:
                with self.audit.new_file(self.directory / "swift-events.jsonl.log") as output:
                    output.write(b"\n".join(originals) + b"\n")
        return rows

    def entries(self, directory):
        self.audit.reject_symlinks(directory)
        if not directory.exists():
            return {}
        require(directory.is_dir(), "Expected receiver directory")
        result = {}
        for path in directory.iterdir():
            require(len(result) < 128, "Receiver directory exceeds bounded case scope")
            value = path.lstat()  # No reads/traversal of unrelated existing inbox contents.
            result[path.name] = (value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns)
        return result

    def verify_file(self, path, expected):
        raw = self.read(path, SIZE)
        require(len(raw) == SIZE and raw == expected, "Committed file differs from full 204800-byte pattern")
        return {"name": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    def jars(self):
        directory = ROOT / "samples/p2p-sample-desktop/build/install/p2p-sample-desktop/lib"
        self.audit.reject_symlinks(directory)
        names = sorted(directory.glob("*.jar"))
        require(1 <= len(names) <= 128, "Missing/excessive prebuilt CLI runtime jars")
        return directory, {path.name: self.checksum(path) for path in names}

    def native_output(self, name, command):
        self.guard()
        # No timeout-driven subprocess.run kill fallback. An unresponsive direct
        # child is recorded and left for the established executor's owned drain.
        path = self.directory / (name + ".log")
        with self.audit.new_file(path) as output, self.audit.new_file(self.directory / (name + ".stderr.log")) as errors:
            process = subprocess.Popen(command, stdout=output, stderr=errors, env=dict(os.environ))
            try:
                require(process.wait(timeout=30) == 0, "Native inspection failed: " + name)
            except BaseException:
                if process.poll() is None:
                    self.record["unresolvedChildren"].append({"kind": name, "pid": process.pid})
                raise
        return self.read(path, 16 * MIB).decode("utf-8")

    def executable_hash(self, directory):
        info = plistlib.loads(self.read(directory / "Info.plist"))
        name = info.get("CFBundleExecutable")
        require(type(name) is str and re.fullmatch(r"[A-Za-z0-9_-]+", name), "Unsafe bundle executable name")
        return self.checksum(directory / name)

    def app_hashes(self, directory):
        return {"executable": self.executable_hash(directory),
                "framework": self.checksum(directory / "Frameworks/P2pKitShared.framework/P2pKitShared")}

    def run(self):
        self.guard()
        products = self.derived / "Build/Products"
        candidates = sorted(products.glob("p2pkit-sample-jvm-transfer_*.xctestrun"))
        require(len(candidates) == 1, "Expected exactly one prepared peer xctestrun")
        prepared = candidates[0]
        document = plistlib.loads(self.read(prepared))
        target = peer_target(document)
        app = Path(target["UITargetAppPath"].replace("__TESTROOT__", str(products)))
        require(app == products / "Debug-iphonesimulator/p2pkit-sample.app", "Unexpected prepared application path")
        built_hashes = self.app_hashes(app)
        test_host = Path(target["TestHostPath"].replace("__TESTROOT__", str(products)))
        test_bundle = Path(target["TestBundlePath"].replace("__TESTROOT__", str(products))
                           .replace("__TESTHOST__", str(test_host)))
        require(all(path.is_relative_to(products) and ".." not in path.parts for path in (test_host, test_bundle)) and
                test_bundle.is_relative_to(test_host) and test_bundle.suffix == ".xctest" and test_host.suffix == ".app",
                "Prepared XCTest runner/bundle are outside these products")
        jars, jar_hashes = self.jars()
        self.record["prepared"] = {"xctestrunSha256": self.checksum(prepared), "jars": jar_hashes, "app": built_hashes,
                                   "testHost": self.executable_hash(test_host), "testBundle": self.executable_hash(test_bundle)}
        expected_a, expected_b = pattern(31, 7), pattern(17, 11)
        fixture = self.directory / self.name
        with self.audit.new_file(fixture) as output:
            output.write(expected_b)
        checksum_b = hashlib.sha256(expected_b).hexdigest()
        java_home = Path(os.environ["JAVA_HOME"]).resolve(strict=True)
        require(str(java_home) in self.context["javaHomes"], "Java installation was not admitted")
        command = [str(java_home / "bin/java"), "-Xmx512m", "-XX:MaxMetaspaceSize=256m", "-XX:ActiveProcessorCount=2",
                   "-Duser.home=" + str(self.home), "-cp", str(jars / "*"), "dev.p2pkit.sample.desktop.MainKt",
                   "JVM-" + self.nonce, "p2pkit-desktop-sample", "trace=off", "test=SWIFT-JVM",
                   "session=" + self.nonce, "role=both", "evidence=" + str(self.home / "evidence"),
                   "log=" + str(self.directory / "events.jsonl")]
        with self.audit.new_file(self.directory / "cli.stdout.log") as output, \
                self.audit.new_file(self.directory / "cli.stderr.log") as errors:
            self.cli = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=output, stderr=errors, env=dict(os.environ))
        self.await_condition("CLI readiness", lambda: "Ready. Type 'help' for commands." in self.output(), 45)
        self.command("mesh off", r"auto-mesh off")
        self.command("disc off", r"discovery off")
        block = self.command("info", r"---\n(.*?)\n---").group(1)
        fields = {}
        for label in ("advertising", "discovering", "auto-mesh", "active sessions", "fingerprint", "pairing QR", "manual port"):
            match = re.search(r"(?:^|\n)" + re.escape(label) + r"\s+([^\n]+)", block)
            require(match is not None, "Missing CLI info field: " + label)
            fields[label] = match.group(1).strip()
        require(fields["advertising"] == "true" and fields["discovering"] == fields["auto-mesh"] == "false" and
                fields["active sessions"] == "0", "CLI was not quiescent and listening before the one Swift dial")
        require(re.fullmatch(r"p2pkit:v2:p2a1-[a-z2-7]{52}:p2f1-[a-z2-7]{52}", fields["pairing QR"]) and
                fields["pairing QR"].endswith(":" + fields["fingerprint"]), "Incomplete AppId-bound CLI pairing QR")
        require(re.fullmatch(r"[0-9]{1,5}", fields["manual port"]) and 1 <= int(fields["manual port"]) <= 65535,
                "Invalid real CLI listener port")
        inject_fixture(document, {"P2PKIT_JVM_NONCE": self.nonce, "P2PKIT_JVM_SOURCE_COMMIT": self.context["expectedCommit"],
                                  "P2PKIT_JVM_PORT": fields["manual port"], "P2PKIT_JVM_QR": fields["pairing QR"],
                                  "P2PKIT_JVM_SHA256": checksum_b}, os.environ)
        # Keep it beside the original, preserving every __TESTROOT__ relative path.
        self.xctestrun = products / ("swift-jvm-" + self.nonce + ".xctestrun")
        with self.audit.new_file(self.xctestrun) as output:
            plistlib.dump(document, output)
        bundle = self.derived / "Logs/Test" / ("swift-jvm-transfer-" + self.nonce + ".xcresult")
        bundle.parent.mkdir(parents=True, exist_ok=True)
        self.record["resultBundle"] = str(bundle.relative_to(self.derived))
        jobs = os.environ.get("P2PKIT_XCODE_JOBS", "2")
        require(jobs in ("1", "2"), "Xcode job count exceeds the owned resource bound")
        with self.audit.new_file(self.directory / "xcodebuild.log") as output:
            self.xcode = subprocess.Popen(["xcodebuild", "-jobs", jobs, "-xctestrun", str(self.xctestrun),
                "-destination", "platform=iOS Simulator,id=" + self.udid, "-parallel-testing-enabled", "NO",
                "-only-testing:" + TARGET + "/" + CASE.removesuffix("()"), "-resultBundlePath", str(bundle),
                "test-without-building"], stdout=output, stderr=subprocess.STDOUT, env=dict(os.environ))
        offers = self.await_condition("one real Swift file offer", lambda:
                                     selected(self.events(), "transfer.offer.received", payloadSizeBytes=SIZE), 120)
        require(len(offers) == 1, "Expected one fresh Swift offer")
        first = offers[0]["transferId"]
        alias = "anon-" + hashlib.sha256(first.encode()).hexdigest()[:16]
        offer = self.command("offers", r"^\s*" + alias + r"\s+(ios-test-200-KiB-[0-9]+\.bin) \(204800B\) from " +
                             re.escape(offers[0]["peerId"]) + r" selector=(anon-[0-9a-f]{16})\n")
        receiver = self.home / ".p2pkit/incoming" / ("Swift-" + self.nonce)
        require(not self.entries(self.home / ".p2pkit/incoming") and not
                selected(self.events(), "transfer.offer.accepted", transferId=first), "Receive began before CLI consent")
        self.command("accept " + offer.group(2))
        self.await_condition("CLI durable hash", lambda: selected(self.events(), "file.receiver.sha256", transferId=first))
        result_a = self.verify_file(receiver / offer.group(1), expected_a)
        require(set(self.entries(receiver)) == {offer.group(1)} and
                set(self.entries(receiver.parent)) == {receiver.name}, "Extra CLI receiver/partial/reservation files")
        self.record["transfers"].append({"direction": "swift-to-jvm", "transferId": first, **result_a})

        container = Path(self.native_output("simulator-data-container", ["xcrun", "simctl", "get_app_container",
                                                                        self.udid, "dev.p2pkit.sample", "data"]).strip())
        require(container.is_absolute(), "Simulator did not return an absolute data container")
        self.audit.reject_symlinks(container)
        self.inbox = container / "Documents/P2pKitInbox"
        before = self.entries(self.inbox)
        require(self.name not in before, "Stale return filename exists before the new send")
        self.record["receiverBaselineEntryCount"] = len(before)
        self.command("sendfile Swift-" + self.nonce + " " + str(fixture))
        sent = self.await_condition("CLI prepared return file", lambda:
                                   selected(self.events(), "file.sender.sha256", payloadSizeBytes=SIZE, direction="SENT"))
        require(len(sent) == 1 and sent[0]["transferId"] != first, "Return transfer is not distinct")
        second = sent[0]["transferId"]
        self.await_condition("CLI return sender completed", lambda:
                             selected(self.events(), "transfer.completed", transferId=second, outcome="SUCCESS"))
        require(self.xcode.wait(timeout=min(90, max(1, self.deadline - time.monotonic()))) == 0, "Native XCTest failed")
        self.guard()
        result_b = self.verify_file(self.inbox / self.name, expected_b)
        after = self.entries(self.inbox)
        require(after == {**before, self.name: after[self.name]}, "Unexpected new/changed inbox or partial/reservation files")
        self.received_identity = after[self.name]
        self.record["transfers"].append({"direction": "jvm-to-swift", "transferId": second, **result_b})
        swift_rows = self.events(swift=True, final=True)
        cli_rows = self.events()
        self.record["transfers"][0].update(sender=transfer_evidence(swift_rows, first, result_a["sha256"], receiver=False, swift=True),
                                          receiver=transfer_evidence(cli_rows, first, result_a["sha256"], receiver=True, swift=False))
        self.record["transfers"][1].update(sender=transfer_evidence(cli_rows, second, result_b["sha256"], receiver=False, swift=False),
                                          receiver=transfer_evidence(swift_rows, second, result_b["sha256"], receiver=True, swift=True))
        require(len(selected(swift_rows, "application.shutdown", currentState="stopped", outcome="SUCCESS")) == 1,
                "Swift did not record its real successful Stop")
        installed = Path(self.native_output("simulator-app-container", ["xcrun", "simctl", "get_app_container",
                                                                        self.udid, "dev.p2pkit.sample", "app"]).strip())
        require(installed.is_absolute() and self.app_hashes(installed) == built_hashes == self.app_hashes(app),
                "Installed sample/framework differ from the prepared product")
        self.record["installedApp"] = built_hashes
        actions = json.loads(self.native_output("xcresult-actions", ["xcrun", "xcresulttool", "get", "object", "--legacy",
                                                                    "--format", "json", "--path", str(bundle)]))
        identifiers = {action["actionResult"]["testsRef"]["id"]["_value"] for action in
                       actions.get("actions", {}).get("_values", []) if "testsRef" in action.get("actionResult", {})}
        require(len(identifiers) == 1, "Missing/ambiguous actual XCTest action")
        objects = [json.loads(self.native_output("xcresult-tests", ["xcrun", "xcresulttool", "get", "object", "--legacy",
                             "--format", "json", "--path", str(bundle), "--id", next(iter(identifiers))]))]
        self.record["nativeCase"] = assess_case(objects)
        require(self.jars()[1] == jar_hashes and self.checksum(prepared) == self.record["prepared"]["xctestrunSha256"] and
                self.executable_hash(test_host) == self.record["prepared"]["testHost"] and
                self.executable_hash(test_bundle) == self.record["prepared"]["testBundle"],
                "Prepared runtime artifacts changed during execution")
        self.guard()
        self.record["result"] = "PASS"

    def observe_cli_quit_timeout(self):
        """One bounded attach after failure, never an alternative graceful-exit path."""
        name, limit = "cli-quit-thread-dump", 2 * MIB
        observation = {"startedUtc": self.audit.utc(), "toolTimeoutSeconds": 10, "perStreamByteLimit": limit,
                       "inspectionOnly": True, "stdout": name + ".log", "stderr": name + ".stderr.log",
                       "limits": "Post-timeout HotSpot attach observation, not natural-exit success or a root-cause verdict"}
        self.record["cliQuitThreadDump"] = observation
        observer, process = None, None
        try:
            from audit_processes import DarwinScope
            # wait(timeout) left this original direct child unreaped. Do not poll,
            # reap or replace it during attach: its PID cannot be reused meanwhile.
            require(self.cli.returncode is None, "CLI has already been reaped; do not attach")
            domain = self.ownership_domain
            observer = DarwinScope(domain["job"], domain["id"], domain["state"], domain["home"])
            owner = observer._identity(os.getpid(), required=True)
            target = observer._identity(self.cli.pid, required=True)
            require(owner is not None and target is not None and target["live"] and
                    target["parentPid"] == os.getpid() and target["parentUniqueId"] == owner["uniqueId"] and
                    target["uid"] == owner["uid"] and observer._ours(observer._inspect_environment(target)),
                    "CLI lifetime/parent/domain is not positively owned")
            observer._acquire(target)  # Existing opaque audit-token acquisition releases its Mach port.
            confirmed = observer._identity(self.cli.pid, required=True)
            require(confirmed is not None and confirmed["live"] and observer._key(confirmed) == observer._key(target) and
                    confirmed["pidVersion"] == target["pidVersion"] and
                    confirmed["parentUniqueId"] == owner["uniqueId"], "CLI lifetime changed before attach")
            observation.update({"controllerIdentity": owner, "cliIdentity": confirmed, "auditTokenAcquired": True})
            java = Path(self.cli.args[0])
            require(java.name == "java" and java.parent.name == "bin" and
                    str(java.parent.parent) in self.context["javaHomes"], "CLI Java home was not admitted")
            jcmd = java.with_name("jcmd")
            self.audit.reject_symlinks(jcmd)
            require(jcmd.is_file() and os.access(jcmd, os.X_OK), "Admitted CLI JDK has no executable jcmd")
            command = [str(jcmd), "-J-Xmx64m", "-J-XX:MaxMetaspaceSize=128m", "-J-XX:ActiveProcessorCount=2",
                       str(self.cli.pid), "Thread.print", "-l"]
            observation["command"] = command
            # Single-threaded controller; lower only this diagnostic child's file
            # bound before exec. No pipe reader thread, controller signal or retry is added.
            with self.audit.new_file(self.directory / observation["stdout"]) as output, \
                    self.audit.new_file(self.directory / observation["stderr"]) as errors:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                    env=dict(os.environ), preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit)))
                observation["diagnosticPid"] = process.pid
                try:
                    observation["exitCode"] = process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    observation["timedOut"] = True
                    # The same outer executor owns its bounded subsequent drain.
                    # Do not signal a PID or treat late diagnostic exit as success.
                observation["bytesAtReturn"] = {key: (self.directory / observation[key]).stat().st_size
                                                 for key in ("stdout", "stderr")}
                observation["outputLimitReached"] = any(size >= limit for size in observation["bytesAtReturn"].values())
            observation["cliIdentityAfter"] = observer._identity(self.cli.pid, required=True)
        except Exception as error:
            observation["error"] = type(error).__name__ + ": " + str(error)
        finally:
            if process is not None and process.returncode is None:
                self.record["unresolvedChildren"].append({"kind": name, "pid": process.pid})
            if observer is not None:
                observer.close()  # No leaders or signal/drain authority was registered here.
            observation["endedUtc"] = self.audit.utc()

    def finish(self):
        # No terminate()/kill()/numeric-PID fallback. The already admitted executor
        # handles any unresolved descendants and must fail this invocation, not
        # replace a missing real Stop/quit or native case with cleanup success.
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, signal.SIG_IGN)
        if self.cli is not None:
            try:
                if self.cli.poll() is None:
                    self.record["cliQuitWriteUtc"] = self.audit.utc()
                    self.cli.stdin.write(b"quit\n")
                    self.cli.stdin.flush()
                    self.record["cliQuitFlushedUtc"] = self.audit.utc()
                self.cli.stdin.close()
                try:
                    status = self.cli.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self.record["cliQuitTimeoutUtc"] = self.audit.utc()
                    self.observe_cli_quit_timeout()
                    raise  # Keep the original natural30s timeout as a failure.
                require(status == 0, "CLI graceful exit was not zero")
                output = self.output() + self.read(self.directory / "cli.stderr.log").decode("utf-8")
                require(output.count("Stopping…") == 1 and not any(value in output for value in
                        ("CLI failed:", "kit.stop() failed:", "CLI shutdown exceeded 30s; cleanup is incomplete")),
                        "CLI graceful shutdown evidence failed")
                rows = self.events(final=True)
                require(len(selected(rows, "application.shutdown")) == 1, "Missing CLI application shutdown event")
            except Exception as error:
                self.record["cleanupErrors"].append("CLI finalization: " + str(error))
            finally:
                try:
                    if not self.cli.stdin.closed:
                        self.cli.stdin.close()
                    # Preserve even malformed/incomplete failed CLI diagnostics.
                    # This fresh process has no unrelated historical sessions.
                    for name in ("events.jsonl", "events.jsonl.1"):
                        path = self.directory / name
                        if path.exists():
                            with self.audit.new_file(self.directory / ("cli-" + name + ".log")) as output:
                                output.write(self.read(path))
                except Exception as error:
                    self.record["cleanupErrors"].append("CLI evidence retention: " + str(error))
        if self.xcode is not None and self.xcode.poll() is None:
            try:
                self.xcode.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        for kind, process in (("cli", self.cli), ("xcodebuild", self.xcode)):
            if process is not None and process.poll() is None:
                self.record["unresolvedChildren"].append({"kind": kind, "pid": process.pid})
        try:
            require(self.audit.source_snapshot(ROOT) == self.context["source"], "Source changed during integration")
            require(self.identity == (self.directory.stat().st_dev, self.directory.stat().st_ino), "Owned work root changed")
            if not self.record["unresolvedChildren"]:
                if self.xctestrun is not None:
                    self.audit.reject_symlinks(self.xctestrun)
                    self.xctestrun.unlink(missing_ok=True)
                if self.received_identity is not None:
                    require(self.entries(self.inbox).get(self.name) == self.received_identity,
                            "Synthetic received file changed before disposal")
                    (self.inbox / self.name).unlink()
                self.audit.reject_symlinks(self.home)
                shutil.rmtree(self.home)
                (self.directory / self.name).unlink(missing_ok=True)
            else:
                self.record["cleanupErrors"].append("Required failure fixtures retained for owned executor drain; no unscoped signaling")
        except Exception as error:
            self.record["cleanupErrors"].append("Output finalization: " + str(error))
        if self.record["cleanupErrors"] or self.record["unresolvedChildren"]:
            self.record["result"] = "FAIL"
        self.write("result.json", self.record)
        print("RESULT: " + self.record["result"] + " — real Swift/JVM transfer; inspect native case, integrity and owned receipt")
        return 0 if self.record["result"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--derived-data", required=True)
    parser.add_argument("--simulator", required=True)
    experiment = Experiment(parser.parse_args())
    def interrupt(signum, frame):
        raise KeyboardInterrupt("Owned integration interrupted")
    previous = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        experiment.run()
    except (Exception, KeyboardInterrupt) as error:
        experiment.record["error"] = type(error).__name__ + ": " + str(error)
        experiment.record["result"] = "FAIL"
    finally:
        try:
            return experiment.finish()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
