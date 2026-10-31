#!/usr/bin/env python3
"""Prepare and resume the physical RPC campaign on one Mac, without a VPS.

This is development test tooling, not a publisher or a physical qualification
verdict. Commands reuse the maintained native supervisor and mobile coordinators.
All settings, signed products, raw logs and device identities stay private.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import stat
import subprocess
import sys
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import rpc_mobile_capacity as protocol

SCOPE = "MAC_DEVELOPMENT_PREPARATION_NOT_PHYSICAL_OR_RELEASE_QUALIFICATION"
MODES = ("large", "steady", "correctness", "churn")
need = protocol.need


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def source():
    runner = module("mac_campaign_source", "run-audit-command.py")
    snapshot = runner.source_snapshot(ROOT)
    need(snapshot["status"] == "" and snapshot["diffSha256"] == hashlib.sha256(b"").hexdigest(),
         "Commit the selected source first; a dirty checkout cannot prepare campaign products")
    return snapshot


def private(path):
    return module("mac_campaign_files", "run-rpc-capacity-lab.py").private_directory(path)


def private_json(path):
    files = module("mac_campaign_json", "run-rpc-capacity-lab.py")
    files.private_directory(path.parent)
    need(stat.S_IMODE(path.lstat().st_mode) == 0o600, "Private JSON must be mode0600")
    # Thirty-minute phone series exceed the small individual-control-file limit.
    # Keep the coordinator's existing8MiB report cap and original descriptor checks.
    raw = files.read_distribution_file(path, 8 * 1024 * 1024, private=True)
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def new_json(path, value):
    private(path.parent)
    module("mac_campaign_writer", "run-audit-command.py").write_new_json(path, value)
    sync_directory(path.parent)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def artifact(path):
    """Hash an original owned regular file, never follow a replacement link/FIFO."""
    need(path.is_absolute() and path == path.resolve(strict=True), "Canonical artifact path required")
    for parent in path.parents:
        need(not parent.is_symlink(), "Linked artifact ancestor")
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1 and
         not stat.S_IMODE(before.st_mode) & 0o022 and 0 < before.st_size <= 1024 ** 3,
         "Artifact must be owned, bounded, unshared and not group/world writable")
    digest = hashlib.sha256()
    count = 0
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink, s.st_size, s.st_mtime_ns)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        need(identity(os.fstat(stream.fileno())) == identity(before), "Artifact replaced before open")
        for block in iter(lambda: stream.read(65536), b""):
            count += len(block)
            need(count <= before.st_size, "Artifact grew during read")
            digest.update(block)
        need(identity(os.fstat(stream.fileno())) == identity(before) and
             identity(path.lstat()) == identity(before) and count == before.st_size, "Artifact changed during read")
    return dict(path=str(path), bytes=count, sha256=digest.hexdigest())


def verify_manifest(value, expected_source, expected_state=None):
    need(type(value) is dict and set(value) == {"schema", "scope", "source", "artifacts", "iosApp"} and
         type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and
         value["source"] == expected_source, "Missing/stale/mismatched Mac preparation manifest")
    entries = value["artifacts"]
    need(type(entries) is dict and 0 < len(entries) <= 4096, "Missing/bounded prepared artifact inventory")
    for label, entry in entries.items():
        need(type(label) is str and type(entry) is dict and set(entry) == {"path", "bytes", "sha256"},
             "Malformed prepared artifact")
        need(type(entry["path"]) is str and type(entry["bytes"]) is int and entry["bytes"] > 0 and
             type(entry["sha256"]) is str and re.fullmatch("[a-f0-9]{64}", entry["sha256"]),
             "Exact artifact length/hash types required")
        need(artifact(Path(entry["path"])) == entry, "Prepared artifact changed: " + label)
    need("android-apk" in entries and "jvm-manifest" in entries, "Both Android and generator products required")
    need(entries["android-apk"]["path"] == str(ROOT / "samples/p2p-sample-android/build/outputs/apk/debug/"
                                                     "p2p-sample-android-debug.apk") and
         entries["jvm-manifest"]["path"] == str(ROOT / "samples/p2p-sample-rpc/build/capacity-lab/manifest.json"),
         "Preparation must select the canonical current-source producers")
    ios_app = value["iosApp"]
    if ios_app is not None:
        need(type(ios_app) is str and Path(ios_app).is_dir() and "ios-executable" in entries and
             Path(entries["ios-executable"]["path"]).parent == Path(ios_app), "Signed iPhone product mismatch")
        actual = set()
        for path in Path(ios_app).rglob("*"):
            info = path.lstat()
            need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), "Linked/special signed app entry")
            if stat.S_ISREG(info.st_mode):
                actual.add(str(path))
        expected = {entry["path"] for label, entry in entries.items() if label.startswith("ios-")}
        need(actual == expected, "Signed app inventory changed; appended/removed files cannot be reused")
        if expected_state is not None:
            need(Path(ios_app) == expected_state / "ios-derived/Build/Products/Debug-iphoneos/p2pkit-rpc-phone.app",
                 "iPhone app is not this session's signed producer output")
    return value


def settings_template(manifest, phone, clients, adb):
    need(phone in ("android", "ios") and type(clients) is int and clients in (128, 256), "Explicit phone/profile required")
    key = "android-apk" if phone == "android" else "ios-executable"
    need(key in manifest["artifacts"], "Prepare the selected phone product first")
    values = dict(schema="2", clientCount=str(clients), sourceSha=manifest["source"]["commit"],
                  hostArtifactSha256=manifest["artifacts"][key]["sha256"], endpointAddress="SELECT_PHONE_LAN_ADDRESS",
                  port="48123", subnets="SELECT_APPROVED_PRIVATE_SUBNET", interface="SELECT_MAC_INTERFACE",
                  localAddress="SELECT_MAC_LAN_ADDRESS", hostInterface="SELECT_PHONE_INTERFACE")
    if phone == "android":
        values.update(androidUsbSerial="SELECT_PHYSICAL_USB_SERIAL", adb=str(adb))
    else:
        values.update(iosDeviceIdentifier="SELECT_WIRED_COREDEVICE_UUID")
    # Deliberately invalid network placeholders cannot accidentally start a run.
    return protocol.encode(values)


def verify_native_jdk(raw, major):
    """Inspect the actual JVM report, not a JAVA_HOME label or launcher alias."""
    need(type(raw) is bytes and type(major) is int and major in (17, 21), "Exact JDK report/major required")
    need(re.findall(rb"(?m)^\s*java\.specification\.version = ([0-9]+)\s*$", raw) ==
         [str(major).encode("ascii")] and
         re.findall(rb"(?m)^\s*os\.arch = (\S+)\s*$", raw) == [b"aarch64"],
         "Installed native JDK" + str(major) + " required; Rosetta or a different JVM cannot satisfy preparation")


def stage_pinned_wrapper_archive(state):
    """Optional private build-tool cache. The original wrapper still verifies and installs its ZIP."""
    cache = state.parent / "tool-cache" / "gradle-distribution.zip"
    if not cache.exists() and not cache.is_symlink():
        return
    private(cache.parent)
    properties = {}
    for line in (ROOT / "gradle/wrapper/gradle-wrapper.properties").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        need(key not in properties, "Duplicate wrapper property")
        properties[key] = value
    url = properties["distributionUrl"].replace("\\:", ":")
    parsed = urlsplit(url)
    name = Path(parsed.path).name
    need(parsed.scheme == "https" and parsed.netloc == "services.gradle.org" and
         not parsed.query and not parsed.fragment and re.fullmatch(r"gradle-[0-9][0-9A-Za-z.-]*-bin\.zip", name) and
         properties["distributionBase"] == properties["zipStoreBase"] == "GRADLE_USER_HOME" and
         properties["distributionPath"] == properties["zipStorePath"] == "wrapper/dists" and
         properties["validateDistributionUrl"] == "true", "Unsupported pinned wrapper cache layout")
    expected = properties["distributionSha256Sum"]
    before = artifact(cache)
    need(re.fullmatch("[0-9a-f]{64}", expected) and before["sha256"] == expected,
         "Cached Gradle ZIP differs from the checked-in checksum")
    # Wrapper PathAssembler's URL MD5/base36 is a directory name, never an integrity check.
    number, bucket = int(hashlib.md5(url.encode("utf-8"), usedforsecurity=False).hexdigest(), 16), ""
    while number:
        number, digit = divmod(number, 36)
        bucket = "0123456789abcdefghijklmnopqrstuvwxyz"[digit] + bucket
    private(state)
    directory = state
    for part in ("gradle-home", "wrapper", "dists", name.removesuffix(".zip"), bucket or "0"):
        directory = directory / part
        directory.mkdir(mode=0o700, exist_ok=True)
        private(directory)
    target = directory / name
    original_info = cache.lstat()
    identity = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as output:
        with os.fdopen(os.open(cache, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as source_zip:
            need(identity(os.fstat(source_zip.fileno())) == identity(original_info), "Cached ZIP was replaced")
            remaining = before["bytes"]
            while remaining:
                block = source_zip.read(min(remaining, 65536))
                need(block, "Cached ZIP ended early")
                output.write(block)
                remaining -= len(block)
            need(not source_zip.read(1) and identity(os.fstat(source_zip.fileno())) == identity(original_info),
                 "Cached ZIP changed during copy")
        output.flush()
        os.fsync(output.fileno())
    need(identity(cache.lstat()) == identity(original_info) and artifact(cache) == before and
         artifact(target)["sha256"] == expected, "Wrapper archive changed while staged")
    sync_directory(directory)
    new_json(state / "private/wrapper-cache.json", dict(scope="CHECKSUM_PINNED_BUILD_TOOL_CACHE_NOT_CAMPAIGN_PRODUCT",
        distributionUrl=url, distributionSha256=expected, cachedArchive=before, stagedArchive=artifact(target),
        wrapperVerificationRequired=True, completionMarkerCreated=False))


def campaign_environment(original, state):
    """Bind nested Xcode provenance to this source and strip unrelated publishers."""
    value = dict(original)
    for key in list(value):
        if key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN") or \
                key.upper().startswith(("SIGNING_", "ORG_GRADLE_PROJECT_SIGNING", "MAVEN_CENTRAL_", "SONATYPE_")):
            value.pop(key)
    for key in ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
        need(not value.get(key, "").strip(), "Remove conflicting JVM option environment: " + key)
    value.update(P2PKIT_AUDIT_STATE_DIR=str(state), GRADLE_USER_HOME=str(state / "gradle-home"),
                 P2PKIT_GRADLE_EXECUTOR=str(ROOT / "scripts/run-audit-command.py"), P2PKIT_PYTHON3=sys.executable,
                 RPC_CAPACITY_LAB_AUTHORIZED="synthetic-private-network-only", PYTHONDONTWRITEBYTECODE="1")
    return value


def bound_attempt_result(attempt, result):
    """A failed workload may retire safely; this grants reuse, never a test pass."""
    need(type(result) is dict and result.get("status") in
         ("FAIL", "MECHANICAL_PASS_PENDING_NETWORK_AND_RESOURCE_REVIEW") and
         result.get("schema") == 2 and type(result.get("schema")) is int and
         result.get("source") == attempt["source"] and result.get("harnessSource") == attempt["source"] and
         result.get("sourceUnchanged") is True and result.get("harnessUnchanged") is True and
         type(result.get("clientCount")) is int and result["clientCount"] == attempt["clients"] and
         result.get("mode") == attempt["mode"] and result.get("settingsSha256") == attempt["settingsSha256"],
         "Attempt result is missing, partial or bound to a different source/settings/profile")
    bound = protocol.binding(result.get("mobileBinding"))
    need(bound["schema"] == "2" and bound["clientCount"] == str(attempt["clients"]) and
         bound["hostPlatform"] == ("Android" if attempt["platform"] == "android" else "Ios") and
         bound["runLabel"] == attempt["runLabel"] and bound["hostSourceSha"] == attempt["source"]["commit"] and
         bound["hostArtifactSha256"] == attempt["hostArtifactSha256"], "Foreign phone/installed product/run")


def retired_attempt(attempt, result):
    bound_attempt_result(attempt, result)
    need(result.get("phoneCleanup") == dict(runtimeClosed=True, clientPinsRemoved=True, controlHealthy=True) and
         type(result.get("inboxSha256")) is str and re.fullmatch("[a-f0-9]{64}", result["inboxSha256"]),
         "Actual exact-inbox phone retirement is not established")
    errors = result.get("errors")
    need(type(errors) is list and all(type(row) is dict and row.get("phase") == "execution" for row in errors) and
         result.get("thermalAbort") is None, "Cleanup/control/thermal failure requires local diagnosis, not automatic reuse")
    usb = result.get("usbCleanup")
    need(type(usb) is dict, "Original USB/control retirement is missing")
    if attempt["platform"] == "android":
        need(usb.get("privateServerExited") is True and usb.get("copiedHostKeysRetired") is True,
             "Private Android server/key copies remain unqualified")
    else:
        need(usb.get("runtimeClosed") is True and usb.get("clientPinsRemoved") is True and
             usb.get("requiresOuterNativeFinalization") is True, "iPhone runtime/control retirement is unqualified")
    return dict(sourceSha=attempt["source"]["commit"], hostArtifactSha256=attempt["hostArtifactSha256"],
                deviceSha256=attempt["deviceSha256"], runLabel=attempt["runLabel"],
                inboxSha256=result["inboxSha256"], originalStatus=result["status"], physicalQualified=False)


def result_summary(value):
    """Summarize observations; never promote a mechanical result to qualification."""
    need(type(value) is dict and type(value.get("schema")) is int and value["schema"] in (1, 2) and
         value.get("status") in ("FAIL", "MECHANICAL_PASS_PENDING_NETWORK_AND_RESOURCE_REVIEW"),
         "Not a completed mobile coordinator record")
    count = value.get("clientCount", 128)
    need(type(count) is int and count in (128, 256) and
         (value["schema"] != 1 or "clientCount" not in value) and
         (value["schema"] != 2 or "clientCount" in value), "Ambiguous client profile")
    rows = value.get("phoneSamples", [])
    need(type(rows) is list and len(rows) <= 3000 and all(type(r) is dict for r in rows), "Invalid phone series")
    segments = []
    for previous, current in zip(rows, rows[1:]):
        wall = current["uptimeMillis"] - previous["uptimeMillis"]
        cpu = current["cpuNanos"] - previous["cpuNanos"]
        need(type(wall) is int and type(cpu) is int and wall > 0 and cpu >= 0, "Invalid phone CPU/monotonic series")
        segments.append(100 * cpu / (wall * 1_000_000))
    return dict(status=value["status"], clientCount=count, mode=value.get("mode"),
                source=value.get("source"), physicalQualified=False,
                peakResidentBytes=max((r["residentBytes"] for r in rows), default=None),
                peakNativeThreads=max((r["nativeThreads"] for r in rows), default=None),
                peakObservedCpuPercentOfOneCore=max(segments, default=None),
                cpuMayExceed100Percent=True, measurement=value.get("measurement"),
                initialization=value.get("initialization"), postRetention=value.get("postRetention"),
                connectedIdle=value.get("connectedIdle"), generatorBefore=value.get("generatorBefore"),
                generatorAfter=value.get("generatorAfter"),
                generatorMemoryAdmission=value.get("generatorMemoryAdmission"),
                thermalAbort=value.get("thermalAbort"), cleanup=value.get("phoneCleanup"),
                errors=value.get("errors"), batteryDrainQualified=False,
                observedBatteryStates=sorted({r["batteryState"] for r in rows if "batteryState" in r}),
                observedThermalStates=sorted({r["thermalState"] for r in rows if "thermalState" in r}))


class Session:
    def __init__(self, state, *, initialize=False):
        need(platform.system() == "Darwin" and platform.machine() == "arm64" and
             os.getuid() == os.geteuid() != 0, "Use a native ordinary-user Apple-Silicon Mac")
        need(sys.version_info >= (3, 12), "Python3.12+ required")
        self.source = source()
        self.runner = module("mac_campaign_native", "run-audit-command.py")
        self.checker = module("mac_campaign_receipts", "check-audit-receipt.py")
        need(state.is_absolute() and not state.is_symlink(), "Absolute private session path required")
        self.state = state.resolve(strict=False)
        if initialize:
            need(not self.state.exists(), "Choose a NEW session; never overwrite an earlier attempt")
            self.runner.main(["init", "--root", str(ROOT), "--state", str(self.state), "--host", "macos-arm64",
                              "--expected-commit", self.source["commit"]])
            for name in ("private", "work", "commands"):
                (self.state / name).mkdir(mode=0o700)
        _, context = self.runner.context_at(str(self.state))
        need(context["source"] == self.source and context["root"] == str(ROOT), "Session binds another source")
        self.env = campaign_environment(os.environ, self.state)

    @contextlib.contextmanager
    def phone_lock(self, phone):
        """Serialize only this session's phone owner; never unlink the stable lock."""
        need(phone in ("android", "ios") and getattr(self, "_locked_phone", None) is None,
             "One original per-phone operation required")
        directory = self.state / "private"
        private(directory)
        path = directory / (phone + "-owner.lock")
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(descriptor)
            need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
                 stat.S_IMODE(info.st_mode) == 0o600 and
                 (info.st_dev, info.st_ino) == (path.lstat().st_dev, path.lstat().st_ino),
                 "Original owned mode0600 phone lock required")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError("Another run/recover owns this phone session; no install or launch was attempted") from error
            need((info.st_dev, info.st_ino) == (path.lstat().st_dev, path.lstat().st_ino),
                 "Phone lock replaced during admission")
            sync_directory(directory)
            self._locked_phone = phone
            try:
                yield
            finally:
                self._locked_phone = None
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def command(self, label, argv, timeout=120, *, gradle=False, stem=None, require_success=True):
        need(re.fullmatch("[a-z0-9-]{1,64}", label), "Stable command label required")
        if stem is None:
            stem = self.state / "commands" / (label + "-" + os.urandom(4).hex())
        need(stem.parent == self.state / "commands" and
             re.fullmatch(re.escape(label) + r"-[a-f0-9]{8}", stem.name), "Original session command stem required")
        receipt = stem.with_suffix(".json")
        command = [sys.executable, "-B", str(ROOT / "scripts/run-audit-command.py"), "--cwd", str(ROOT),
                   "--wrapper", str(ROOT / "gradlew"), "--kind", "gradle" if gradle else "command",
                   "--purpose", label, "--timeout", str(timeout), "--receipt", str(receipt), "--", *map(str, argv)]
        with stem.with_suffix(".log").open("xb") as output:
            child = subprocess.Popen(command, cwd=ROOT, env=self.env, stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT)
            try:
                code = child.wait()  # The maintained supervisor owns all deadlines, children and cleanup.
            except BaseException:
                # Interrupt the ORIGINAL controller, not a guessed PID/group or a phone application.
                # Its signal handler requests cancellation and drains its own native scope.
                import signal
                if child.poll() is None:
                    child.send_signal(signal.SIGINT)
                try:
                    child.wait(timeout=600)
                except subprocess.TimeoutExpired as error:
                    raise RuntimeError("Native controller retirement is unobserved; retain session and inspect locally") from error
                raise
        proof = self.runner.read_json(receipt)
        self.checker.validate(proof, code, label, ROOT, ROOT / "gradlew", list(map(str, argv)))
        need((code == 0 or not require_success) and proof["sourceBefore"] == proof["sourceAfter"] == self.source and
             not proof["errors"] and not proof["ownedSurvivors"] and proof["stopExitCode"] == 0,
             "Command failed; retained private receipt: " + str(receipt))
        return proof

    def doctor(self):
        for major, key in ((17, "JAVA_HOME"), (21, "P2PKIT_AUDIT_JDK21")):
            need(os.environ.get(key) and Path(os.environ[key]).is_absolute() and
                 all((Path(os.environ[key]) / "bin" / binary).is_file() for binary in ("java", "javac")),
                 "Select installed native JDK" + str(major) + " with " + key)
        need(shutil.which("xcodegen") is not None, "Install the maintained XcodeGen before preparation")
        sdk = Path(os.environ.get("ANDROID_HOME", ""))
        need(sdk.is_absolute() and all((sdk / item).exists() for item in
             ("platforms/android-36", "platforms/android-37.0", "ndk/29.0.14206865", "platform-tools/adb")),
             "Install both Android compile platforms, platform-tools and pinned NDK29.0.14206865")
        # Every supervised command finalizes this session with the checked-in
        # wrapper's --stop. In a new Gradle home that would otherwise download
        # the distribution inside the unchanged 120-second cleanup deadline.
        # Bootstrap as its own supervised product, before any tool command.
        stage_pinned_wrapper_archive(self.state)
        self.command("doctor-wrapper", ["--version"], 900, gradle=True)
        for major, key in ((17, "JAVA_HOME"), (21, "P2PKIT_AUDIT_JDK21")):
            java = self.command("doctor-jdk" + str(major), [Path(os.environ[key]) / "bin/java",
                                                           "-XshowSettings:properties", "-version"])
            raw = (self.state / "evidence" / java["id"] / "product.stderr.log").read_bytes()
            verify_native_jdk(raw, major)
        for label, argv in (("doctor-xcode", ["/usr/bin/xcodebuild", "-version"]),
                            ("doctor-xcode-ready", ["/usr/bin/xcodebuild", "-checkFirstLaunchStatus"]),
                            ("doctor-xcodegen", [shutil.which("xcodegen"), "--version"]),
                            ("doctor-adb", [sdk / "platform-tools/adb", "version"])):
            self.command(label, argv)
        print("MAC_TOOLS_READY; device trust, signing, LAN permissions and physical control are not yet verified")

    def campaign_keys(self):
        directory = self.state / "private/adb-keys"
        directory.mkdir(mode=0o700)
        adb = Path(os.environ["ANDROID_HOME"]) / "platform-tools/adb"
        self.command("prepare-private-usb-key", [adb, "keygen", directory / "adbkey"])
        for name in ("adbkey", "adbkey.pub"):
            path = directory / name
            artifact(path)  # Checks original owner, type, linkage and descriptor lifetime before permission change.
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
                info = os.fstat(stream.fileno())
                need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1,
                     "Changed new test key")
                os.fchmod(stream.fileno(), 0o600)
        fields = dict(schema="1", scope="mobile-usb-campaign-adb-keys", sourceSha=self.source["commit"],
                      adbSha256=hashlib.sha256(adb.read_bytes()).hexdigest(),
                      privateKeySha256=artifact(directory / "adbkey")["sha256"],
                      publicKeySha256=artifact(directory / "adbkey.pub")["sha256"])
        module("mac_campaign_key_writer", "run-rpc-capacity-lab.py").write_private(directory / "manifest.txt",
                                                                                  protocol.encode(fields))
        return directory

    def prepare(self, team):
        self.doctor()
        self.command("prepare-phone-regressions", [":p2p-sample-rpc:jvmTest",
            ":p2p-sample-android:testDebugUnitTest", "--dependency-verification=strict", "--console=plain",
            "--no-parallel", "--max-workers=2"], 2400, gradle=True)
        keys = self.campaign_keys()
        tasks = [":p2p-sample-rpc:prepareRpcCapacityLab", ":p2p-sample-android:assembleDebug"]
        if team is not None:
            need(re.fullmatch("[A-Z0-9]{10}", team), "Exact development team identifier required, not a credential")
            tasks += [":p2p-sample-rpc:verifyP2pKitRpcExampleDebugXCFrameworkProvenance"]
        self.command("prepare-products", tasks, 7200, gradle=True)
        paths = {"android-apk": ROOT / "samples/p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk",
                 "jvm-manifest": ROOT / "samples/p2p-sample-rpc/build/capacity-lab/manifest.json"}
        paths.update({"jvm-" + p.name: p for p in (ROOT / "samples/p2p-sample-rpc/build/capacity-lab").glob("*.jar")})
        stage = ROOT / "library/p2p-transport-lan/build/macos-tcp" / self.source["commit"]
        paths.update({"native-" + p.name: p for p in stage.iterdir()})
        app = None
        if team is not None:
            phone = module("mac_campaign_phone", "run-rpc-phone-ios-controls.py")
            project = ROOT / "samples/p2p-sample-rpc/build/phone-ios"
            project.mkdir(parents=True, exist_ok=True)
            self.command("prepare-project", phone.project_generation_argv(ROOT, Path(shutil.which("xcodegen")), project))
            derived = self.state / "ios-derived"
            self.command("prepare-iphone", ["/usr/bin/xcodebuild", "-jobs", "2", "-project",
                project / "p2pkit-rpc-phone.xcodeproj", "-scheme", "p2pkit-rpc-phone", "-configuration", "Debug",
                "-sdk", "iphoneos", "-destination", "generic/platform=iOS", "-derivedDataPath", derived,
                "DEVELOPMENT_TEAM=" + team, "SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", "-allowProvisioningUpdates", "build"], 3600)
            app = derived / "Build/Products/Debug-iphoneos/p2pkit-rpc-phone.app"
            self.command("verify-iphone-signature", ["/usr/bin/codesign", "--verify", "--deep", "--strict", app])
            info = plistlib.loads((app / "Info.plist").read_bytes())
            need(info.get("CFBundleIdentifier") == "dev.p2pkit.rpc.phonelab" and
                 info.get("CFBundleExecutable") == "p2pkit-rpc-phone", "Wrong signed application")
            paths.update({"ios-" + p.relative_to(app).as_posix(): p for p in app.rglob("*") if p.is_file()})
            paths["ios-executable"] = app / "p2pkit-rpc-phone"
            framework = ROOT / "samples/p2p-sample-rpc/build/XCFrameworks/debug"
            paths.update({"framework-" + p.relative_to(framework).as_posix(): p
                          for p in framework.rglob("*") if p.is_file()})
        manifest = dict(schema=1, scope=SCOPE, source=self.source, artifacts={k: artifact(p) for k, p in paths.items()},
                        iosApp=str(app) if app is not None else None)
        new_json(self.state / "private/preparation.json", manifest)
        print("MAC_PRODUCTS_PREPARED: " + str(self.state / "private/preparation.json"))
        print("PRIVATE_CAMPAIGN_USB_KEYS: " + str(keys) + "; approve this test identity once on the selected Android phone")
        if team is None:
            print("iPhone product not built: configure local development signing, then prepare a new session with --team")

    def run(self, args):
        with self.phone_lock(args.platform):
            self._run(args)

    def _run(self, args):
        manifest = verify_manifest(private_json(self.state / "private/preparation.json"), self.source, self.state)
        files = module("mac_campaign_settings", "run-rpc-capacity-lab.py")
        values = files.parse(files.read_private(args.settings))
        artifact_name = "android-apk" if args.platform == "android" else "ios-executable"
        need(artifact_name in manifest["artifacts"] and values.get("schema") == "2" and
             values.get("clientCount") == str(args.clients) and values.get("sourceSha") == self.source["commit"] and
             values.get("hostArtifactSha256") == manifest["artifacts"][artifact_name]["sha256"],
             "Use exact prepared source/artifact and explicitly selected schema2 client profile")
        coordinator = "run-rpc-mobile-capacity.py" if args.platform == "android" else "run-rpc-ios-mobile-capacity.py"
        argv = [sys.executable, "-B", ROOT / "scripts" / coordinator, "--owner-authorized-mobile",
                "--settings", args.settings, "--run-label", args.run_label, "--mode", args.mode]
        pending = self.state / "private" / (args.platform + "-pending.json")
        need(not pending.exists(), "An earlier attempt remains unresolved; use recover --platform " + args.platform +
             " after inspecting its retained result. Never reinstall to erase uncertain ownership")
        # Reject known-invalid network/device templates before acquiring an
        # attempt lease. This calls only the maintained pure settings validator,
        # never a device command or an inferred post-dispatch cleanup shortcut.
        config = module("mac_campaign_preflight", coordinator).settings(
            values, self.source["commit"], args.run_label, files)
        need(re.fullmatch("en[0-9]{1,3}", config["interface"]), "Selected native Mac LAN interface required")
        device_key = "androidUsbSerial" if args.platform == "android" else "iosDeviceIdentifier"
        device_hash = hashlib.sha256(values[device_key].encode("ascii")).hexdigest()
        latest = self.state / "private" / (args.platform + "-latest.json")
        need(not latest.is_symlink(), "Installed continuation cannot be a replaced/linked pointer")
        if latest.exists():
            previous = private_json(latest)
            need(previous.get("sourceSha") == self.source["commit"] and
                 previous.get("hostArtifactSha256") == values["hostArtifactSha256"] and
                 previous.get("deviceSha256") == device_hash,
                 "Existing installed continuation belongs to another source, product or physical device")
            if args.platform == "ios":
                argv += ["--previous-ios-run-label", previous["runLabel"],
                         "--previous-ios-inbox-sha256", previous["inboxSha256"]]
        else:
            if args.platform == "android":
                argv += ["--install-android-apk", manifest["artifacts"]["android-apk"]["path"]]
            else:
                argv += ["--install-ios-app", manifest["iosApp"], "--prepare-ios-slot"]
        purpose = "campaign-" + args.platform + "-" + args.run_label
        stem = self.state / "commands" / (purpose + "-" + os.urandom(4).hex())
        attempt_path = self.state / "private" / ("attempt-" + args.platform + "-" + args.run_label + ".json")
        attempt = dict(schema=1, source=self.source, platform=args.platform, deviceSha256=device_hash,
                       hostArtifactSha256=values["hostArtifactSha256"], settingsSha256=artifact(args.settings)["sha256"],
                       clients=args.clients, mode=args.mode, runLabel=args.run_label, purpose=purpose,
                       argv=list(map(str, argv)), receipt=str(stem.with_suffix(".json")))
        new_json(attempt_path, attempt)
        # Atomic/create-only per-platform lease BEFORE any install/launch. Keep
        # the immutable original attempt even after a failed-but-healthy recovery.
        new_json(pending, dict(attempt=str(attempt_path), sha256=artifact(attempt_path)["sha256"]))
        proof = self.command(purpose, argv, 7200, stem=stem, require_success=False)
        verify_manifest(manifest, self.source, self.state)
        result = private_json(self.state / "work" / ("mobile-control-" + args.run_label) / "result.json")
        self.retire_pending(args.platform, attempt, result, proof)
        need(proof["finalExitCode"] == 0 and result["status"] == "MECHANICAL_PASS_PENDING_NETWORK_AND_RESOURCE_REVIEW" and
             not result["errors"], "Attempt failed; original evidence and retirement scope retained; use a NEW label")
        print("ATTEMPT_COMPLETE; inspect the retained phone/client results before any physical qualification claim")

    def retire_pending(self, phone, attempt, result, proof):
        need(getattr(self, "_locked_phone", None) == phone, "Original per-phone lock must cover retirement")
        need(proof == self.runner.read_json(self.state / "evidence" / proof["id"] / "receipt.json") and
             proof.get("sourceBefore") == proof.get("sourceAfter") == self.source and
             proof.get("jobId") == self.runner.context_at(str(self.state))[1]["id"] and
             proof.get("host") == "macos-arm64" and proof.get("kind") == "command" and
             proof.get("gradleHome") == str(self.state / "gradle-home"),
             "Only this session's original finalized native invocation can establish retirement")
        self.checker.validate(proof, proof["finalExitCode"], attempt["purpose"], ROOT, ROOT / "gradlew", attempt["argv"])
        if result.get("deviceControlStarted") is False:
            bound_attempt_result(attempt, result)
            need(result["status"] == "FAIL" and result.get("usbCommands") == [] and
                 result.get("phoneSamples") == [] and
                 not any(key in result for key in ("inboxSha256", "phoneCleanup", "installationAccepted",
                                                   "developmentSlotLaunchAccepted", "measurement", "thermalAbort")),
                 "No-contact retirement requires an untouched prerequisite rejection")
            control = self.state / "work" / ("mobile-control-" + attempt["runLabel"])
            need(not (control / "device-control-started.json").exists() and
                 not (control / "device-control-started.json").is_symlink(), "Device control was attempted")
            for directory in (control / "commands", control / "usb",
                              self.state / "work" / ("mobile-client-" + attempt["runLabel"])):
                private(directory)
                need(not any(directory.iterdir()), "Phone or generator dispatch cannot be retired as untouched")
            errors = result.get("errors")
            need(type(errors) is list and errors and all(type(row) is dict and row.get("phase") in
                 ("execution", "generator-final-observation") for row in errors), "Other cleanup failure is unqualified")
            authority = None  # Preserve any prior installed continuation exactly.
        else:
            authority = retired_attempt(attempt, result)
        pending = self.state / "private" / (phone + "-pending.json")
        saved = artifact(pending)
        original = private_json(pending)
        attempt_path = Path(original["attempt"])
        need(private_json(attempt_path) == attempt and artifact(attempt_path)["sha256"] == original["sha256"],
             "Pending attempt was replaced; retain for diagnosis")
        if authority is None:
            new_json(self.state / "private" / ("undispatched-" + phone + "-" + attempt["runLabel"] + ".json"),
                     dict(scope="PREREQUISITE_REJECTION_NO_DEVICE_CONTROL", source=self.source,
                          runLabel=attempt["runLabel"], originalStatus=result["status"],
                          originalReceiptSha256=artifact(Path(attempt["receipt"]))["sha256"], physicalQualified=False))
        else:
            latest = self.state / "private" / (phone + "-latest.json")
            module("mac_campaign_resume", "run-rpc-capacity-lab.py").write_private(
                latest, (json.dumps(authority) + "\n").encode(), replace=latest.exists())
        need(artifact(pending) == saved, "Pending lease changed during retirement")
        pending.unlink()  # Only this original lease; all attempt/results/receipts remain.
        sync_directory(pending.parent)

    def recover(self, phone):
        with self.phone_lock(phone):
            self._recover(phone)

    def _recover(self, phone):
        verify_manifest(private_json(self.state / "private/preparation.json"), self.source, self.state)
        pending = private_json(self.state / "private" / (phone + "-pending.json"))
        path = Path(pending["attempt"])
        need(path.parent == self.state / "private" and artifact(path)["sha256"] == pending["sha256"],
             "Original source-bound pending attempt required")
        attempt = private_json(path)
        need(type(attempt.get("schema")) is int and attempt["schema"] == 1 and
             attempt["source"] == self.source and attempt["platform"] == phone and
             attempt["purpose"] == "campaign-" + phone + "-" + attempt["runLabel"] and
             Path(attempt["receipt"]).parent == self.state / "commands", "Foreign recovery attempt")
        result = private_json(self.state / "work" / ("mobile-control-" + attempt["runLabel"]) / "result.json")
        proof = private_json(Path(attempt["receipt"]))
        self.retire_pending(phone, attempt, result, proof)
        print("ORIGINAL_ATTEMPT_RETIREMENT_VERIFIED; original " + result["status"] + " retained, not promoted to PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("doctor", "prepare", "verify", "run", "settings", "recover"):
        command = sub.add_parser(name)
        command.add_argument("--state", type=Path, required=True, help="Private canonical path OUTSIDE the checkout")
        if name in ("doctor", "prepare"):
            command.add_argument("--new-session", action="store_true", help="Initialize a new native session")
        if name == "prepare":
            command.add_argument("--team", help="Existing locally provisioned Apple development team; never a token")
        if name == "run":
            command.add_argument("--platform", choices=("android", "ios"), required=True)
            command.add_argument("--clients", type=int, choices=(128, 256), required=True)
            command.add_argument("--mode", choices=MODES, required=True)
            command.add_argument("--settings", type=Path, required=True)
            command.add_argument("--run-label", required=True)
        if name == "settings":
            command.add_argument("--platform", choices=("android", "ios"), required=True)
            command.add_argument("--clients", type=int, choices=(128, 256), required=True)
            command.add_argument("--output", type=Path, required=True, help="New private settings template; edit real LAN/device values")
        if name == "recover":
            command.add_argument("--platform", choices=("android", "ios"), required=True,
                                 help="Inspect/reuse only an exact failed attempt whose original retirement is verified")
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--result", type=Path, required=True)
    analyze.add_argument("--output", type=Path, required=True, help="NEW private summary, never overwrites original evidence")
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "analyze":
        private(args.output.parent)
        new_json(args.output, result_summary(private_json(args.result)))
        print("SUMMARY_WRITTEN; no physical/release verdict: " + str(args.output))
        return
    if args.action == "run":
        need(re.fullmatch("[a-z0-9-]{1,24}", args.run_label), "New short run label required for the private USB socket")
    session = Session(args.state, initialize=getattr(args, "new_session", False))
    if args.action == "doctor":
        session.doctor()
    elif args.action == "prepare":
        session.prepare(args.team)
    elif args.action == "verify":
        verify_manifest(private_json(session.state / "private/preparation.json"), session.source, session.state)
        print("PREPARED_PRODUCTS_UNCHANGED; no device qualification implied")
    elif args.action == "settings":
        manifest = verify_manifest(private_json(session.state / "private/preparation.json"), session.source, session.state)
        raw = settings_template(manifest, args.platform, args.clients, Path(os.environ["ANDROID_HOME"]) / "platform-tools/adb")
        if args.platform == "android":
            values = protocol.parse(raw) | dict(adbCampaignKeys=str(session.state / "private/adb-keys"))
            raw = protocol.encode(values)
        module("mac_campaign_template", "run-rpc-capacity-lab.py").write_private(args.output, raw)
        print("SETTINGS_TEMPLATE_WRITTEN: " + str(args.output) + "; replace deliberately invalid device/network placeholders")
    elif args.action == "recover":
        session.recover(args.platform)
    else:
        session.run(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("MAC_CAMPAIGN_ABORTED: " + type(error).__name__ + "; " + str(error), file=sys.stderr)
        raise SystemExit(1)
