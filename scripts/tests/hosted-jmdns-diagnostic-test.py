#!/usr/bin/env python3
"""Focused synthetic/source controls, not Java, native-policy or hosted evidence.

Only the pure diagnostic DATA helper is imported. Every receipt, PID, clock and
native-log record below is invented test data, never a substitute for originals.
The carrier's source/run/attempt/custody and actual execution are checked in its
separate controls. This suite neither starts a process nor queries native policy.
"""
from __future__ import annotations

import ast
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/hosted_jmdns_diagnostic.py"
FIXTURE = ROOT / (
    "library/p2p-transport-lan/src/jvmTest/java/dev/p2pkit/transport/lan/internal/jmdns/impl/"
    "JmdnsCloseLifecycleFixture.java"
)
LAUNCHER = ROOT / (
    "library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JmdnsCloseLifecycleTest.kt"
)
WIRING = ROOT / "library/p2p-transport-lan/build.gradle.kts"
MODES = (
    "control", "failed_recovery", "shared_close", "close_wins", "recovery_wins",
    "responder_close", "callback_executor", "cleanup_retry",
)
TASKS = (
    ":p2p-transport-lan:jvmTest", "--tests",
    "dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest.realResourceCloseRegressionsExitNaturally",
    "--no-configure-on-demand",
)
PREDICATE = '''
(process == "nehelper" OR process == "networkd" OR process == "mDNSResponder"
 OR subsystem BEGINSWITH "com.apple.network"
 OR (process == "kernel" AND eventMessage CONTAINS[c] "necp"))
AND
(eventMessage CONTAINS[c] "local network" OR eventMessage CONTAINS[c] "local-network"
 OR eventMessage CONTAINS[c] "necp" OR eventMessage CONTAINS[c] "policy"
 OR eventMessage CONTAINS[c] "deny" OR eventMessage CONTAINS[c] "denied"
 OR eventMessage CONTAINS[c] "responsib")
'''
INVOCATION = "1" * 32
JOB = "2" * 32
JAVA_PATH = "/synthetic-jdk/Contents/Home/bin/java"
PATH_HASH = hashlib.sha256(b"p2pkit-jmdns-executable-path-v1\0" + JAVA_PATH.encode()).hexdigest()
BASE = int(datetime(2026, 9, 28, 12, tzinfo=timezone.utc).timestamp()) * 1000
BIRTH = BASE + 123
BEFORE = BASE + 10_111
AFTER = BEFORE + 1
PID = 24680


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def utc(millis):
    return datetime.fromtimestamp(millis / 1000, timezone.utc).isoformat(timespec="milliseconds")


def synthetic_trace(**changes):
    fields = {
        "mode": "control", "pid": PID, "birthEpochMillis": BIRTH,
        "birthPrecision": "MILLISECONDS", "executablePathSha256": PATH_HASH,
        "ordinal": 1, "utcBeforeMillis": BEFORE, "utcAfterMillis": AFTER,
        "monotonicBeforeNanos": -1_200_000, "monotonicAfterNanos": -200_000,
        "failureClass": "java.net.NoRouteToHostException", "destination": "true",
    }
    fields.update(changes)
    return (
        "FAIL mode={mode}\n"
        "startup elapsedMillis=10000 sendCalls=2 sendReturns=0 recoveryCalls=2 proberCalls=1 announcerCalls=0\n"
        "startup firstSendFailureClass={failureClass} firstSendDestinationIpv4Mdns={destination}\n"
        "startup processIdentity schema=1 mode={mode} pid={pid} birthEpochMillis={birthEpochMillis} "
        "birthPrecision={birthPrecision} executablePathSha256={executablePathSha256}\n"
        "startup firstSendIdentity schema=1 ordinal={ordinal} utcBeforeMillis={utcBeforeMillis} "
        "utcAfterMillis={utcAfterMillis} monotonicBeforeNanos={monotonicBeforeNanos} "
        "monotonicAfterNanos={monotonicAfterNanos}\n"
        "startup frameRole=send_failure frame=sun.nio.ch.DatagramChannelImpl.send0\n"
        "phase=fixture_rescue_begin mode={mode}\n"
        "phase=fixture_rescue_finished_original_failure_preserved mode={mode}\n"
    ).format(**fields).encode("utf-8")


def synthetic_receipt():
    # Schema-shaped DATA only. Nothing here proves that a native owner executed.
    source = {"commit": "3" * 40, "tree": "4" * 40, "status": "", "diffSha256": digest(b"")}
    native = {
        "pid": PID, "uid": 501, "parentPid": 24679, "group": 24000,
        "uniqueId": 80001, "parentUniqueId": 80000, "pidVersion": 7,
        "startSeconds": BIRTH // 1000, "startMicroseconds": 123456,
        "realUid": 501, "status": 2, "flags": 4, "live": True,
    }
    return {
        "schema": 1, "id": INVOCATION, "jobId": JOB, "kind": "command", "host": "macos-arm64",
        "purpose": "synthetic-jmdns-target", "productPid": 24000,
        "productExitCode": 1, "stopExitCode": 0, "finalExitCode": 1,
        "errors": [], "ownedSurvivors": [], "sourceUnchanged": True,
        "sourceBefore": source, "sourceAfter": copy.deepcopy(source),
        "productStartedUtc": utc(BASE), "productEndedUtc": utc(BASE + 30_000),
        "ownership": {
            "backend": "darwin-libproc-audit-token", "scope": "controlled-marker-inheriting-descendants",
            "invocation": INVOCATION, "job": JOB, "startedIdentities": [native],
            "discoveryErrors": [], "discoveryReconciliations": [],
            "observationReconciliations": [], "drainReconciliations": [], "launches": [],
        },
    }


def region(text, first, last=None):
    assert text.count(first) == 1, "source region start changed"
    start = text.index(first)
    if last is None:
        return text[start:]
    assert text.count(last) == 1, "source region end changed"
    end = text.index(last, start) + len(last)
    assert text[end:end + 1] == "\n", "source region boundary changed"
    return text[start:end + 1]


def fixture_source_guard(text):
    # These are preserved accepted SOURCE regions from b19780f0, not regenerated
    # native evidence/expected-output hashes. Only the approved report(mode)
    # argument addition is normalized when comparing the original main method.
    main = region(text, "    public static void main(String[] args) throws Throwable {",
                  "    private static void ordinaryClose(Fixture f) throws Exception {")
    assert main.count("STARTUP.report(mode);") == 1, "missing failure-only identity report"
    main = main.replace("STARTUP.report(mode);", "STARTUP.report();")
    assert digest(main.encode()) == "ea4ca39f0f614503a4f629a4ab35ded4a59c290d45bb2e83394fcf087b807a35"
    regions = (
        ("    private static void ordinaryClose(Fixture f) throws Exception {",
         "    private static final class FixtureDns extends JmDNSImpl {",
         "660c772fbc8dad7666140bdd4fd2a90cfc4eb25dbe3226bd67b80e3f02661f9f"),
        ("    private static final class FixtureDns extends JmDNSImpl {",
         "        private void observedNativeSend(DNSOutgoing outgoing) throws IOException {",
         "abbb55441622e3b73000a84e2718ef4c02ce9e2eac159072dc5919f33e109218"),
        ("        public void recover() {", "    private static final class StartupTrace {",
         "c18c0bfcf0e684ee968764c47bfed56b6a9bbae6cc78b981b3fbcd8627d52212"),
        ("    private record InterfaceIdentity(int index, String name) {", None,
         "7b8e981614192e4fc054005ed1a23fce2b39b9d433350b5762b887343b05386c"),
    )
    for first, last, expected in regions:
        assert digest(region(text, first, last).encode()) == expected, "accepted fixture behavior changed"
    for name, value in (("READY", "10_000"), ("STEP", "5_000"), ("JOIN", "1_000")):
        assert text.count(f"private static final long {name}_MILLIS = {value};") == 1, "fixture limit changed"
    send = region(text, "        private void observedNativeSend(DNSOutgoing outgoing) throws IOException {",
                  "        public void recover() {")
    assert send.count("super.send(outgoing);") == 1, "real send replaced/repeated"
    assert send.count("STARTUP.sendCalls.incrementAndGet()") == 1, "call ordinal changed"
    assert send.count("STARTUP.sendReturns.incrementAndGet();") == 1, "send success accounting changed"
    assert send.count("STARTUP.firstSendFailure.compareAndSet(null, new SendFailure(failure, ipv4Mdns, ordinal,") == 1
    assert send.count("throw failure;") == 1, "original send failure lost"
    assert send.count("System.nanoTime()") == 2 and send.count("System.currentTimeMillis()") == 2
    ordered = (
        "int ordinal = STARTUP.sendCalls.incrementAndGet();",
        "long monotonicBeforeNanos = System.nanoTime();",
        "long utcBeforeMillis = System.currentTimeMillis();",
        "super.send(outgoing);", "STARTUP.sendReturns.incrementAndGet();",
        "long utcAfterMillis = System.currentTimeMillis();",
        "long monotonicAfterNanos = System.nanoTime();",
        "STARTUP.firstSendFailure.compareAndSet", "throw failure;",
    )
    positions = [send.index(item) for item in ordered]
    assert positions == sorted(positions), "original-send clock enclosure changed"
    for forbidden in ("ProcessHandle", "ProcessBuilder", "Files.", "Path.", "MessageDigest", "System.out",
                      "Thread.sleep", "waitFor", "synchronized", "StartupPrimitives", "new Datagram"):
        assert forbidden not in send, "send path gained work other than clocks/ordinal"
    identity = region(text, "        private static void reportProcessIdentity(String mode) {",
                      "        static void reportThread(String role, Thread thread) {")
    for required in ("ProcessHandle.current()", "current.pid()", "info.startInstant()", "value.toEpochMilli()",
                     "info.command()", ".toRealPath()", 'MessageDigest.getInstance("SHA-256")',
                     '"p2pkit-jmdns-executable-path-v1\\0"', "pathBytes.length <= 16_384",
                     '"UNKNOWN"', '"MILLISECONDS"', "catch (Throwable ignored)"):
        assert required in identity, "actual private failure identity metadata changed"
    assert "System.out.println(realPath)" not in identity and '" path="' not in identity


def pure_helper_source_guard(source):
    tree = ast.parse(source)
    allowed_imports = {"__future__", "datetime", "hashlib", "json", "pathlib", "re", "typing"}
    forbidden_calls = {"open", "exec", "eval", "__import__", "print", "input", "breakpoint",
                       "read_text", "read_bytes", "write_text", "write_bytes", "resolve", "stat", "lstat",
                       "exists", "is_file", "is_dir", "mkdir", "unlink", "rename", "getenv", "system",
                       "Popen", "run", "call", "check_call", "check_output", "urlopen", "connect", "sleep"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(item.name in allowed_imports for item in node.names), "helper gained execution/IO import"
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module in allowed_imports, "helper gained execution/IO import"
            if node.module == "pathlib":
                assert all(item.name == "PurePosixPath" for item in node.names), "helper gained filesystem path API"
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else None)
            assert name not in forbidden_calls, "helper gained IO/execution"
            assert not (isinstance(node.func, ast.Name) and name == "compile"), "helper gained dynamic code"
        if isinstance(node, ast.Attribute):
            assert node.attr != "environ", "helper gained ambient environment access"


def predicate_shape(text):
    # Ignore source formatting, not spaces inside quoted native selector values.
    parts = re.split(r'("(?:[^"\\]|\\.)*")', text)
    return "".join(part if index % 2 else re.sub(r"\s+", "", part) for index, part in enumerate(parts))


class DiagnosticControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        helper_source = HELPER.read_text(encoding="utf-8")
        pure_helper_source_guard(helper_source)
        spec = importlib.util.spec_from_file_location("p2pkit_synthetic_jmdns_diagnostic", HELPER)
        cls.helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.helper
        spec.loader.exec_module(cls.helper)
        cls.helper_source = helper_source
        cls.fixture_source = FIXTURE.read_text(encoding="utf-8")

    def binding(self, trace=None, receipt=None, **overrides):
        arguments = {"invocation_id": INVOCATION, "job_id": JOB, "executable_path_sha256": PATH_HASH}
        arguments.update(overrides)
        return self.helper.bind_native_process(
            self.helper.parse_fixture_trace(synthetic_trace()) if trace is None else trace,
            synthetic_receipt() if receipt is None else receipt, **arguments)

    def assert_inconclusive(self, result):
        self.assertEqual(result["schema"], 1)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertRegex(result["reason"], r"\A[A-Z0-9_]+\Z")
        self.assertNotIn("queryStartUtc", result)
        self.assertNotIn("queryEndUtc", result)

    def test_01_unchanged_launcher_wiring_and_fixture_acceptance(self):
        # Byte-equal at reviewed base b19780f0: original8 modes/order, JDK17,
        # heap/metaspace/processor flags,45s child,5s reap and natural/no-rescue.
        self.assertEqual(digest(LAUNCHER.read_bytes()),
                         "1eee1f8352a615c5c4aa543aa63837d9112c050c336677d2e3015d237fe27ec7")
        self.assertEqual(digest(WIRING.read_bytes()),
                         "b8d22cf058d3b43b7cd694b8552a5bfd8a429ad0ec3bfe1556934008cc623847")
        fixture_source_guard(self.fixture_source)
        self.assertEqual(tuple(self.helper.MODES), MODES)
        self.assertEqual(tuple(self.helper.GRADLE_ARGUMENTS), TASKS)

    def test_02_fixture_source_mutations_are_rejected(self):
        mutations = (
            ("READY_MILLIS = 10_000", "READY_MILLIS = 20_000"),
            ("STEP_MILLIS = 5_000", "STEP_MILLIS = 6_000"),
            ("JOIN_MILLIS = 1_000", "JOIN_MILLIS = 2_000"),
            ('case "control":', 'case "different_control":'),
            ("throw failure;", "return;"),
            ("super.send(outgoing);", "super.send(outgoing); super.send(outgoing);"),
            ("long utcBeforeMillis = System.currentTimeMillis();",
             "long utcBeforeMillis = System.currentTimeMillis(); Files.readAllBytes(Path.of(\"/synthetic\"));"),
            ("long monotonicAfterNanos = System.nanoTime();", "long monotonicAfterNanos = monotonicBeforeNanos;"),
            ('!"true".equals(System.getProperty("p2pkit.audit.jmdnsStartupPrimitives"))', "false"),
        )
        for before, after in mutations:
            with self.subTest(mutation=before):
                self.assertIn(before, self.fixture_source)
                changed = self.fixture_source.replace(before, after, 1)
                self.assertNotEqual(changed, self.fixture_source)
                with self.assertRaises(AssertionError):
                    fixture_source_guard(changed)

    def test_03_helper_stays_pure_and_source_io_mutations_are_rejected(self):
        pure_helper_source_guard(self.helper_source)
        for extra in ("import subprocess\n", "import os\n", "open('/synthetic')\n",
                      "compile('synthetic', '<synthetic>', 'exec')\n",
                      "from pathlib import Path\n", "print('synthetic')\n"):
            with self.subTest(source=extra.strip()):
                with self.assertRaises(AssertionError):
                    pure_helper_source_guard(self.helper_source + "\n" + extra)

    def test_04_fixed_observation_bounds(self):
        expected = {"FIXTURE_LIMIT": 65536, "LOG_LIMIT": 1048576, "CODE_LIMIT": 65536,
                    "LOG_SECONDS": 45, "CODE_SECONDS": 15, "HASH_SECONDS": 5,
                    "OBSERVATION_SECONDS": 120, "PRODUCT_SECONDS": 1200}
        for name, value in expected.items():
            with self.subTest(bound=name):
                self.assertEqual(getattr(self.helper, name), value)

    def test_05_canonical_path_hash_and_fixed_read_only_code_commands(self):
        self.assertEqual(self.helper.path_identity(JAVA_PATH), PATH_HASH)
        self.assertEqual(self.helper.code_argv(JAVA_PATH), {
            "signature": ["/usr/bin/codesign", "-d", "--verbose=4", JAVA_PATH],
            "uuid": ["/usr/bin/xcrun", "dwarfdump", "--uuid", JAVA_PATH],
        })
        other = "/different-synthetic-jdk/bin/java"
        self.assertNotEqual(self.helper.path_identity(other), PATH_HASH)
        unicode_path = "/synthetic-\u00e9/bin/java"
        self.assertEqual(self.helper.path_identity(unicode_path),
                         digest(b"p2pkit-jmdns-executable-path-v1\0" + unicode_path.encode("utf-8")))

    def test_06_ambiguous_noncanonical_and_oversized_paths_rejected(self):
        paths = (None, True, b"/bin/java", "java", "", "//bin/java", "/bin/../java", "/bin/./java",
                 "/bin//java", "/bin/java/", "/bin/java\n", "/\t/bin/java", "/\0/bin/java",
                 "/\x7f/bin/java", "/\ud800/bin/java", "/" + "x" * 16384 + "/java")
        for path in paths:
            with self.subTest(path_type=type(path).__name__, length=len(path) if isinstance(path, str) else 0):
                with self.assertRaises(self.helper.DiagnosticError) as raised:
                    self.helper.path_identity(path)
                self.assertRegex(str(raised.exception), r"\A[A-Z0-9_]+\Z")
                with self.assertRaises(self.helper.DiagnosticError):
                    self.helper.code_argv(path)

    def test_07_original_failure_metadata_parses_without_acceptance(self):
        raw = synthetic_trace()
        result = self.helper.parse_fixture_trace(raw)
        self.assertEqual(result["status"], "CAPTURED")
        self.assertEqual(result["reason"], "ORIGINAL_FAILURE_METADATA")
        self.assertEqual(result["traceSha256"], digest(raw))
        self.assertEqual(result["pid"], PID)
        self.assertEqual(result["birthEpochMillis"], BIRTH)
        self.assertEqual(result["birthPrecision"], "MILLISECONDS")
        self.assertEqual(result["executablePathSha256"], PATH_HASH)
        self.assertEqual(result["ordinal"], 1)
        self.assertEqual(result["failureClass"], "java.net.NoRouteToHostException")
        self.assertIs(result["destinationIpv4Mdns"], True)
        self.assertNotIn("accepted", result)
        self.assertNotIn("responsiblePid", result)

    def test_08_signed_monotonic_origin_and_signed_wrap_preserve_elapsed(self):
        captures = ((-1_200_000, -200_000), (0, 1_000_000),
                    (2**63 - 500_000, -(2**63) + 500_000))
        for before, after in captures:
            with self.subTest(before=before, after=after):
                result = self.helper.parse_fixture_trace(synthetic_trace(
                    monotonicBeforeNanos=before, monotonicAfterNanos=after))
                self.assertEqual(result["status"], "CAPTURED")
                self.assertEqual(result["monotonicBeforeNanos"], before)
                self.assertEqual(result["monotonicAfterNanos"], after)

    def test_09_reversed_overflow_and_unbounded_clocks_are_inconclusive(self):
        changes = (
            {"monotonicBeforeNanos": 2, "monotonicAfterNanos": 1},
            {"monotonicBeforeNanos": -(2**63) - 1}, {"monotonicAfterNanos": 2**63},
            {"monotonicBeforeNanos": 0, "monotonicAfterNanos": 45_000_000_001},
            {"utcAfterMillis": BEFORE - 1}, {"utcBeforeMillis": 0},
            {"utcAfterMillis": BEFORE + 45001}, {"birthEpochMillis": AFTER + 1},
            {"utcAfterMillis": BEFORE + 1000},
        )
        for change in changes:
            with self.subTest(change=change):
                self.assert_inconclusive(self.helper.parse_fixture_trace(synthetic_trace(**change)))

    def test_10_missing_duplicate_and_malformed_capture_lines_are_inconclusive(self):
        raw = synthetic_trace()
        for prefix in (b"startup processIdentity", b"startup firstSendIdentity", b"startup firstSendFailureClass"):
            line = next(item for item in raw.splitlines(keepends=True) if item.startswith(prefix))
            for changed in (raw.replace(line, b""), raw + line, raw.replace(line, line.rstrip() + b" extra=1\n")):
                with self.subTest(prefix=prefix.decode(), bytes=len(changed)):
                    self.assert_inconclusive(self.helper.parse_fixture_trace(changed))

    def test_11_unavailable_or_invalid_identity_is_not_substituted(self):
        changes = (
            {"pid": "UNKNOWN"}, {"birthEpochMillis": "UNKNOWN"}, {"birthPrecision": "UNKNOWN"},
            {"executablePathSha256": "UNKNOWN"}, {"pid": 0}, {"pid": 2**31},
            {"pid": "1e3"}, {"pid": "001"}, {"ordinal": 0}, {"ordinal": -1},
            {"ordinal": 2**31}, {"mode": "another_mode"}, {"birthPrecision": "NANOSECONDS"},
            {"executablePathSha256": PATH_HASH.upper()}, {"executablePathSha256": "f" * 63},
        )
        for change in changes:
            with self.subTest(change=change):
                self.assert_inconclusive(self.helper.parse_fixture_trace(synthetic_trace(**change)))

    def test_12_original_failure_outcome_cannot_be_replaced_by_pass(self):
        raw = synthetic_trace()
        for changed in (raw.replace(b"FAIL mode=control\n", b""), raw + b"FAIL mode=control\n",
                        raw.replace(b"FAIL mode=control", b"FAIL mode=failed_recovery"),
                        raw + b"PASS mode=control\n"):
            self.assert_inconclusive(self.helper.parse_fixture_trace(changed))

    def test_13_trace_encoding_limit_and_no_original_text_echo(self):
        raw = synthetic_trace()
        at_limit = raw + b"x" * (65536 - len(raw) - 1) + b"\n"
        self.assertEqual(len(at_limit), 65536)
        self.assertEqual(self.helper.parse_fixture_trace(at_limit)["status"], "CAPTURED")
        for changed in (at_limit + b"x", b"", None, bytearray(raw), raw + b"\xff"):
            self.assert_inconclusive(self.helper.parse_fixture_trace(changed))
        sentinel = "synthetic-private-message-not-evidence"
        result = self.helper.parse_fixture_trace(raw.replace(b"pid=24680", b"pid=" + sentinel.encode()))
        self.assert_inconclusive(result)
        self.assertNotIn(sentinel, json.dumps(result))

    def test_14_later_captured_send_is_retained_but_never_first_send_bound(self):
        trace = self.helper.parse_fixture_trace(synthetic_trace(ordinal=2))
        self.assertEqual(trace["status"], "CAPTURED")
        self.assertEqual(trace["ordinal"], 2)
        self.assert_inconclusive(self.binding(trace))

    def test_15_other_mode_exception_or_destination_is_not_original_target(self):
        for change in ({"mode": "failed_recovery"}, {"failureClass": "java.io.IOException"},
                       {"destination": "false"}, {"destination": "UNKNOWN"}):
            with self.subTest(change=change):
                trace = self.helper.parse_fixture_trace(synthetic_trace(**change))
                self.assertEqual(trace["status"], "CAPTURED")
                self.assert_inconclusive(self.binding(trace))

    def test_16_exact_native_lifetime_common_precision_and_data_copies(self):
        trace = self.helper.parse_fixture_trace(synthetic_trace())
        receipt = synthetic_receipt()
        binding = self.binding(trace, receipt)
        self.assertEqual(binding["status"], "BOUND")
        self.assertEqual(binding["reason"], "ORIGINAL_FIRST_SEND_IDENTITY")
        self.assertEqual(binding["nativeIdentity"], receipt["ownership"]["startedIdentities"][0])
        self.assertEqual(binding["nativeIdentity"]["startMicroseconds"], 123456)
        self.assertEqual(binding["nativeIdentity"]["startSeconds"] * 1000 + 123456 // 1000, BIRTH)
        self.assertNotEqual(binding["nativeIdentity"]["pid"], receipt["productPid"])
        self.assertNotIn("responsiblePid", binding)
        self.assertNotIn("runId", binding)  # Original run/source custody is the carrier's job.
        receipt["ownership"]["startedIdentities"][0]["uid"] = 0
        trace["pid"] = 1
        self.assertEqual(binding["nativeIdentity"]["uid"], 501)
        self.assertEqual(binding["trace"]["pid"], PID)

    def test_17_source_invocation_and_executable_mismatch_are_inconclusive(self):
        for overrides in ({"invocation_id": "5" * 32}, {"job_id": "6" * 32},
                          {"executable_path_sha256": "7" * 64}, {"executable_path_sha256": None}):
            with self.subTest(overrides=overrides):
                self.assert_inconclusive(self.binding(**overrides))
        for field, value in (("commit", "bad"), ("tree", "bad"), ("status", " M synthetic"),
                             ("diffSha256", "8" * 64)):
            receipt = synthetic_receipt()
            receipt["sourceBefore"][field] = value
            receipt["sourceAfter"] = copy.deepcopy(receipt["sourceBefore"])
            self.assert_inconclusive(self.binding(receipt=receipt))
        receipt = synthetic_receipt()
        receipt["sourceAfter"]["commit"] = "9" * 40
        self.assert_inconclusive(self.binding(receipt=receipt))

    def test_18_unclosed_canceled_or_nonfailure_receipts_cannot_bind(self):
        changes = (
            ("schema", True), ("kind", "gradle"), ("sourceUnchanged", False),
            ("stopExitCode", 1), ("stopExitCode", False), ("finalExitCode", 0),
            ("ownedSurvivors", [{"pid": PID}]), ("errors", ["synthetic retirement error"]),
            ("cancelRequested", True), ("cancelledSignals", [15]), ("productPid", PID),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value):
                receipt = synthetic_receipt()
                receipt[field] = value
                self.assert_inconclusive(self.binding(receipt=receipt))
        for code in (None, True, 0, -9, 124, 125, 126, 127, 137, 255):
            receipt = synthetic_receipt()
            receipt["productExitCode"] = receipt["finalExitCode"] = code
            self.assert_inconclusive(self.binding(receipt=receipt))

    def test_19_wrong_native_owner_or_discovery_error_cannot_bind(self):
        changes = (("backend", "linux-pidfd"), ("scope", "process-group"),
                   ("invocation", "a" * 32), ("job", "different-job"),
                   ("discoveryErrors", ["synthetic unresolved discovery"]))
        for field, value in changes:
            with self.subTest(field=field):
                receipt = synthetic_receipt()
                receipt["ownership"][field] = value
                self.assert_inconclusive(self.binding(receipt=receipt))

    def test_20_missing_ambiguous_or_reused_pid_is_not_assumed_fixture(self):
        for rows in ([], [synthetic_receipt()["ownership"]["startedIdentities"][0]] * 2):
            receipt = synthetic_receipt()
            receipt["ownership"]["startedIdentities"] = rows
            self.assert_inconclusive(self.binding(receipt=receipt))
        for field, value in (("pid", PID + 1), ("startSeconds", BIRTH // 1000 - 1),
                             ("startMicroseconds", 124000), ("startMicroseconds", 1000000),
                             ("pidVersion", True), ("uniqueId", 0), ("uid", -1), ("live", 1)):
            with self.subTest(field=field, value=value):
                receipt = synthetic_receipt()
                receipt["ownership"]["startedIdentities"][0][field] = value
                self.assert_inconclusive(self.binding(receipt=receipt))
        receipt = synthetic_receipt()
        del receipt["ownership"]["startedIdentities"][0]["realUid"]
        self.assert_inconclusive(self.binding(receipt=receipt))

    def test_21_unrelated_native_descendant_does_not_replace_target(self):
        receipt = synthetic_receipt()
        other = copy.deepcopy(receipt["ownership"]["startedIdentities"][0])
        other.update(pid=PID + 100, uniqueId=90000, parentPid=1)
        receipt["ownership"]["startedIdentities"].insert(0, other)
        binding = self.binding(receipt=receipt)
        self.assertEqual(binding["status"], "BOUND")
        self.assertEqual(binding["nativeIdentity"]["pid"], PID)
        self.assertEqual(binding["nativeIdentity"]["uniqueId"], 80001)

    def test_22_original_send_and_birth_must_be_inside_original_product_interval(self):
        changes = (("productStartedUtc", utc(BIRTH + 1)), ("productEndedUtc", utc(BEFORE)),
                   ("productStartedUtc", "2026-09-28T12:00:00"),
                   ("productEndedUtc", "2026-09-28T12:00:30+01:00"),
                   ("productEndedUtc", "2026-02-30T12:00:30Z"))
        for field, value in changes:
            with self.subTest(field=field, value=value):
                receipt = synthetic_receipt()
                receipt[field] = value
                self.assert_inconclusive(self.binding(receipt=receipt))

    def test_23_one_fixed_utc_log_query_not_emitter_pid_or_sliding_history(self):
        binding = self.binding()
        argv = self.helper.log_argv(binding)
        self.assertEqual(argv[:8], ["/usr/bin/log", "show", "--style", "json", "--info", "--debug", "--timezone", "UTC"])
        self.assertEqual(argv[8:13], ["--start", "2026-09-28 12:00:09", "--end", "2026-09-28 12:00:12", "--predicate"])
        self.assertEqual(len(argv), 14)
        self.assertEqual(predicate_shape(argv[-1]), predicate_shape(PREDICATE))
        self.assertNotIn(str(PID), argv[-1])
        self.assertNotIn("processID", argv[-1])
        for forbidden in ("--last", "stream", "sudo", "--privacy", "config", "enable"):
            self.assertNotIn(forbidden, argv)

    def test_24_query_edge_rounding_stays_below_two_seconds(self):
        for before, after, elapsed in ((BASE + 10_000, BASE + 11_000, 1_000_000_000),
                                       (BASE + 10_001, BASE + 10_002, 1_000_000),
                                       (BASE + 10_999, BASE + 11_000, 1_000_000)):
            with self.subTest(before=before, after=after):
                trace = self.helper.parse_fixture_trace(synthetic_trace(
                    utcBeforeMillis=before, utcAfterMillis=after,
                    monotonicBeforeNanos=0, monotonicAfterNanos=elapsed))
                binding = self.binding(trace)
                self.assertEqual(binding["status"], "BOUND")
                start = int(datetime.strptime(binding["queryStartUtc"], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc).timestamp()) * 1000
                end = int(datetime.strptime(binding["queryEndUtc"], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc).timestamp()) * 1000
                self.assertGreaterEqual(before - start, 1000)
                self.assertLess(before - start, 2000)
                self.assertGreaterEqual(end - after, 1000)
                self.assertLess(end - after, 2000)
                self.assertLessEqual(end - start, 50000)

    def test_25_binding_mutation_cannot_change_window_or_attribution(self):
        mutations = (
            lambda b: b.update(queryStartUtc="2026-09-28 00:00:00"),
            lambda b: b.update(queryEndUtc="2026-09-29 00:00:00"),
            lambda b: b.update(status="PASS"), lambda b: b.update(schema=True),
            lambda b: b.update(invocationId="wrong"), lambda b: b.update(extra="selector"),
            lambda b: b["trace"].update(pid=PID + 1), lambda b: b["trace"].update(ordinal=2),
            lambda b: b["trace"].update(destinationIpv4Mdns=False),
            lambda b: b["nativeIdentity"].update(startMicroseconds=124000),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                binding = self.binding()
                mutate(binding)
                with self.assertRaises(self.helper.DiagnosticError) as raised:
                    self.helper.log_argv(binding)
                self.assertRegex(str(raised.exception), r"\A[A-Z0-9_]+\Z")
                self.assert_inconclusive(self.helper.log_data(b"[]", b"", 0, binding))

    def test_26_closed_trace_schema_rejects_extra_fields_and_boolean_numbers(self):
        for field in ("schema", "pid", "birthEpochMillis", "ordinal", "utcBeforeMillis",
                      "monotonicBeforeNanos"):
            trace = self.helper.parse_fixture_trace(synthetic_trace())
            trace[field] = True
            self.assert_inconclusive(self.binding(trace))
        trace = self.helper.parse_fixture_trace(synthetic_trace())
        trace["responsiblePid"] = PID
        self.assert_inconclusive(self.binding(trace))

    def test_27_even_an_explicit_looking_synthetic_event_is_never_automatic_denial_acceptance(self):
        # No invented Apple schema is recognized as proof, even if the emitter
        # PID equals the fixture or the message claims an explicit client denial.
        for row in ({"processID": PID, "eventMessage": "synthetic policy denied"},
                    {"processID": 99, "eventMessage": f"synthetic client pid={PID} local network denied"},
                    {"processID": 99, "clientPid": PID, "responsiblePid": 77, "denied": True}):
            with self.subTest(emitter=row["processID"]):
                raw = json.dumps([row]).encode()
                result = self.helper.log_data(raw, b"", 0, self.binding())
                self.assert_inconclusive(result)
                self.assertEqual(result["reason"], "NATIVE_ORIGINAL_REVIEW_REQUIRED")
                self.assertEqual(result["recordCount"], 1)
                self.assertEqual(result["stdoutSha256"], digest(raw))
                self.assertEqual(result["stderrSha256"], digest(b""))
                self.assertEqual(result["exitCode"], 0)
                self.assertNotIn("eventMessage", result)
                self.assertNotIn("clientPid", result)
                self.assertNotIn("responsiblePid", result)

    def test_28_native_missing_nonzero_or_redacted_remains_inconclusive(self):
        cases = ((b"[]", b"", 0), (b"", b"", 0), (b"[]", b"permission denied", 1),
                 (b'[{"eventMessage":"<private>"}]', b"", 0),
                 (b'[{}]', b"<PRIVATE>", 0), (b"\xff", b"", 0), (b"[{}]", b"\xff", 0))
        for stdout, stderr, code in cases:
            with self.subTest(code=code, stdout_length=len(stdout), stderr_length=len(stderr)):
                result = self.helper.log_data(stdout, stderr, code, self.binding())
                self.assert_inconclusive(result)
                self.assertNotEqual(result["reason"], "NATIVE_ORIGINAL_REVIEW_REQUIRED")
                self.assertEqual(result.get("exitCode"), code)

    def test_29_native_invalid_json_or_shape_is_not_an_available_record(self):
        cases = (b"{}", b"null", b"true", b"[1]", b"[null]", b"[", b"[{},]",
                 b'[{"key":1,"key":2}]', b'[{"value":NaN}]', b'[{"value":Infinity}]')
        for raw in cases:
            with self.subTest(raw=raw):
                result = self.helper.log_data(raw, b"", 0, self.binding())
                self.assert_inconclusive(result)
                self.assertNotEqual(result["reason"], "NATIVE_ORIGINAL_REVIEW_REQUIRED")

    def test_30_native_combined_byte_limit_not_truncated_to_acceptance(self):
        stdout = b"[{}]"
        stderr = b" " * (1048576 - len(stdout))
        result = self.helper.log_data(stdout, stderr, 0, self.binding())
        self.assert_inconclusive(result)
        self.assertEqual(result["reason"], "NATIVE_ORIGINAL_REVIEW_REQUIRED")
        for out, err in ((stdout, stderr + b" "), (b" " * 1048577, b""), (None, b""), (stdout, None)):
            result = self.helper.log_data(out, err, 0, self.binding())
            self.assert_inconclusive(result)
            self.assertNotEqual(result["reason"], "NATIVE_ORIGINAL_REVIEW_REQUIRED")

    def test_31_native_timeout_reserved_signal_and_unknown_codes_never_look_successful(self):
        for code in (None, True, -9, 124, 125, 126, 127, 137, 255):
            with self.subTest(code=code):
                result = self.helper.log_data(b"[{}]", b"", code, self.binding())
                self.assert_inconclusive(result)
                self.assertNotEqual(result["reason"], "NATIVE_ORIGINAL_REVIEW_REQUIRED")

    def test_32_private_native_messages_are_represented_only_by_hashes(self):
        sentinel = "synthetic-private-message-not-evidence"
        for stdout, stderr in ((json.dumps([{"eventMessage": sentinel}]).encode(), b""),
                               (b"not-json-" + sentinel.encode(), sentinel.encode())):
            result = self.helper.log_data(stdout, stderr, 0, self.binding())
            self.assert_inconclusive(result)
            self.assertNotIn(sentinel, json.dumps(result))
            self.assertNotIn("stdout", result)
            self.assertNotIn("stderr", result)
            self.assertEqual(result["stdoutSha256"], digest(stdout))
            self.assertEqual(result["stderrSha256"], digest(stderr))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DiagnosticControls)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    if result.wasSuccessful():
        print(f"RESULT: PASS — {result.testsRun} focused synthetic/source controls; "
              "no Java, native-policy, provider, custody or hosted qualification")
    raise SystemExit(0 if result.wasSuccessful() else 1)
