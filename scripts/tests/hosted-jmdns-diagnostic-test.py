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
POLICY_JAVA = FIXTURE.with_name("JmdnsStartupPolicy.java")
POLICY_C = ROOT / "library/p2p-transport-lan/src/jvmTest/native/JmdnsStartupPolicy.c"
MODES = (
    "control", "failed_recovery", "shared_close", "close_wins", "recovery_wins",
    "responder_close", "callback_executor", "cleanup_retry",
)
TASKS = (
    ":p2p-transport-lan:jvmTest", "--tests",
    "dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest.realResourceCloseRegressionsExitNaturally",
    "--no-configure-on-demand",
)
# This closed JNI result is source/schema DATA, not a simulated native return.
POLICY_FIELDS = (
    "SCHEMA", "PID", "REAL_UID", "EFFECTIVE_UID", "INTERFACE_INDEX", "OUTCOME", "ELAPSED_NS",
    "CLOCK_ERRNO", "BROWSE_CODE", "REF_CREATED", "SOCKET_FD", "POLL_CALLS", "POLL_RETURN",
    "POLL_ERRNO", "POLL_REVENTS", "EINTR_RETRIES", "PROCESS_CODE", "CALLBACK_COUNT",
    "CALLBACK_OVERFLOW", "FIRST_CALLBACK_ERROR", "CALLBACK_POLICY_COUNT", "CALLBACK_CONTEXT_MISMATCH",
    "DEALLOCATE_ATTEMPTED", "DEALLOCATE_RETURNED", "POLICY_PHASE_MASK", "BUDGET_NS",
)
POLICY_OUTCOMES = (
    "ADMISSION_REFUSED", "CLOCK_FAILED", "BROWSE_ERROR", "REFERENCE_UNAVAILABLE", "SOCKET_UNAVAILABLE",
    "POLL_TIMED_OUT", "POLL_FAILED", "EINTR_EXHAUSTED", "BUDGET_ELAPSED", "PROCESS_RETURNED",
    "REENTRANT_REFUSED",
)
POLICY_PROPERTIES = (
    "p2pkit.audit.jmdnsPolicyLibrary", "p2pkit.audit.jmdnsPolicyLibrarySha256",
    "p2pkit.audit.jmdnsPolicyLibraryIdentity", "p2pkit.audit.jmdnsPolicyRecordSha256",
    "p2pkit.audit.jmdnsPolicyJavaHome",
)
POLICY_HOOK = '''            if (first.ordinal == 1) {
                JmdnsStartupPolicy.report(fixture.mode, snapshot.selected.index, () -> {
                    NetworkInterface current = matchedNetwork(fixture);
                    return current == null ? -1 : current.getIndex();
                });
            }
'''
# Exact opt-in additions requiring independent review. Remove only these bytes at their
# required anchors before comparing the original accepted full-file hashes.
# These are SOURCE controls, not Kotlin/Gradle execution or primitive evidence.
LAUNCHER_OPT_IN = r'''    private fun startupDiagnosticJvmArguments(mode: String): Array<String> {
        val startupPrimitives = System.getProperty("p2pkit.audit.jmdnsStartupPrimitives")
        val pythonExecutable = System.getProperty("p2pkit.audit.pythonExecutable")
        if (startupPrimitives == null && pythonExecutable == null) return emptyArray()
        require(startupPrimitives == "true" && pythonExecutable != null) {
            "JmDNS startup diagnostics require both explicit properties"
        }
        val python = File(pythonExecutable)
        require(
            pythonExecutable.toByteArray(Charsets.UTF_8).size in 1..16_384 &&
                pythonExecutable.none { it < ' ' || it == '\u007f' } &&
                python.isAbsolute && python.isFile && python.canExecute() &&
                runCatching { python.canonicalPath == pythonExecutable }.getOrDefault(false),
        ) { "JmDNS startup diagnostics require a canonical executable interpreter" }
        if (mode != "control") return emptyArray()
        // The fixture probes only after a captured failure and still rethrows that failure.
        return arrayOf(
            "-Dp2pkit.audit.jmdnsStartupPrimitives=true",
            "-Dp2pkit.audit.pythonExecutable=$pythonExecutable",
        )
    }

'''
LAUNCHER_OPT_IN_ARGUMENT = "                *startupDiagnosticJvmArguments(mode),\n"
GRADLE_OPT_IN_PROVIDERS = '''val jmdnsStartupPrimitives = providers.gradleProperty("p2pkit.audit.jmdnsStartupPrimitives")
val jmdnsStartupPython = providers.gradleProperty("p2pkit.audit.pythonExecutable")
'''
GRADLE_OPT_IN_INPUTS = '''    inputs.property("p2pkit.audit.jmdnsStartupPrimitives", jmdnsStartupPrimitives).optional(true)
    inputs.property("p2pkit.audit.pythonExecutable", jmdnsStartupPython).optional(true)
'''
GRADLE_OPT_IN = r'''        // Only the manual diagnostic supplies this coupled opt-in; defaults forward nothing.
        val startupPrimitives = jmdnsStartupPrimitives.orNull
        val pythonExecutable = jmdnsStartupPython.orNull
        if (startupPrimitives != null || pythonExecutable != null) {
            require(startupPrimitives == "true" && pythonExecutable != null) {
                "JmDNS startup diagnostics require both explicit properties"
            }
            val python = File(pythonExecutable)
            require(
                pythonExecutable.toByteArray(Charsets.UTF_8).size in 1..16_384 &&
                    pythonExecutable.none { it < ' ' || it == '\u007f' } &&
                    python.isAbsolute && python.isFile && python.canExecute() &&
                    runCatching { python.canonicalPath == pythonExecutable }.getOrDefault(false)
            ) { "JmDNS startup diagnostics require a canonical executable interpreter" }
            systemProperty("p2pkit.audit.jmdnsStartupPrimitives", "true")
            systemProperty("p2pkit.audit.pythonExecutable", pythonExecutable)
        }
'''
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


def between(text, first, last):
    """Unique source anchors, never a parser for runtime or private evidence."""
    assert text.count(first) == 1 and text.count(last) == 1, "policy source boundary changed"
    start, end = text.index(first), text.index(last)
    assert start < end, "policy source boundary order changed"
    return text[start:end]


def ordered_once(text, *parts):
    assert all(text.count(part) == 1 for part in parts), "policy source operation missing or duplicated"
    positions = [text.index(part) for part in parts]
    assert positions == sorted(positions), "policy source operation order changed"


def marked_block(text, label, indent="", *, blank_after=False):
    first, last = (indent + "// " + word + " JMDNS_POLICY_" + label + "\n"
                   for word in ("BEGIN", "END"))
    assert text.count(first) == 1 and text.count(last) == 1, "policy addition absent or duplicated"
    start, end = text.index(first), text.index(last)
    assert start < end, "policy addition boundary order changed"
    end += len(last)
    if blank_after:
        assert text[end:end + 1] == "\n", "policy addition separator changed"
        end += 1
    return text[start:end]


def normalize_policy_hook(text):
    before = "            nativeSend(python, snapshot.selected, fixture.address);\n"
    after = "        }\n\n        private static NetworkInterface matchedNetwork(Fixture fixture) throws IOException {\n"
    assert text.count(POLICY_HOOK) == 1, "policy hook missing or duplicated"
    assert text.count(before + POLICY_HOOK + after) == 1, "policy hook moved before the existing pair"
    assert text.count("JmdnsStartupPolicy.report(") == 1, "policy diagnostic gained another caller"
    assert "System.load" not in text, "fixture gained default/eager native loading"
    normalized = text.replace(POLICY_HOOK, "", 1)
    primitives = between(normalized, "    private static final class StartupPrimitives {\n",
                         "    private static final class Controls {\n").encode()
    # Pre-addition e970c5f2 source bytes, not a refreshed expectation for the
    # repair: every original JDK/Python predicate, order and limit stays intact.
    assert len(primitives) == 12573
    assert digest(primitives) == "ba5cf99a326800179778ec74c95d1745bf2e398cb96b89dd6d61b3f11d449eb8"
    return normalized


def normalize_policy_consumers(launcher, wiring):
    child = marked_block(launcher, "CONTROL_PROPERTIES", "    ", blank_after=True)
    arguments = marked_block(launcher, "CONTROL_ARGUMENTS", "            ")
    consumer = marked_block(wiring, "COMPILE_RECORD_CONSUMER")
    forwarding = marked_block(wiring, "COMPILE_RECORD_FORWARDING", "            ")
    assert launcher.count("    }\n\n" + child + "    private fun runChild(") == 1, "child helper moved"
    assert launcher.count('            "-Dp2pkit.audit.pythonExecutable=$pythonExecutable",\n'
                          + arguments + "        )\n") == 1, "child property forwarding escaped original control gate"
    assert arguments == ("            // BEGIN JMDNS_POLICY_CONTROL_ARGUMENTS\n"
                         "            *policyDiagnosticJvmArguments(),\n"
                         "            // END JMDNS_POLICY_CONTROL_ARGUMENTS\n")
    assert wiring.count("}\n" + consumer + GRADLE_OPT_IN_PROVIDERS) == 1, "consumer definition moved"
    assert wiring.count('            ) { "JmDNS startup diagnostics require a canonical executable interpreter" }\n'
                        + forwarding + '            systemProperty("p2pkit.audit.jmdnsStartupPrimitives", "true")\n') == 1, \
        "consumer preflight escaped coupled opt-in"
    assert forwarding == '''            // BEGIN JMDNS_POLICY_COMPILE_RECORD_FORWARDING
            val diagnosticLauncher = javaLauncher.get().metadata
            require(diagnosticLauncher.languageVersion.asInt() == 17) { "JmDNS policy diagnostics require JDK 17" }
            consumeJmdnsPolicyCompileRecord(rootProject.projectDir, diagnosticLauncher.installationPath.asFile)
                .forEach { (key, value) -> systemProperty(key, value) }
            // END JMDNS_POLICY_COMPILE_RECORD_FORWARDING
''', "actual Test JDK/consumer forwarding changed"
    assert launcher.count("policyDiagnosticJvmArguments(") == 2
    assert wiring.count("consumeJmdnsPolicyCompileRecord(") == 2
    for text in (child, consumer):
        assert sorted(re.findall(r'"(p2pkit\.audit\.jmdnsPolicy[A-Za-z0-9]+)"', text)) == sorted(POLICY_PROPERTIES)
        for forbidden in ("ProcessBuilder", "System.load", "Runtime.getRuntime", "Files.create", "Files.write",
                          "Thread.sleep", "new Thread"):
            assert forbidden not in text, "consumer gained execution/production work"
        assert not re.search(r"\b(?:exec|javaexec)\s*[({]", text), "Gradle consumer gained a compiler task"
    for token in (
        "requireNotNull(System.getProperty(it))", "path.toByteArray(Charsets.UTF_8).size in 1..16_384",
        "File(path).canonicalPath == path", "components.size == 8", "it.toLongOrNull()",
        "(identity[2] and 0xf000L) == 0x8000L", "(identity[2] and 0x12L) == 0L",
        "identity[4] == 1L && identity[5] in 1L..1_048_576L", "Runtime.version().feature() == 17",
        'File(System.getProperty("java.home")).canonicalPath == javaHomePath',
        'return names.map { "-D$it=${values.getValue(it)}" }.toTypedArray()',
    ):
        assert token in child, "child JDK/property data validation changed"

    # Inspect the maintained Kotlin parser/consumer source, not a Python clone
    # of it. Runtime JSON/NIO/JDK validation remains a separate hosted task.
    fields = {
        "record": ("schema", "scope", "requestSha256", "request", "github", "invocationId", "jobId",
                   "candidateRoot", "controllerRoot", "javaHome", "architecture", "developerDir", "sdk",
                   "sourceGitBlob", "startedMonotonicNs", "endedMonotonicNs", "status", "reason", "inputs",
                   "observations", "compiler", "artifact"),
        "declaration": ("schema", "scope", "request", "github", "startedMonotonicNs", "deadlineMonotonicNs",
                        "observationBudgetNs"),
        "request": ("operation", "controller_sha", "controller_tree", "candidate_sha", "candidate_tree",
                    "dependency_base_sha"),
        "inputs": ("source", "clang", "jniHeader", "jniPlatformHeader", "dnsSdHeader", "linkerStub", "javaRelease"),
        "observations": ("findClang", "findSdk", "clangVersion", "dylibSignature", "dylibUuid"),
    }
    for name, expected in fields.items():
        matches = re.findall(r"        val " + name + r" = objectData\([^\n]+, setOf\(\n(.*?)\n        \)\)",
                             consumer, re.DOTALL)
        assert len(matches) == 1, "consumer closed field-set boundary changed"
        assert tuple(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', matches[0])) == expected, "consumer closed schema changed"
    for token in (
        'fun consumeJmdnsPolicyCompileRecord(candidateRoot: File, javaHome: File): Map<String, String> {',
        'demand(!result.containsKey(key), "JSON_DUPLICATE_KEY")', "depth <= 32 && ++values <= 32_768",
        'demand(offset == text.length, "JSON_TRAILING_DATA")', "CodingErrorAction.REPORT",
        'fun integer(value: Any?): Long = value as? Long ?: refusal("INTEGER_TYPE")',
        "fields == null || result.keys == fields", "java.nio.file.LinkOption.NOFOLLOW_LINKS",
        'info[2] == 0x41c0L && info[3] == ownerUid',
        'listOf(state, state.resolve("evidence"), records, directory.parent.parent, directory.parent, directory)',
        'val raw = read(records.resolve("jmdns-policy-compile.json"), 256 * 1024)',
        'demand(raw.contentEquals(read(directory.resolve("compile-record.json"), 256 * 1024)), "RECORD_COPY")',
        'record["status"] == "COMPILED" && record["reason"] == "READY_FOR_FAILURE_ONLY_DIAGNOSTIC"',
        'hash(record["requestSha256"]) == checksum(requestRaw)',
        'request == declaration["request"] && request["operation"] == "diagnose-jmdns"',
        'github["runId"] == environment("GITHUB_RUN_ID")',
        'github["runAttempt"] == environment("GITHUB_RUN_ATTEMPT")',
        'environment("GITHUB_SHA") == request["controller_sha"]',
        'environment("GITHUB_WORKFLOW_SHA") == request["controller_sha"]',
        'source["commit"] == request["controller_sha"]', 'source["tree"] == request["controller_tree"]',
        'invocation == environment("P2PKIT_AUDIT_OWNERSHIP_CHAIN")',
        'job == environment("P2PKIT_AUDIT_JOB_ID") && job == context["id"]',
        'context["gradleHome"] == environment("GRADLE_USER_HOME")',
        'developer.toString() == "/Applications/Xcode_26.5.app/Contents/Developer"',
        'java.nio.file.Files.isDirectory(sdk, noFollow) && headerHome == launcherHome',
        'physical(absolute(environment("JAVA_HOME")).toRealPath()) == headerHome',
        "requestDeadline - requestStarted == 1200_000_000_000L",
        'integer(declaration["observationBudgetNs"]) == 120_000_000_000L',
        "ended - requestStarted < 120_000_000_000L", "identity(row) == ownedFile(expected, limit.toLong(), installed)",
        'checksum(cRaw) == cInput["sha256"]', 'checksum(blob, "SHA-1") == hash(record["sourceGitBlob"], 40)',
        'checksum(read(library, 1024 * 1024)) == artifact["sha256"]',
        'row["status"] == "RETURNED" && row["argv"] == argv && code in 0L..123L',
        "(!required || code == 0L)", "if (compiler) 30_000_000_000L else 5_000_000_000L",
        'observation(record["compiler"], "policy-native-compile", listOf(', "), true, compiler = true)",
        'for ((path, expected) in pinned) demand(physical(path).let(::stat) == expected, "FINAL_FILE_CHANGED")',
        'demand(physical(path).let(::stat).take(4) == expected, "FINAL_PARENT_CHANGED")',
        'demand(previousEnd <= positive(row["startedMonotonicNs"]), "OBSERVATION_ORDER")',
        '1_048_576L, "COMPILER_OUTPUT_BOUND")',
        'throw org.gradle.api.GradleException("JmDNS policy preflight: ${failure.code}")',
        'throw org.gradle.api.GradleException("JmDNS policy preflight: INPUT_UNAVAILABLE_OR_MALFORMED")',
    ):
        assert token in consumer, "consumer source/run/JDK/compile/artifact validation changed"
    return launcher.replace(child, "", 1).replace(arguments, "", 1), \
        wiring.replace(consumer, "", 1).replace(forwarding, "", 1)


def java_policy_source_guard(source):
    expected = {name: index for index, name in enumerate((*POLICY_FIELDS, "RESULT_FIELDS"))}
    expected.update({name: index + 1 for index, name in enumerate(POLICY_OUTCOMES)})
    for name, number in expected.items():
        actual = re.findall(r"\b" + name + r"\s*=\s*([0-9][0-9_]*)(?:L)?(?=\s*[,;])", source)
        assert actual == [str(number)], "Java/C numeric result schema diverged"
    for token in (
        'private static final String PROPERTY_PREFIX = "p2pkit.audit.jmdnsPolicy";',
        '"library/p2p-transport-lan/build/reports/jmdns-policy-native/libp2pkit-jmdns-policy.dylib"',
        'private static final String RECORD_NAME = "compile-record.json";',
        "private static final long LIBRARY_LIMIT = 1_048_576;",
        "private static final long RECORD_LIMIT = 262_144;",
        "private static final long NORMAL_BUDGET_NS = 1_000_000_000L;",
        "private static final long OUTER_WATCHDOG_NS = 45_000_000_000L;",
        "private static final long UNOBSERVED = Long.MIN_VALUE;",
        "private static final int POLICY_DENIED = -65570;",
        "private static final int CALLBACK_LIMIT = 32;",
        "private static final int EINTR_RETRY_LIMIT = 4;",
        "private static native long[] browse0(int interfaceIndex, long expectedPid, long expectedUid);",
    ):
        assert source.count(token) == 1, "policy Java fixed schema/path/limit changed"
    properties = re.findall(r'PROPERTY_PREFIX \+ "([A-Za-z0-9]+)"', source)
    assert sorted("p2pkit.audit.jmdnsPolicy" + suffix for suffix in properties) == sorted(POLICY_PROPERTIES)
    assert source.count("System.load(") == 1 and source.count("browse0(") == 2
    assert not re.search(r"\bstatic\s*\{", source), "policy gained eager class-initializer work"
    for token in ("System.loadLibrary", "Runtime.getRuntime", "ProcessBuilder", "new Thread", "System.getenv",
                  "System.setProperty", "Files.create", "Files.write", "getMessage()", "printStackTrace"):
        assert token not in source, "policy Java gained another authority path or raw diagnostic output"

    report = between(source, "    static void report(String mode, int interfaceIndex, MatchedInterface currentInterface) {\n",
                     "    private static Handoff handoff() throws IOException {\n")
    ordered_once(report, 'if (!"true".equals(System.getProperty("p2pkit.audit.jmdnsStartupPrimitives")))',
                 'require("control".equals(mode) && "Mac OS X".equals(System.getProperty("os.name"))',
                 "Handoff handoff = handoff();", "FileIdentity recordIdentity = verifyFile(",
                 "long pid = ProcessHandle.current().pid();", "ATTEMPTED.compareAndSet(false, true)",
                 'phase = "LOAD_ATTEMPT";', "System.load(handoff.library.toString());",
                 'phase = "LOAD_RETURNED";', 'phase = "NATIVE_CALL_ATTEMPT";',
                 "long[] result = browse0(interfaceIndex, pid, handoff.originalLibrary.uid);",
                 'phase = "NATIVE_RETURNED";', "validateResult(result, interfaceIndex, pid, handoff.originalLibrary.uid",
                 "boolean denied =", 'phase = "OBSERVATION";', "} catch (Refusal refusal)", "} catch (Throwable failure)")
    assert report.count("currentInterface.currentIndex() == interfaceIndex") == 3
    assert report.count("!Thread.currentThread().isInterrupted()") == 3
    assert report.count("verifyHandoff(handoff, recordIdentity);") == 2
    ordered_once(report, "long loadMonotonicBefore = System.nanoTime();",
                 "long loadUtcBefore = System.currentTimeMillis();", "System.load(handoff.library.toString());",
                 "long loadUtcAfter = System.currentTimeMillis();", "long loadMonotonicAfter = System.nanoTime();",
                 "enclosedElapsed(loadMonotonicBefore, loadMonotonicAfter, loadUtcBefore, loadUtcAfter);",
                 "long monotonicBefore = System.nanoTime();", "long utcBefore = System.currentTimeMillis();",
                 "long[] result = browse0(interfaceIndex, pid, handoff.originalLibrary.uid);",
                 "long utcAfter = System.currentTimeMillis();", "long monotonicAfter = System.nanoTime();",
                 "long elapsed = enclosedElapsed(monotonicBefore, monotonicAfter, utcBefore, utcAfter);",
                 "validateResult(result, interfaceIndex, pid, handoff.originalLibrary.uid, elapsed);")
    native_attempt = between(report, '            phase = "NATIVE_CALL_ATTEMPT";\n',
                             '            phase = "NATIVE_RETURNED";\n')
    ordered_once(native_attempt, "require(!Thread.currentThread().isInterrupted()",
                 "currentInterface.currentIndex() == interfaceIndex, Reason.INTERFACE);",
                 "long[] result = browse0(interfaceIndex, pid, handoff.originalLibrary.uid);")
    for token in (
        "Runtime.version().feature() == 17", "interfaceIndex > 0 && currentInterface != null",
        "result[POLICY_PHASE_MASK] != 0 && result[CLOCK_ERRNO] == 0",
        "result[CALLBACK_CONTEXT_MISMATCH] == 0 && result[CALLBACK_OVERFLOW] == 0",
        'denied ? "POLICY_DENIED_POST_FAILURE_OPERATION" : "UNKNOWN"',
        "priorSendCause=UNKNOWN lifecycleAcceptance=NOT_PERFORMED",
        'emit(phase, "result=UNKNOWN reason=" + refusal.reason.name());',
        'emit(phase, "result=UNKNOWN reason=DIAGNOSTIC_FAILURE");',
    ):
        assert token in report, "policy result attribution/caller guard changed"
    assert not re.search(r'"[^"\n]*(?:result=PASS|priorSendCause=POLICY|lifecycleAcceptance=PASS)', report)

    handoff = between(source, "    private static Handoff handoff() throws IOException {\n",
                      "    private static long number(Object value) {\n")
    for token in (
        "require(library.endsWith(LIBRARY_SUFFIX), Reason.PATH);",
        "Path record = library.getParent().resolve(RECORD_NAME);",
        'javaHome.equals(Path.of(System.getProperty("java.home", "")).toRealPath())',
        'value.matches("[0-9a-f]{64}")', "value.getBytes(StandardCharsets.UTF_8).length <= 16_384",
        "path.isAbsolute() && path.toString().equals(value) && path.equals(path.normalize())",
        "!attributes.isSymbolicLink() && (item.equals(path) || attributes.isDirectory())",
        "identity.uid == owner && (identity.mode & 0170000) == 0040000",
        "(identity.mode & 07777) == 0700",
        "before.regular(owner, maximum);", "original == null || before.equals(original)",
        "Files.newInputStream(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)",
        "size <= maximum", "before.equals(after) && (original == null || after.equals(original))",
        "size == before.size && HexFormat.of().formatHex(digest.digest()).equals(expectedHash)",
        "for (int level = 0; level < 3; level++)", "path = path.getParent();",
        "privateReportDirectories(library.getParent(), original.uid);",
        "privateReportDirectories(handoff.library.getParent(), handoff.originalLibrary.uid);",
    ):
        assert token in handoff, "policy Java physical/JDK/hash/stat admission changed"
    assert handoff.count('javaHome.equals(Path.of(System.getProperty("java.home", "")).toRealPath())') == 2
    identity = between(source, "    private record FileIdentity(", "    private record Handoff(")
    for token in ("parts.length == 8", '"unix:dev,ino,mode,uid,nlink,size,lastModifiedTime,ctime"',
                  "LinkOption.NOFOLLOW_LINKS", "(mode & 0170000) == 0100000 && (mode & 0022) == 0",
                  "uid == owner && uid >= 0 && uid <= UINT32_MAX && links == 1",
                  "size > 0 && size <= maximum && mtimeNanos > 0 && ctimeNanos > 0"):
        assert token in identity, "policy library original raw-stat identity changed"
    validation = between(source, "    private static void validateResult(", "    private static String rawResult(")
    for token in (
        "value != null && value.length == RESULT_FIELDS && value[SCHEMA] == 1",
        "value[PID] == pid && value[REAL_UID] == uid && value[EFFECTIVE_UID] == uid",
        "value[INTERFACE_INDEX] == interfaceIndex", "value[field] == 0 || value[field] == 1",
        "value[CLOCK_ERRNO] == 0 ? value[ELAPSED_NS] >= 0 && value[ELAPSED_NS] <= javaElapsed",
        "value[DEALLOCATE_ATTEMPTED] == value[REF_CREATED]",
        "value[DEALLOCATE_RETURNED] == value[REF_CREATED]",
        "value[POLL_CALLS] <= EINTR_RETRY_LIMIT + 1", "value[EINTR_RETRIES] <= EINTR_RETRY_LIMIT",
        "value[CALLBACK_COUNT] <= CALLBACK_LIMIT", "value[CALLBACK_POLICY_COUNT] <= value[CALLBACK_COUNT]",
        "value[CALLBACK_OVERFLOW] == 0 || value[CALLBACK_COUNT] == CALLBACK_LIMIT",
        "value[OUTCOME] == PROCESS_RETURNED && readable(value)",
        "value[BROWSE_CODE] != 0 || value[REF_CREATED] == 0", "value[PROCESS_CODE] == UNOBSERVED",
        "long mask = (value[BROWSE_CODE] == POLICY_DENIED ? 1 : 0)",
        "| (value[PROCESS_CODE] == POLICY_DENIED ? 2 : 0)",
        "| (value[CALLBACK_POLICY_COUNT] > 0 ? 4 : 0)", "value[POLICY_PHASE_MASK] == mask",
        "default -> throw new Refusal(Reason.NATIVE_SCHEMA);",
    ):
        assert token in validation, "policy native return cross-field validation changed"
    outcomes = re.findall(r"case ([A-Z_]+)(?:, ([A-Z_]+))? ->", validation)
    assert sorted(item for pair in outcomes for item in pair if item) == sorted(POLICY_OUTCOMES)
    raw = between(source, "    private static String rawResult(", "    private static void emit(")
    assert "result == null || result.length != RESULT_FIELDS" in raw and "index < RESULT_FIELDS" in raw
    clocks = between(source, "    private static long enclosedElapsed(", "    private static void validateResult(")
    assert "long elapsed = monotonicAfter - monotonicBefore;" in clocks
    assert "elapsed >= 0 && elapsed <= OUTER_WATCHDOG_NS && utcBefore > 0" in clocks
    assert "utcAfter >= utcBefore && utcAfter - utcBefore <= 45_000" in clocks


def native_policy_source_guard(source):
    # These checks inspect the actual C source. They do not execute a Python
    # replacement for JNI, validate compiler output, or establish OS behavior.
    def enum(name):
        body = between(source, "enum " + name + " {\n", "};\n\n" + (
            "enum outcome" if name == "result_field" else "enum { CALLBACK_LIMIT"))
        declarations = body.split("{", 1)[1].strip().split(",")
        pairs = [re.fullmatch(r"\s*([A-Z][A-Z0-9_]*)\s*=\s*([0-9]+)\s*", item)
                 for item in declarations]
        assert all(pairs), "policy enum is not the closed numeric schema"
        values = {match[1]: int(match[2]) for match in pairs}
        assert len(values) == len(pairs), "policy enum duplicated a field"
        return values

    assert enum("result_field") == {name: index for index, name in enumerate((*POLICY_FIELDS, "RESULT_FIELDS"))}
    assert enum("outcome") == {name: index + 1 for index, name in enumerate(POLICY_OUTCOMES)}
    for token in (
        "#if !defined(__APPLE__) || (!defined(__arm64__) && !defined(__aarch64__))",
        "enum { CALLBACK_LIMIT = 32, EINTR_RETRY_LIMIT = 4 };",
        "static const jlong UNOBSERVED = INT64_MIN;",
        "static const int64_t NORMAL_BUDGET_NS = INT64_C(1000000000);",
        "_Static_assert(kDNSServiceErr_PolicyDenied == -65570,",
        "_Static_assert(sizeof(jlong) == 8 && sizeof(jint) == 4,",
        "_Static_assert(sizeof(DNSServiceErrorType) == 4,",
        "static _Thread_local struct browse_context *active_context;",
    ):
        assert source.count(token) == 1, "policy native fixed bound/schema changed"

    callback = between(source, "static void DNSSD_API browse_reply(", "static int monotonic_ns(")
    ordered_once(callback, "struct browse_context *state = active_context;", "if (state == NULL)",
                 "if (state->callback_count < CALLBACK_LIMIT)", "if (!state->processing)",
                 "if (error != kDNSServiceErr_NoError)",
                 "return; /* Do not read any other reply argument on an error. */",
                 "if (reference != state->reference || context != state",
                 "|| interface_index != state->interface_index)")
    error_branch = between(callback, "    if (error != kDNSServiceErr_NoError) {\n",
                           "    if (reference != state->reference || context != state\n")
    for name in ("reference", "flags", "interface_index", "service_name", "regtype", "reply_domain", "context"):
        assert not re.search(r"\b" + name + r"\b", error_branch), "error callback read undefined reply data"
    assert "error == kDNSServiceErr_PolicyDenied && state->policy_count < CALLBACK_LIMIT" in error_branch
    assert "state->first_error = error;" in error_branch and "state->policy_count++;" in error_branch
    assert "state->callback_overflow = 1;" in callback

    entry = source[source.index("JNIEXPORT jlongArray JNICALL\n"):]
    ordered_once(entry, "jlong expected_pid, jlong expected_uid)", "values[PID] = (jlong) getpid();",
                 "values[REAL_UID] = (jlong) (uint64_t) getuid();",
                 "values[EFFECTIVE_UID] = (jlong) (uint64_t) geteuid();",
                 "deadline = started + NORMAL_BUDGET_NS;", "if (interface_index <= 0 || expected_pid <= 0",
                 "if (active_context != NULL)", "active_context = &state;",
                 "DNSServiceBrowse(&reference, 0, state.interface_index,\n"
                 '            "_p2pkit-audit._tcp", "local.", browse_reply, &state);')
    for token in ("values[PID] != expected_pid || values[REAL_UID] != expected_uid",
                  "values[EFFECTIVE_UID] != expected_uid", "expected_pid > INT32_MAX",
                  "(uint64_t) expected_uid > UINT32_MAX"):
        assert token in entry, "JNI actual caller identity guard changed"
    for call in ("DNSServiceBrowse", "DNSServiceRefSockFD", "DNSServiceProcessResult", "DNSServiceRefDeallocate",
                 "poll", "NewLongArray", "SetLongArrayRegion"):
        assert len(re.findall(r"\b" + call + r"\s*\(", source)) == 1, "policy native operation repeated"
    for call in ("close", "socket", "bind", "connect", "send", "sendto", "system", "popen", "fork",
                 "pthread_create", "dispatch_async", "DNSServiceRegister", "DNSServiceResolve",
                 "DNSServiceSetDispatchQueue", "printf", "fprintf", "puts", "NewStringUTF"):
        assert not re.search(r"\b" + call + r"\s*\(", source), "policy native gained an unadmitted operation"
    ordered_once(entry, "if (values[BROWSE_CODE] != kDNSServiceErr_NoError)", "if (reference == NULL)",
                 "values[REF_CREATED] = 1;", "values[SOCKET_FD] = DNSServiceRefSockFD(reference);",
                 "for (;;) {", "ready = poll(&descriptor, 1, timeout_ms);", "state.processing = 1;",
                 "values[PROCESS_CODE] = DNSServiceProcessResult(reference);", "state.processing = 0;",
                 "values[OUTCOME] = PROCESS_RETURNED;", "finished:", "if (values[REF_CREATED])",
                 "values[DEALLOCATE_ATTEMPTED] = 1;", "DNSServiceRefDeallocate(reference);",
                 "values[DEALLOCATE_RETURNED] = 1;", "active_context = NULL;",
                 "returned = (*env)->NewLongArray(env, RESULT_FIELDS);")
    loop = between(entry, "    for (;;) {\n", "\nfinished:\n")
    for token in (
        "if (now >= deadline)", "clock_error = monotonic_ns(&now);",
        "timeout_ms = (int) ((deadline - now + NS_PER_MILLISECOND - 1) / NS_PER_MILLISECOND);",
        "if (ready < 0 && error == EINTR)", "if (values[EINTR_RETRIES] == EINTR_RETRY_LIMIT)",
        "values[EINTR_RETRIES]++;", "values[OUTCOME] = EINTR_EXHAUSTED;",
        "if (ready != 1 || !(descriptor.revents & POLLIN)",
        "|| (descriptor.revents & (POLLERR | POLLHUP | POLLNVAL)))",
    ):
        assert token in loop, "policy native poll deadline/retry/readiness guard changed"
    assert len(re.findall(r"\bdeadline\s*(?:\+=|=)", entry)) == 2, "native deadline was refilled"
    assert loop.count("if (now >= deadline)") == 2 and loop.count("continue;") == 1
    assert "values[POLICY_PHASE_MASK] = (values[BROWSE_CODE] == kDNSServiceErr_PolicyDenied ? 1 : 0)" in entry
    assert "| (values[PROCESS_CODE] == kDNSServiceErr_PolicyDenied ? 2 : 0)" in entry
    assert "| (state.policy_count != 0 ? 4 : 0);" in entry


def fixture_source_guard(text):
    # These are preserved accepted SOURCE regions from b19780f0, not regenerated
    # native evidence/expected-output hashes. Only the approved report(mode)
    # argument addition is normalized when comparing the original main method.
    # First remove the new exact failure-only hook so the old tail pin remains
    # unchanged, including every byte of the accepted StartupPrimitives pair.
    text = normalize_policy_hook(text)
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


def opt_in_handoff_source_guard(launcher, wiring):
    def remove_at(text, addition, before, after):
        assert text.count(addition) == 1, "approved optional block missing or duplicated"
        assert text.count(before + addition + after) == 1, "approved optional block moved"
        return text.replace(addition, "", 1)

    launcher, wiring = normalize_policy_consumers(launcher, wiring)
    launcher = remove_at(launcher, LAUNCHER_OPT_IN, "    }\n\n",
                        "    private fun runChild(mode: String, classpath: String, reports: File) {\n")
    launcher = remove_at(launcher, LAUNCHER_OPT_IN_ARGUMENT,
                        '                "-Dorg.slf4j.simpleLogger.defaultLogLevel=off",\n',
                        '                "-cp",\n')
    assert digest(launcher.encode()) == "1eee1f8352a615c5c4aa543aa63837d9112c050c336677d2e3015d237fe27ec7", \
        "original launcher modes, arguments, limits or natural-exit assertions changed"
    wiring = remove_at(wiring, "import java.io.File\n",
                       "import dev.p2pkit.build.WriteXcframeworkProvenanceTask\n",
                       "import org.gradle.api.tasks.compile.JavaCompile\n")
    wiring = remove_at(wiring, GRADLE_OPT_IN_PROVIDERS, "}\n",
                       'val jmdnsCloseFixtureReports = layout.buildDirectory.dir("reports/jmdns-close")\n')
    wiring = remove_at(wiring, GRADLE_OPT_IN_INPUTS,
                       '    outputs.dir(jmdnsCloseFixtureReports).withPropertyName("jmdnsCloseFixtureReports")\n',
                       "    // Gradle's worker java.class.path need not contain the test runtime. The\n")
    wiring = remove_at(wiring, GRADLE_OPT_IN,
                       '        systemProperty("p2pkit.jmdns.fixture.outputDir", jmdnsCloseFixtureReports.get().asFile.absolutePath)\n',
                       "    }\n}\n")
    assert digest(wiring.encode()) == "b8d22cf058d3b43b7cd694b8552a5bfd8a429ad0ec3bfe1556934008cc623847", \
        "original Gradle task graph, classpath or non-diagnostic wiring changed"


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
        # Only exact anchored opt-in additions are removed. Original b19780f0
        # full-file pins still protect modes/order, classpath, JDK17,45s/5s,
        # heap/metaspace/processor flags and natural/no-rescue acceptance.
        opt_in_handoff_source_guard(LAUNCHER.read_text(encoding="utf-8"), WIRING.read_text(encoding="utf-8"))
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

    def test_33_diagnostic_opt_in_has_exact_original_selector_and_two_tokens(self):
        paths = ("/synthetic-python/bin/python3.12", "/synthetic Python/bin/python3.12",
                 "/synthetic-\u00e9/bin/python3.12")
        for path in paths:
            with self.subTest(path=path):
                expected = [*TASKS, "-Pp2pkit.audit.jmdnsStartupPrimitives=true",
                            "-Pp2pkit.audit.pythonExecutable=" + path]
                actual = self.helper.diagnostic_gradle_arguments(path)
                self.assertIs(type(actual), list)
                self.assertEqual(actual, expected)
                actual.append("synthetic-mutation")
                self.assertEqual(self.helper.diagnostic_gradle_arguments(path), expected)
        self.assertEqual(tuple(self.helper.GRADLE_ARGUMENTS), TASKS)
        self.assertFalse(any("p2pkit.audit." in token for token in self.helper.GRADLE_ARGUMENTS))

    def test_34_diagnostic_interpreter_lexical_admission_rejects_ambiguous_paths(self):
        boundary = "/" + "\u00e9" * 8191 + "x"
        self.assertEqual(len(boundary.encode("utf-8")), 16384)
        self.assertEqual(self.helper.diagnostic_gradle_arguments(boundary)[-1],
                         "-Pp2pkit.audit.pythonExecutable=" + boundary)
        paths = (None, True, b"/bin/python3", "", "/", "python3", "//bin/python3", "/bin/../python3",
                 "/bin/./python3", "/bin//python3", "/bin/python3/", "/bin/python3\n",
                 "/bin/\tpython3", "/bin/\0python3", "/bin/\x7fpython3", "/\ud800/python3",
                 "/" + "x" * 16384, boundary + "\u00e9")
        for path in paths:
            with self.subTest(path_type=type(path).__name__, length=len(path) if isinstance(path, str) else 0):
                with self.assertRaises(self.helper.DiagnosticError) as raised:
                    self.helper.diagnostic_gradle_arguments(path)
                self.assertRegex(str(raised.exception), r"\A[A-Z0-9_]+\Z")

    def test_35_handoff_guards_reject_partial_default_other_mode_and_surrounding_drift(self):
        launcher, wiring = LAUNCHER.read_text(encoding="utf-8"), WIRING.read_text(encoding="utf-8")
        launcher_mutations = (
            ("if (startupPrimitives == null && pythonExecutable == null) return emptyArray()", "return emptyArray()"),
            ('startupPrimitives == "true" && pythonExecutable != null', "pythonExecutable != null"),
            ('if (mode != "control") return emptyArray()', 'if (mode == "control") return emptyArray()'),
            ("python.canExecute()", "true"),
            ("python.canonicalPath == pythonExecutable", "true"),
            ('"-Dp2pkit.audit.jmdnsStartupPrimitives=true"', '"-Dp2pkit.audit.jmdnsStartupPrimitives=false"'),
            ('"-XX:ActiveProcessorCount=2"', '"-XX:ActiveProcessorCount=3"'),
            ("child.waitFor(45, TimeUnit.SECONDS)", "child.waitFor(46, TimeUnit.SECONDS)"),
            ("child.waitFor(5, TimeUnit.SECONDS)", "child.waitFor(6, TimeUnit.SECONDS)"),
            ('assertFalse(transcript.contains("phase=fixture_rescue_begin")', "assertFalse(false"),
        )
        for before, after in launcher_mutations:
            with self.subTest(launcher=before):
                self.assertIn(before, launcher)
                with self.assertRaises(AssertionError):
                    opt_in_handoff_source_guard(launcher.replace(before, after, 1), wiring)
        moved = launcher.replace(LAUNCHER_OPT_IN_ARGUMENT, "", 1).replace(
            "                classpath,\n", "                classpath,\n" + LAUNCHER_OPT_IN_ARGUMENT, 1)
        with self.assertRaises(AssertionError):
            opt_in_handoff_source_guard(moved, wiring)
        wiring_mutations = (
            ("startupPrimitives != null || pythonExecutable != null", "startupPrimitives != null && pythonExecutable != null"),
            ('startupPrimitives == "true" && pythonExecutable != null', "true"),
            ("python.isFile && python.canExecute()", "true"),
            ("python.canonicalPath == pythonExecutable", "true"),
            ('systemProperty("p2pkit.audit.pythonExecutable", pythonExecutable)', 'systemProperty("p2pkit.audit.pythonExecutable", "/different/python")'),
            (GRADLE_OPT_IN_INPUTS, ""),
            ('systemProperty("p2pkit.jmdns.fixture.classpath", classpath.asPath)', 'systemProperty("p2pkit.jmdns.fixture.classpath", "synthetic")'),
        )
        for before, after in wiring_mutations:
            with self.subTest(wiring=before):
                self.assertIn(before, wiring)
                with self.assertRaises(AssertionError):
                    opt_in_handoff_source_guard(launcher, wiring.replace(before, after, 1))
        with self.assertRaises(AssertionError):
            opt_in_handoff_source_guard(launcher + LAUNCHER_OPT_IN, wiring)

    def test_36_policy_hook_is_ordinal_one_failure_only_after_the_unchanged_primitive_pair(self):
        source = self.fixture_source
        fixture_source_guard(source)
        mutations = (
            ("if (first.ordinal == 1)", "if (first.ordinal > 0)"),
            ("NetworkInterface current = matchedNetwork(fixture);", "NetworkInterface current = network;"),
            ("return current == null ? -1 : current.getIndex();", "return snapshot.selected.index;"),
            ("JmdnsStartupPolicy.report(fixture.mode,", 'JmdnsStartupPolicy.report("control",'),
            ("jdkSend(network);", "nativeSend(python, snapshot.selected, fixture.address);"),
            ("nativeSend(python, snapshot.selected, fixture.address);", "jdkSend(network);"),
            ('!"control".equals(fixture.mode)', "false"),
            ("!(first.cause instanceof NoRouteToHostException)", "false"),
            ("!Boolean.TRUE.equals(first.ipv4Mdns)", "false"),
            ("Thread.currentThread().isInterrupted()", "false"),
            (POLICY_HOOK, POLICY_HOOK + POLICY_HOOK),
        )
        for before, after in mutations:
            with self.subTest(source=before):
                self.assertIn(before, source)
                with self.assertRaises(AssertionError):
                    fixture_source_guard(source.replace(before, after, 1))
        moved = source.replace(POLICY_HOOK, "", 1).replace("            jdkSend(network);\n",
                POLICY_HOOK + "            jdkSend(network);\n", 1)
        with self.assertRaises(AssertionError):
            fixture_source_guard(moved)
        with self.assertRaises(AssertionError):
            fixture_source_guard(source.replace("    private JmdnsCloseLifecycleFixture() {\n",
                '    static { System.load("/synthetic-not-a-library"); }\n\n'
                "    private JmdnsCloseLifecycleFixture() {\n", 1))

    def test_37_policy_consumer_is_data_only_bound_to_actual_test_jdk_and_original_records(self):
        launcher, wiring = LAUNCHER.read_text(encoding="utf-8"), WIRING.read_text(encoding="utf-8")
        opt_in_handoff_source_guard(launcher, wiring)
        launcher_mutations = (
            ('"p2pkit.audit.jmdnsPolicyRecordSha256",\n', ""),
            ('requireNotNull(System.getProperty(it))', '"synthetic-unbound-value"'),
            ("components.size == 8", "components.size >= 8"),
            ("(identity[2] and 0xf000L) == 0x8000L", "true"),
            ("identity[4] == 1L", "identity[4] > 0L"),
            ('File(System.getProperty("java.home")).canonicalPath == javaHomePath', "true"),
            ("*policyDiagnosticJvmArguments(),", ""),
        )
        for before, after in launcher_mutations:
            with self.subTest(launcher=before):
                self.assertIn(before, launcher)
                with self.assertRaises(AssertionError):
                    opt_in_handoff_source_guard(launcher.replace(before, after, 1), wiring)
        wiring_mutations = (
            ('diagnosticLauncher.languageVersion.asInt() == 17', 'diagnosticLauncher.languageVersion.asInt() == 21'),
            ('diagnosticLauncher.installationPath.asFile', 'File(System.getenv("JAVA_HOME"))'),
            ('demand(!result.containsKey(key), "JSON_DUPLICATE_KEY")', ""),
            ('depth <= 32 && ++values <= 32_768', 'depth <= 128 && ++values <= 65_536'),
            ('"schema", "scope", "requestSha256", "request",', '"schema", "scope", "request",'),
            ('directory.parent.parent, directory.parent, directory', 'directory'),
            ('info[2] == 0x41c0L && info[3] == ownerUid', 'info[2] == 0x41c0L'),
            ('raw.contentEquals(read(directory.resolve("compile-record.json"), 256 * 1024))', 'true'),
            ('record["status"] == "COMPILED"', 'record["status"] != "COMPILED"'),
            ('hash(record["requestSha256"]) == checksum(requestRaw)', 'true'),
            ('github["runAttempt"] == environment("GITHUB_RUN_ATTEMPT")', 'true'),
            ('environment("GITHUB_WORKFLOW_SHA") == request["controller_sha"]', 'true'),
            ('source["tree"] == request["controller_tree"]', 'true'),
            ('invocation == environment("P2PKIT_AUDIT_OWNERSHIP_CHAIN")', 'true'),
            ('headerHome == launcherHome', 'true'),
            ('ended - requestStarted < 120_000_000_000L', 'ended - requestStarted < 180_000_000_000L'),
            ('checksum(cRaw) == cInput["sha256"]', 'true'),
            ('checksum(read(library, 1024 * 1024)) == artifact["sha256"]', 'true'),
            ('code in 0L..123L', 'code in 0L..255L'),
            ('(!required || code == 0L)', 'true'),
            ('true, compiler = true)', 'false, compiler = true)'),
            ('1_048_576L, "COMPILER_OUTPUT_BOUND")', '2_097_152L, "COMPILER_OUTPUT_BOUND")'),
            ('demand(previousEnd <= positive(row["startedMonotonicNs"]), "OBSERVATION_ORDER")', ''),
            ('demand(physical(path).let(::stat).take(4) == expected, "FINAL_PARENT_CHANGED")', ''),
            ('// END JMDNS_POLICY_COMPILE_RECORD_CONSUMER',
             'exec { commandLine("synthetic-forbidden-compiler") }\n// END JMDNS_POLICY_COMPILE_RECORD_CONSUMER'),
        )
        for before, after in wiring_mutations:
            with self.subTest(wiring=before):
                self.assertIn(before, wiring)
                with self.assertRaises(AssertionError):
                    opt_in_handoff_source_guard(launcher, wiring.replace(before, after, 1))
        forwarding = marked_block(wiring, "COMPILE_RECORD_FORWARDING", "            ")
        moved = wiring.replace(forwarding, "", 1).replace("    doFirst {\n", "    doFirst {\n" + forwarding, 1)
        with self.assertRaises(AssertionError):
            opt_in_handoff_source_guard(launcher, moved)
        # Default/other-mode blocks and all historic full-file expected hashes
        # remain unchanged; this is not Gradle/Kotlin preflight execution credit.

    def test_38_policy_java_loader_identity_schema_and_unknown_attribution_are_fail_closed(self):
        source = POLICY_JAVA.read_text(encoding="utf-8")
        java_policy_source_guard(source)
        mutations = (
            ("RESULT_FIELDS = 26", "RESULT_FIELDS = 27"),
            ("LIBRARY_LIMIT = 1_048_576", "LIBRARY_LIMIT = 2_097_152"),
            ("RECORD_LIMIT = 262_144", "RECORD_LIMIT = 524_288"),
            ("OUTER_WATCHDOG_NS = 45_000_000_000L", "OUTER_WATCHDOG_NS = 60_000_000_000L"),
            ("POLICY_DENIED = -65570", "POLICY_DENIED = -65571"),
            ("ATTEMPTED.compareAndSet(false, true)", "true"),
            ("currentInterface.currentIndex() == interfaceIndex", "true"),
            ("long loadMonotonicBefore = System.nanoTime();", "long loadMonotonicBefore = 0;"),
            ("long loadUtcAfter = System.currentTimeMillis();", "long loadUtcAfter = loadUtcBefore;"),
            ("System.load(handoff.library.toString())", "System.loadLibrary(handoff.library.toString())"),
            ("browse0(interfaceIndex, pid, handoff.originalLibrary.uid)", "browse0(interfaceIndex, pid, 0)"),
            ('javaHome.equals(Path.of(System.getProperty("java.home", "")).toRealPath())', "true"),
            ("uid == owner && uid >= 0", "uid >= 0"),
            ("uid <= UINT32_MAX && links == 1", "uid <= UINT32_MAX && links > 0"),
            ("for (int level = 0; level < 3; level++)", "for (int level = 0; level < 1; level++)"),
            ("original == null || before.equals(original)", "true"),
            ("before.equals(after) && (original == null || after.equals(original))", "true"),
            ("Files.newInputStream(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)",
             "Files.newInputStream(path, StandardOpenOption.READ)"),
            ("value.length == RESULT_FIELDS", "value.length >= RESULT_FIELDS"),
            ("value[REAL_UID] == uid && value[EFFECTIVE_UID] == uid", "value[REAL_UID] >= 0"),
            ("value[DEALLOCATE_RETURNED] == value[REF_CREATED]", "value[DEALLOCATE_RETURNED] >= 0"),
            ("value[ELAPSED_NS] <= javaElapsed", "value[ELAPSED_NS] <= OUTER_WATCHDOG_NS"),
            ("value[CALLBACK_POLICY_COUNT] <= value[CALLBACK_COUNT]", "value[CALLBACK_POLICY_COUNT] >= 0"),
            ("value[POLICY_PHASE_MASK] == mask", "true"),
            ("result[CLOCK_ERRNO] == 0", "true"),
            ("priorSendCause=UNKNOWN lifecycleAcceptance=NOT_PERFORMED",
             "priorSendCause=POLICY_DENIED lifecycleAcceptance=PASS"),
            ('emit(phase, "result=UNKNOWN reason=DIAGNOSTIC_FAILURE");', "failure.printStackTrace();"),
        )
        for before, after in mutations:
            with self.subTest(source=before):
                self.assertIn(before, source)
                with self.assertRaises(AssertionError):
                    java_policy_source_guard(source.replace(before, after, 1))
        moved = source.replace("            System.load(handoff.library.toString());\n", "", 1).replace(
            "            Handoff handoff = handoff();\n",
            "            Handoff handoff = handoff();\n            System.load(handoff.library.toString());\n", 1)
        with self.assertRaises(AssertionError):
            java_policy_source_guard(moved)
        with self.assertRaises(AssertionError):
            java_policy_source_guard(source.replace("    private JmdnsStartupPolicy() {\n",
                '    static { System.load("/synthetic-not-a-library"); }\n\n'
                "    private JmdnsStartupPolicy() {\n", 1))
        # No Java/C compilation or dynamic-loader mapping is established by
        # these actual-source/mutation controls, even if every assertion passes.

    def test_39_policy_native_source_has_bounded_single_operation_and_truthful_cleanup(self):
        source = POLICY_C.read_text(encoding="utf-8")
        native_policy_source_guard(source)
        mutations = (
            ("RESULT_FIELDS = 26", "RESULT_FIELDS = 27"),
            ("PROCESS_RETURNED = 10", "PROCESS_RETURNED = 11"),
            ("CALLBACK_LIMIT = 32", "CALLBACK_LIMIT = 33"),
            ("EINTR_RETRY_LIMIT = 4", "EINTR_RETRY_LIMIT = 5"),
            ("INT64_C(1000000000)", "INT64_C(2000000000)"),
            ("kDNSServiceErr_PolicyDenied == -65570", "kDNSServiceErr_PolicyDenied == -65571"),
            ("values[EFFECTIVE_UID] != expected_uid", "values[EFFECTIVE_UID] < 0"),
            ("values[PID] != expected_pid", "values[PID] <= 0"),
            ('"_p2pkit-audit._tcp", "local."', '"_services._dns-sd._udp", "local."'),
            ("if (error != kDNSServiceErr_NoError) {", "if (error != kDNSServiceErr_NoError) {\n        (void) interface_index;"),
            ("if (reference == NULL)", "if (0)"),
            ("if (values[EINTR_RETRIES] == EINTR_RETRY_LIMIT)", "if (values[EINTR_RETRIES] > EINTR_RETRY_LIMIT)"),
            ("values[EINTR_RETRIES]++;", "values[EINTR_RETRIES]++; deadline = now + NORMAL_BUDGET_NS;"),
            ("state.processing = 1;", "state.processing = 0;"),
            ("if (values[REF_CREATED])", "if (reference != NULL)"),
            ("values[DEALLOCATE_RETURNED] = 1;", "values[DEALLOCATE_RETURNED] = 0;"),
            ("return returned;", "close((int) values[SOCKET_FD]); return returned;"),
            ("return returned;", 'printf("synthetic-data"); return returned;'),
        )
        for before, after in mutations:
            with self.subTest(source=before):
                self.assertIn(before, source)
                with self.assertRaises(AssertionError):
                    native_policy_source_guard(source.replace(before, after, 1))
        # These are source-order controls, not proof that a synchronous native
        # call or cleanup returns before the unchanged 45s JVM watchdog.
        reordered = source.replace("        values[DEALLOCATE_ATTEMPTED] = 1;\n", "", 1).replace(
            "        values[DEALLOCATE_RETURNED] = 1;\n",
            "        values[DEALLOCATE_RETURNED] = 1;\n        values[DEALLOCATE_ATTEMPTED] = 1;\n", 1)
        with self.assertRaises(AssertionError):
            native_policy_source_guard(reordered)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DiagnosticControls)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    if result.wasSuccessful():
        print(f"RESULT: PASS — {result.testsRun} focused synthetic/source controls; "
              "no Java, native-policy, provider, custody or hosted qualification")
    raise SystemExit(0 if result.wasSuccessful() else 1)
