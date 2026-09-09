#!/usr/bin/env python3
"""Real current-host executor fixtures; never product, device or interoperability evidence.

Fake wrappers are explicitly fixture programs, not Gradle successes. Test fixture
contexts explicitly preserve every parent ownership domain. The current host's real ownership controls
are mandatory; another host's tests are not selected or counted as native evidence.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import audit_processes as processes

SPEC = importlib.util.spec_from_file_location("audit_runner", SCRIPTS / "run-audit-command.py")
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
EXECUTOR = SCRIPTS / "run-audit-command.py"
PYTHON = str(Path(sys.executable).resolve())
EVIDENCE_ROOT = None
CASE_EVIDENCE = None


def property_spellings(expression):
    for short, long in (("D", "system-prop"), ("P", "project-prop")):
        yield [f"-{short}{expression}"]
        for option in (f"-{short}", f"--{short}", f"-{long}", f"--{long}"):
            yield [option, expression]
            if option != f"-{long}":
                yield [option + "=" + expression]


def archive_fixture_file(source, destination, budget, *, count_entry=True):
    runner.reject_symlinks(source)
    before = source.lstat()
    runner.require(stat.S_ISREG(before.st_mode), "Required fixture evidence is not a regular file")
    if count_entry:
        budget["entries"] += 1
    runner.require(budget["entries"] <= runner.MAX_ARCHIVE_FILES, "Fixture evidence entry count exceeds its bound")
    runner.reject_symlinks(destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    size = 0
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(source, flags), "rb") as input_stream, runner.new_file(destination) as output_stream:
        opened = os.fstat(input_stream.fileno())
        runner.require(stat.S_ISREG(opened.st_mode) and os.path.samestat(before, opened),
                       "Fixture evidence was replaced before copying")
        for block in iter(lambda: input_stream.read(65536), b""):
            size += len(block)
            budget["bytes"] += len(block)
            runner.require(budget["bytes"] <= runner.MAX_ARCHIVE_BYTES, "Fixture evidence bytes exceed their bound")
            output_stream.write(block)
        output_stream.flush()
        os.fsync(output_stream.fileno())
        after = os.fstat(input_stream.fileno())
        runner.require((opened.st_size, opened.st_mtime_ns) == (after.st_size, after.st_mtime_ns) and
                       size == opened.st_size, "Fixture evidence changed during copying; retain its original directory")
    return {"source": str(source), "retained": str(destination), "bytes": size,
            "sha256": runner.file_digest(destination)}


def archive_fixture_tree(source, destination, errors, budget=None):
    """Best effort means retain other safe files after a fault, never follow links.

    This copies observed fixture evidence, not synthetic successful receipts. Any
    failure keeps the generated source fixture for inspection and fails the test.
    """
    if budget is None:
        budget = {"entries": 0, "bytes": 0}
    records = []
    pending = [(source, destination, 0)]
    budget["entries"] += 1
    while pending:
        parent, target, depth = pending.pop()
        try:
            runner.require(depth <= 256, "Fixture evidence depth exceeds its bound")
            runner.require(runner.physical_directory_present(parent), "Required fixture evidence directory is missing")
            runner.require(not runner.within(destination, source), "Fixture archive must be outside its source tree")
            runner.require(budget["entries"] <= runner.MAX_ARCHIVE_FILES,
                           "Fixture evidence entry count exceeds its bound")
            runner.reject_symlinks(target)
            target.mkdir(parents=True, exist_ok=True, mode=0o700)
            with os.scandir(parent) as entries:
                for entry in entries:
                    try:
                        budget["entries"] += 1
                        runner.require(budget["entries"] <= runner.MAX_ARCHIVE_FILES,
                                       "Fixture evidence entry count exceeds its bound")
                        info = entry.stat(follow_symlinks=False)
                        runner.require(not stat.S_ISLNK(info.st_mode) and
                                       not (getattr(info, "st_file_attributes", 0) & 0x400),
                                       "Linked fixture evidence is not admissible")
                        path, retained = Path(entry.path), target / entry.name
                        if stat.S_ISDIR(info.st_mode):
                            pending.append((path, retained, depth + 1))
                        else:
                            records.append(archive_fixture_file(path, retained, budget, count_entry=False))
                    except Exception as error:
                        errors.append(f"Fixture evidence entry {entry.path}: {type(error).__name__}: {error}")
                        if budget["entries"] > runner.MAX_ARCHIVE_FILES or \
                                budget["bytes"] > runner.MAX_ARCHIVE_BYTES:
                            return records
        except Exception as error:
            errors.append(f"Fixture evidence directory {parent}: {type(error).__name__}: {error}")
    return records

FIXTURE = r'''import json, os, pathlib, signal, subprocess, sys, time
state = pathlib.Path(os.environ["P2PKIT_AUDIT_STATE_DIR"])
arguments = sys.argv[1:]
record = {"argv": arguments, "pid": os.getpid(), "home": os.environ.get("GRADLE_USER_HOME"),
          "job": os.environ.get("P2PKIT_AUDIT_JOB_ID"), "chain": os.environ.get("P2PKIT_AUDIT_OWNERSHIP_CHAIN")}
with (state / "fixture-calls.jsonl").open("a", encoding="utf-8") as output:
    output.write(json.dumps(record) + "\n")
if "--stop" in arguments:
    sys.stdout.buffer.write(b"STOP-ONLY-STDOUT\n")
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(b"STOP-ONLY-STDERR\n")
    sys.stderr.buffer.flush()
    if os.environ.get("FIXTURE_STOP_HANG") == "yes":
        while True: time.sleep(.05)
    raise SystemExit(int(os.environ.get("FIXTURE_STOP_EXIT", "0")))
mode = arguments[0]
if mode == "argv":
    print(json.dumps(arguments, ensure_ascii=True))
    raise SystemExit(0)
if mode == "mutation":
    pathlib.Path("source.txt").write_text("mutated source\n", encoding="utf-8")
if mode in ("report", "project-report"):
    project = pathlib.Path(arguments[arguments.index("-p") + 1]) if mode == "project-report" else pathlib.Path(".")
    output = project / "build/test-results/fixture/result.xml"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('<testsuite tests="1" failures="0"/>\n', encoding="utf-8")
if mode == "escape":
    code = """import json, os, pathlib, signal, time
if hasattr(signal, 'SIGTERM'): signal.signal(signal.SIGTERM, signal.SIG_IGN)
if hasattr(signal, 'SIGBREAK'): signal.signal(signal.SIGBREAK, signal.SIG_IGN)
pathlib.Path(os.environ['P2PKIT_AUDIT_STATE_DIR'], 'escaped-worker.json').write_text(json.dumps({'pid': os.getpid()}))
while True: time.sleep(.05)
"""
    options = {"creationflags": 0x208} if os.name == "nt" else {"start_new_session": True}
    subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, **options)
    ready = state / "escaped-worker.json"
    end = time.monotonic() + 10
    while not ready.exists():
        if time.monotonic() > end: raise SystemExit(9)
        time.sleep(.02)
if mode in ("hold", "timeout"):
    (state / "product-ready").write_text("ready\n")
    while not (state / "release-product").exists(): time.sleep(.02)
sys.stdout.buffer.write(b"PRODUCT-STDOUT\n")
sys.stdout.buffer.flush()
sys.stderr.buffer.write(b"PRODUCT-STDERR\n")
sys.stderr.buffer.flush()
raise SystemExit(7 if mode == "failure" else 0)
'''


class Capture:
    def __init__(self, child):
        self.child = child
        self.out, self.err = bytearray(), bytearray()
        self.errors = []
        self.threads = []
        self.directory = None
        if CASE_EVIDENCE is not None:
            self.directory = CASE_EVIDENCE / f"controller-{uuid.uuid4().hex}"
            self.directory.mkdir(mode=0o700)
            (self.directory / "start.json").write_text(json.dumps({"pid": child.pid}) + "\n")
        for source, destination, label in ((child.stdout, self.out, "stdout"), (child.stderr, self.err, "stderr")):
            log = (self.directory / f"{label}.log").open("xb", buffering=0) if self.directory else None
            thread = threading.Thread(target=self.copy, args=(source, destination, log), daemon=True)
            thread.start()
            self.threads.append(thread)

    def copy(self, source, destination, log):
        try:
            while True:
                block = source.read(65536)
                if not block:
                    return
                destination.extend(block)
                if log is not None:
                    log.write(block)
        except Exception as error:
            self.errors.append(f"Fixture capture failed: {type(error).__name__}: {error}")
        finally:
            try:
                source.close()
                if log is not None:
                    log.flush()
                    os.fsync(log.fileno())
                    log.close()
            except Exception as error:
                self.errors.append(f"Fixture capture close failed: {type(error).__name__}: {error}")

    def finish(self, scope, timeout=40):
        deadline = time.monotonic() + timeout
        while self.child.poll() is None:
            scope.discover()
            if time.monotonic() >= deadline:
                raise AssertionError("Fixture controller did not complete within its explicit bound")
            time.sleep(.05)
        for thread in self.threads:
            thread.join(timeout=5)
            if thread.is_alive():
                raise AssertionError("Fixture controller retained an open stdout/stderr pipe")
        if self.directory is not None:
            (self.directory / "completion.json").write_text(json.dumps({"pid": self.child.pid,
                "exitCode": self.child.poll(), "stdoutSha256": runner.digest(bytes(self.out)),
                "stderrSha256": runner.digest(bytes(self.err)), "errors": self.errors}) + "\n")
        if self.errors:
            raise AssertionError("; ".join(self.errors))
        return self.child.poll(), bytes(self.out), bytes(self.err)


class PurePolicyTests(unittest.TestCase):
    def test_fixture_markers_are_flushed_raw_bytes_under_both_text_newline_policies(self):
        # Exercise the actual embedded program, not a duplicate marker implementation.
        # Buffered binary streams make a missing explicit flush observable before close.
        cases = ((["success"], 0, 0, b"PRODUCT"), (["failure"], 0, 7, b"PRODUCT"),
                 (["--stop"], 0, 0, b"STOP-ONLY"), (["--stop"], 7, 7, b"STOP-ONLY"))
        for newline in ("\n", "\r\n"):
            for arguments, stop_status, expected_status, marker in cases:
                with self.subTest(newline=repr(newline), arguments=arguments, stop_status=stop_status), \
                        tempfile.TemporaryDirectory(prefix="audit fixture newline ") as temporary:
                    stdout_bytes, stderr_bytes = io.BytesIO(), io.BytesIO()
                    with io.TextIOWrapper(io.BufferedWriter(stdout_bytes), encoding="utf-8", newline=newline) as stdout, \
                            io.TextIOWrapper(io.BufferedWriter(stderr_bytes), encoding="utf-8", newline=newline) as stderr:
                        environment = {"P2PKIT_AUDIT_STATE_DIR": temporary, "FIXTURE_STOP_HANG": "no",
                                       "FIXTURE_STOP_EXIT": str(stop_status)}
                        with mock.patch.dict(os.environ, environment), \
                                mock.patch.object(sys, "argv", ["fixture.py", *arguments]), \
                                mock.patch.object(sys, "stdout", stdout), mock.patch.object(sys, "stderr", stderr):
                            with self.assertRaises(SystemExit) as stopped:
                                exec(compile(FIXTURE, "actual-audit-fixture", "exec"), {})
                        self.assertEqual(stopped.exception.code, expected_status)
                        for stream, captured in ((b"STDOUT", stdout_bytes), (b"STDERR", stderr_bytes)):
                            with self.subTest(stream=stream):
                                self.assertEqual(captured.getvalue(), marker + b"-" + stream + b"\n")
                    calls = (Path(temporary) / "fixture-calls.jsonl").read_text(encoding="utf-8").splitlines()
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(json.loads(calls[0])["argv"], arguments)

    def test_resource_flags_and_original_arguments_are_preserved(self):
        original = ["publishToMavenLocal", "-Dmaven.repo.local=/tmp/fixture repository", "--configure-on-demand"]
        snapshot = list(original)
        result = runner.gradle_arguments(original)
        self.assertEqual(original, snapshot)
        self.assertEqual(result[:len(original)], original)
        self.assertNotIn("--no-configure-on-demand", result)
        self.assertIn("--no-parallel", result)
        self.assertIn("--max-workers=2", result)
        self.assertIn("strict", result)

    def test_real_init_script_negative_control_is_not_removed(self):
        original = ["indirectLockRefresh", "--dry-run", "--init-script", "/tmp/owned-policy.init.gradle.kts"]
        self.assertEqual(runner.gradle_arguments(original)[:len(original)], original)

    def test_security_resource_and_home_overrides_are_rejected(self):
        for arguments in (["check", "--parallel"], ["check", "--max-workers", "3"],
                          ["check", "--dependency-verification=off"], ["check", "--build-cache"],
                          ["check", "-g/tmp/shared"], ["check", "--gradle-user-home=/tmp/shared"],
                          ["check", "-Foff"], ["check", "-F", "lenient"],
                          ["check", "-Dorg.gradle.jvmargs=-Xmx8g"],
                          ["check", "-Pkotlin.compiler.execution.strategy=daemon"],
                          ["check", "-Dorg.gradle.java.home=/unowned"], ["check", "--write-verification-metadata=sha256"]):
            with self.subTest(arguments=arguments), self.assertRaises(runner.AuditError):
                runner.gradle_arguments(arguments)

    def test_every_property_alias_preserves_accepted_raw_tokens(self):
        expressions = ["maven.repo.local=/tmp/fixture repository", "fixture.value=first=second",
                       "fixture.flag", "fixture.empty=", "org.gradle.parallel=false",
                       "org.gradle.workers.max=2", "org.gradle.daemon=false",
                       "org.gradle.caching=false", "org.gradle.configuration-cache=false",
                       "org.gradle.jvmargs=" + runner.JVM_ARGUMENTS,
                       "kotlin.compiler.execution.strategy=in-process"]
        for expression in expressions:
            for spelling in property_spellings(expression):
                with self.subTest(expression=expression, spelling=spelling):
                    original = ["fixtureTask", *spelling, "--configure-on-demand", "--init-script", "/tmp/control.init"]
                    snapshot = list(original)
                    result = runner.gradle_arguments(original)
                    self.assertEqual(original, snapshot)
                    self.assertEqual(result, [*snapshot, *runner.AUDIT_FLAGS])

    def test_every_property_alias_rejects_home_resource_toolchain_and_security_override(self):
        expressions = ["gradle.user.home=/foreign/home", "gradle.user.home", "gradle.user.home=",
                       "java.home=/foreign/jdk",
                       "org.gradle.java.home=/foreign/jdk", "org.gradle.jvmargs=-Xmx8g",
                       "org.gradle.java.installations.paths=/foreign/jdk",
                       "org.gradle.java.installations.auto-download=true",
                       "org.gradle.parallel=true", "org.gradle.workers.max=3", "org.gradle.daemon=true",
                       "org.gradle.caching=true", "org.gradle.configuration-cache=true",
                       "org.gradle.dependency.verification=off", "org.gradle.project.fixture=override",
                       "kotlin.compiler.execution.strategy=daemon", "kotlin.daemon.jvmargs=-Xmx8g"]
        for expression in expressions:
            for spelling in property_spellings(expression):
                with self.subTest(expression=expression, spelling=spelling), self.assertRaises(runner.AuditError):
                    runner.gradle_arguments(["check", *spelling])

    def test_conflicting_option_aliases_and_inner_terminator_are_not_hidden(self):
        for name, value in (("g", "/foreign/home"), ("gradle-user-home", "/foreign/home"),
                            ("F", "off"), ("M", "sha256"), ("max-workers", "3"),
                            ("dependency-verification", "off"), ("console", "rich")):
            for prefix in ("-", "--"):
                for spelling in ([prefix + name, value], [prefix + name + "=" + value]):
                    with self.subTest(spelling=spelling), self.assertRaises(runner.AuditError):
                        runner.gradle_arguments(["check", *spelling])
        for arguments in (["check", "--", "--max-workers=3"], ["--", "check"],
                          ["check", "-system-prop=maven.repo.local=/tmp/fixture"],
                          ["check", "-project-prop=fixture.option=value"],
                          ["check", "-qDgradle.user.home=/foreign/home"], ["check", "-qD", "gradle.user.home=/foreign/home"],
                          ["check", "-imPorg.gradle.parallel=true"], ["check", "-qt"]):
            with self.subTest(arguments=arguments), self.assertRaises(runner.AuditError):
                runner.gradle_arguments(arguments)

    def test_missing_or_empty_property_keys_are_rejected_without_guessing(self):
        for option in ("-D", "-P", "--D", "--P", "--system-prop", "--project-prop", "-system-prop", "-project-prop"):
            for suffix in ([], [""], ["=value"], ["--parallel"]):
                arguments = ["check", option, *suffix]
                with self.subTest(arguments=arguments), self.assertRaises(runner.AuditError):
                    runner.gradle_arguments(arguments)
            with self.subTest(option=option), self.assertRaises(runner.AuditError):
                runner.gradle_arguments(["check", option + "="])

    def test_report_root_and_descendant_scan_errors_are_not_empty_success(self):
        # Deliberate function-level faults, not claims of native permissions or
        # a Gradle execution. PermissionError is injected even when running as root.
        with tempfile.TemporaryDirectory(prefix="audit report scan fixture ") as temporary:
            root = Path(temporary).resolve() / "source"
            state = Path(temporary).resolve() / "state"
            module = root / "library"
            reports = root / "build/reports"
            nested = reports / "nested"
            for directory in (state, module, nested):
                directory.mkdir(parents=True)
            (nested / "report.json").write_text('{"fixtureOnly":true}\n')
            actual_scandir = os.scandir
            for blocked in (module, reports, nested):
                def unavailable(path, *, target=blocked):
                    if Path(path) == target:
                        raise PermissionError("injected required inventory failure")
                    return actual_scandir(path)
                with self.subTest(blocked=blocked), mock.patch.object(runner.os, "scandir", side_effect=unavailable):
                    with self.assertRaisesRegex(PermissionError, "injected required inventory failure"):
                        runner.report_snapshot(root, state, [])

    def test_source_and_evidence_lstat_failures_are_not_treated_as_absence(self):
        with tempfile.TemporaryDirectory(prefix="audit report stat fixture ") as temporary:
            root = Path(temporary).resolve() / "source"
            state = Path(temporary).resolve() / "state"
            (root / "library").mkdir(parents=True)
            (root / "build/reports").mkdir(parents=True)
            state.mkdir()
            actual_lstat = Path.lstat
            for blocked in (root / "library", root / "build/reports"):
                def unavailable(path, *args, target=blocked, **kwargs):
                    if path == target:
                        raise PermissionError("injected required lstat failure")
                    return actual_lstat(path, *args, **kwargs)
                with self.subTest(blocked=blocked), mock.patch.object(Path, "lstat", new=unavailable):
                    with self.assertRaisesRegex(PermissionError, "injected required lstat failure"):
                        runner.report_snapshot(root, state, [])

    def test_report_entry_bound_counts_empty_directories_not_just_files(self):
        with tempfile.TemporaryDirectory(prefix="audit report bound fixture ") as temporary:
            root = Path(temporary).resolve() / "source"
            state = Path(temporary).resolve() / "state"
            for name in ("one", "two", "three", "four"):
                (root / "build/reports" / name).mkdir(parents=True)
            state.mkdir()
            with mock.patch.object(runner, "MAX_ARCHIVE_FILES", 3):
                with self.assertRaisesRegex(runner.AuditError, "entry count"):
                    runner.report_snapshot(root, state, [])

    def test_nested_environment_keeps_parent_and_binds_job_home(self):
        job, outer, inner = (uuid.uuid4().hex for _ in range(3))
        first = processes.ownership_environment({}, job, outer, "/state", "/home")
        second = processes.ownership_environment(first, job, inner, "/state", "/home")
        self.assertEqual(second[processes.CHAIN_ENV], outer + ":" + inner)
        with self.assertRaises(processes.OwnershipError):
            processes.ownership_environment({**first, "GRADLE_USER_HOME": "/different"}, job, inner, "/state", "/home")
        with self.assertRaises(processes.OwnershipError):
            processes.ownership_environment(first, uuid.uuid4().hex, inner, "/state", "/home")

    def test_explicit_fixture_context_crossing_preserves_exact_parent_domain(self):
        parent_job, child_job, outer, inner = (uuid.uuid4().hex for _ in range(4))
        first = processes.ownership_environment({}, parent_job, outer, "/parent-state", "/parent-home")
        child = processes.ownership_environment(first, child_job, inner, "/child-state", "/child-home",
                                                allow_new_context=True)
        domains = processes.ownership_domains(child[processes.CHAIN_ENV], child[processes.DOMAINS_ENV])
        self.assertEqual(domains, [{"id": outer, "job": parent_job, "state": "/parent-state", "home": "/parent-home"},
                                  {"id": inner, "job": child_job, "state": "/child-state", "home": "/child-home"}])
        invalid = {**first, processes.DOMAINS_ENV: "[]"}
        with self.assertRaises(processes.OwnershipError):
            processes.ownership_environment(invalid, child_job, inner, "/child-state", "/child-home",
                                            allow_new_context=True)

    def test_procargs_parser_discards_argv_and_selects_exact_environment(self):
        import struct
        raw = struct.pack("=i", 3) + b"/usr/bin/python\0\0python\0-c\0private payload\0" + \
            b"PRIVATE=not retained\0P2PKIT_AUDIT_JOB_ID=job\0P2PKIT_AUDIT_OWNERSHIP_CHAIN=outer:inner\0\0"
        result = processes.parse_procargs2(raw)
        self.assertEqual(result, {b"P2PKIT_AUDIT_JOB_ID": b"job", b"P2PKIT_AUDIT_OWNERSHIP_CHAIN": b"outer:inner"})
        for malformed in (b"", b"\1\0\0\0no terminator", raw[:16]):
            with self.subTest(malformed=malformed), self.assertRaises(processes.OwnershipError):
                processes.parse_procargs2(malformed)

    def test_restricted_batch_grammar_rejects_expansion_and_control(self):
        for value in ("%PATH%", "bang!", 'quote"', "pipe|", "and&", "lt<", "gt>", "caret^", "paren(", "line\n"):
            with self.subTest(value=value), self.assertRaises(processes.OwnershipError):
                processes.batch_command_line(r"C:\Windows\System32\cmd.exe", [r"C:\root\gradlew.bat", value])
        command = processes.batch_command_line(r"C:\Windows\System32\cmd.exe",
                                               [r"C:\space root\gradlew.bat", "two words", "Ω", "", "tail\\"])
        self.assertIn('/d /s /v:off /c ""', command)
        self.assertIn('""', command)

    def test_structure_layouts_are_explicit_not_native_acceptance(self):
        self.assertEqual(tuple(ctypes.sizeof(kind) for kind in (processes.DarwinBsdInfo, processes.DarwinUniqueInfo,
                                                               processes.DarwinIdentity, processes.AuditToken)),
                         (136, 56, 192, 32))
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual(tuple(ctypes.sizeof(kind) for kind in (processes.SecurityAttributes,
                processes.ProcessInformation, processes.StartupInfo, processes.StartupInfoEx,
                processes.JobBasicLimits, processes.IoCounters, processes.JobExtendedLimits)),
                (24, 24, 104, 112, 64, 48, 144))


class ExecutorFixtureTests(unittest.TestCase):
    def setUp(self):
        global CASE_EVIDENCE
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit audit fixture ")
        # On an unexpected ownership/archive failure leave the private fixture for
        # inspection; only explicit successful cleanup may delete its generated data.
        self.temporary._finalizer.detach()
        self.addCleanup(self._cleanup_fixture)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "source Ω with spaces"
        self.root.mkdir()
        self.state = self.base / "state"
        self.sentinel_scopes = []
        self.fixture_retention_errors = []
        self.fixture_archivists = []
        if EVIDENCE_ROOT is not None:
            case = EVIDENCE_ROOT / self._testMethodName
            case.mkdir(mode=0o700)
            CASE_EVIDENCE = case
            (case / "case.json").write_text(json.dumps({"source": str(self.root), "state": str(self.state)}) + "\n")
        (self.root / ".gitignore").write_text("build/\n!**/src/**/build/\nsamples/iosApp/p2pkit-sample.xcodeproj/\n",
                                               encoding="utf-8")
        (self.root / "source.txt").write_text("original source\n", encoding="utf-8")
        (self.root / "fixture.py").write_text(FIXTURE, encoding="utf-8")
        (self.root / "gradlew").write_text('#!/bin/sh\nexec "' + PYTHON + '" "$(dirname "$0")/fixture.py" "$@"\n',
                                           encoding="utf-8")
        (self.root / "gradlew").chmod(0o755)
        (self.root / "gradlew.bat").write_text('@echo off\r\n"' + PYTHON + '" "%~dp0fixture.py" %*\r\nexit /b %errorlevel%\r\n',
                                               encoding="utf-8")
        source_build = self.root / "buildSrc/src/main/java/dev/p2pkit/build"
        source_build.mkdir(parents=True)
        (source_build / "Source.java").write_text("// source, never disposable\n", encoding="utf-8")
        for command in (["init", "-q"], ["config", "user.email", "fixture@example.invalid"],
                        ["config", "user.name", "Audit Fixture"], ["config", "core.autocrlf", "false"],
                        ["add", "."], ["commit", "-qm", "Fixture baseline"]):
            self.git(*command)
        self.commit = self.git("rev-parse", "HEAD").decode().strip()
        self.env = dict(os.environ)
        # Resource variables are not consumed by the fake wrapper; parent ownership
        # markers/domains are never stripped when switching this explicit fixture.
        for key in ("P2PKIT_GRADLE_EXECUTOR", "JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS",
                    "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
            self.env.pop(key, None)
        result = subprocess.run([PYTHON, str(EXECUTOR), "init", "--root", str(self.root), "--state", str(self.state),
                                 "--expected-commit", self.commit, "--host", processes.host_role()], env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
        if CASE_EVIDENCE is not None:
            (CASE_EVIDENCE / "init.stdout.log").write_bytes(result.stdout)
            (CASE_EVIDENCE / "init.stderr.log").write_bytes(result.stderr)
            (CASE_EVIDENCE / "init.json").write_text(json.dumps({"expectedCommit": self.commit,
                "exitCode": result.returncode, "source": str(self.root), "state": str(self.state)}) + "\n")
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.context = json.loads((self.state / "context.json").read_text())
        self.guard_id = uuid.uuid4().hex
        self.scope = processes.make_scope(self.context["id"], self.guard_id, str(self.state), self.context["gradleHome"])
        self.env = processes.ownership_environment(self.env, self.context["id"], self.guard_id,
                                                  str(self.state), self.context["gradleHome"], allow_new_context=True)
        self.wrapper = self.root / ("gradlew.bat" if os.name == "nt" else "gradlew")

    def _cleanup_fixture(self):
        errors = list(getattr(self, "fixture_retention_errors", []))
        fatal = []
        record = {"schema": 1, "kind": "executor-fixture-cleanup", "id": uuid.uuid4().hex,
                  "startedUtc": runner.utc(), "fixtureBase": str(getattr(self, "base", "")),
                  "state": str(getattr(self, "state", "")), "guardSurvivors": None, "sentinels": [],
                  "errors": errors, "archive": [], "dependentArchives": [],
                  "fixtureDataRemoved": False, "cleanupComplete": False}

        def attempt(label, action):
            try:
                return action()
            except BaseException as error:
                errors.append(f"{label}: {type(error).__name__}: {error}")
                if not isinstance(error, Exception):
                    fatal.append(error)
                return None

        if hasattr(self, "scope"):
            record["guardSurvivors"] = attempt("Fixture guard drain", lambda: self.scope.drain(grace=.5, kill_wait=5))
            if record["guardSurvivors"] is None:
                errors.append("Fixture guard worker retirement is unproven; retain the generated fixture")
            if record["guardSurvivors"]:
                errors.append(f"Fixture-owned survivors: {record['guardSurvivors']}")
            discovery = attempt("Fixture guard discovery status", lambda: sorted(self.scope.discovery_errors))
            if discovery:
                errors.append(f"Fixture ownership uncertainty: {discovery}")
            attempt("Fixture guard close", self.scope.close)
        else:
            errors.append("Fixture ownership guard was not established; retain the unadmitted generated fixture")
        for number, (sentinel_scope, capture) in enumerate(getattr(self, "sentinel_scopes", [])):
            survivors = attempt(f"Fixture sentinel {number} drain", lambda: sentinel_scope.drain(grace=.2, kill_wait=5))
            record["sentinels"].append({"index": number, "survivors": survivors})
            if survivors is None:
                errors.append(f"Separately-owned sentinel {number} retirement is unproven")
            if survivors:
                errors.append(f"Separately-owned sentinel {number} survived teardown")
            attempt(f"Fixture sentinel {number} capture", lambda: capture.finish(sentinel_scope, timeout=5))
            attempt(f"Fixture sentinel {number} close", sentinel_scope.close)
        for number, archivist in enumerate(getattr(self, "fixture_archivists", [])):
            retained = attempt(f"Dependent fixture evidence {number}", archivist)
            if retained is not None:
                record["dependentArchives"].append(retained)

        # Teardown is not allowed to short-circuit evidence retention. Give each
        # attempt a fresh directory: an injected/real failure and later recovery
        # must not overwrite one another's records or authentic invocation logs.
        destination = None
        if EVIDENCE_ROOT is not None:
            candidate = EVIDENCE_ROOT / self._testMethodName / f"teardown-{record['id']}"
            def create_destination():
                runner.reject_symlinks(candidate)
                candidate.mkdir(parents=True, mode=0o700)
                return candidate
            destination = attempt("Fixture archive directory creation", create_destination)
        else:
            errors.append("Fixture evidence root is unavailable; preserve all generated fixture data")
        if destination is not None:
            record["archiveDirectory"] = str(destination)
            budget = {"entries": 0, "bytes": 0}
            if hasattr(self, "state"):
                evidence = self.state / "evidence"
                def retain_invocations():
                    exists = runner.existing_lstat(evidence) is not None
                    runner.require(exists or not hasattr(self, "context"), "Initialized fixture evidence root is missing")
                    if exists:
                        record["archive"].extend(archive_fixture_tree(evidence, destination / "invocations", errors, budget))
                attempt("Fixture invocation evidence retention", retain_invocations)
                for name in ("context.json", "fixture-calls.jsonl"):
                    def retain_file(name=name):
                        source = self.state / name
                        exists = runner.existing_lstat(source) is not None
                        runner.require(exists or name != "context.json" or not hasattr(self, "context"),
                                       "Initialized fixture context is missing")
                        if exists:
                            record["archive"].append(archive_fixture_file(source, destination / name, budget))
                    attempt(f"Fixture {name} retention", retain_file)
            if hasattr(self, "scope"):
                description = attempt("Fixture guard description", self.scope.description)
                if description is not None:
                    attempt("Fixture guard evidence write", lambda: runner.write_new_json(destination / "guard.json", description))
            attempt("Fixture pre-disposal evidence write",
                    lambda: runner.write_new_json(destination / "cleanup-before-disposal.json", record))
        if hasattr(self, "temporary") and not errors:
            def dispose():
                self.temporary.cleanup()
                runner.require(runner.existing_lstat(self.base) is None, "Generated fixture directory still exists")
                record["fixtureDataRemoved"] = True
            attempt("Generated fixture disposal", dispose)
        record["endedUtc"] = runner.utc()
        record["cleanupComplete"] = not errors and record["fixtureDataRemoved"]
        if destination is not None:
            before_final_write = len(errors)
            attempt("Fixture final cleanup evidence write", lambda: runner.write_new_json(destination / "cleanup.json", record))
            if len(errors) != before_final_write:
                record["cleanupComplete"] = False
        if errors:
            record["cleanupComplete"] = False
            if hasattr(self, "base") and not record["fixtureDataRemoved"]:
                # Also preserve the unresolved path if upload storage is unavailable.
                attempt("Unresolved fixture path/error record", lambda: runner.write_new_json(
                    self.base / f"unresolved-fixture-cleanup-{record['id']}.json", record))
            if destination is not None:
                # A failed final write must not leave a partial/previous complete
                # JSON as the only outcome. The raised test failure is authoritative
                # even if storage also prevents this supplemental failure journal.
                attempt("Fixture cleanup failure journal", lambda: runner.write_new_json(
                    destination / "cleanup-failure.json", record))
        if fatal:
            raise fatal[0]
        if errors:
            self.fail("; ".join(errors))

    def git(self, *arguments):
        result = subprocess.run(["git", "-C", str(self.root), *arguments], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=20, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return result.stdout

    def start(self, arguments, *, kind="gradle", env=None, timeout=20, stop_timeout=5, receipt=None, invocation=None):
        receipt = receipt or self.state / f"optional-{uuid.uuid4().hex}.json"
        command = [PYTHON, str(EXECUTOR), "--cwd", str(self.root), "--wrapper", str(self.wrapper),
                   "--purpose", "executor-fixture", "--kind", kind, "--timeout", str(timeout),
                   "--stop-timeout", str(stop_timeout), "--receipt", str(receipt), "--", *arguments]
        if invocation:
            command[2:2] = ["--id", invocation]
        child = self.scope.spawn(command, str(self.root), self.env if env is None else env)
        return Capture(child), receipt

    def run_leaf(self, arguments, **options):
        capture, path = self.start(arguments, **options)
        code, out, err = capture.finish(self.scope)
        document = json.loads(path.read_text()) if path.exists() and path.stat().st_size else None
        return code, out, err, document

    def calls(self):
        path = self.state / "fixture-calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def ready(self, path):
        deadline = time.monotonic() + 15
        while not path.exists():
            self.scope.discover()
            self.assertLess(time.monotonic(), deadline, "Real fixture child did not establish readiness")
            time.sleep(.05)

    def sentinel(self):
        identifier = uuid.uuid4().hex
        # Sibling of this fixture guard, not its descendant: the leaf must not stop
        # it, but the real outer controller's domains remain intact for cancellation.
        environment = processes.ownership_environment(dict(os.environ), self.context["id"], identifier,
            str(self.state), self.context["gradleHome"], allow_new_context=True)
        scope = processes.make_scope(self.context["id"], identifier, str(self.state), self.context["gradleHome"])
        child = scope.spawn([PYTHON, "-c", "import time; time.sleep(120)"], str(self.root), environment)
        self.sentinel_scopes.append((scope, Capture(child)))
        return child

    def test_success_has_unchanged_stdout_stderr_and_same_home_stop(self):
        code, out, err, receipt = self.run_leaf(["success"])
        self.assertEqual((code, out, err), (0, b"PRODUCT-STDOUT\n", b"PRODUCT-STDERR\n"))
        self.assertEqual(receipt["requestedArgv"], ["success"])
        self.assertEqual([receipt[key] for key in ("productExitCode", "stopExitCode", "finalExitCode")], [0, 0, 0])
        self.assertTrue(receipt["sourceUnchanged"])
        self.assertEqual(receipt["errors"], [])
        self.assertEqual(receipt["ownedSurvivors"], [])
        launches = receipt["ownership"]["launches"]
        self.assertEqual(len(launches), 2)
        self.assertEqual(receipt["productLaunchIndex"], 0)
        self.assertEqual(receipt["stopLaunchIndex"], 1)
        self.assertEqual(launches[0]["requestedArgv"], receipt["executedArgv"])
        self.assertEqual(launches[1]["requestedArgv"], receipt["stopArgv"])
        self.assertEqual(launches[0]["pid"], receipt["productPid"])
        self.assertTrue(all(item["created"] and item["cwd"] == str(self.root) for item in launches))
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        self.assertIn("--stop", calls[1]["argv"])
        self.assertEqual({call["home"] for call in calls}, {self.context["gradleHome"]})
        self.assertTrue(all(self.guard_id in call["chain"].split(":") for call in calls))
        directory = Path(receipt["evidenceDirectory"])
        self.assertEqual((directory / "stop.stdout.log").read_bytes(), b"STOP-ONLY-STDOUT\n")
        self.assertEqual((directory / "stop.stderr.log").read_bytes(), b"STOP-ONLY-STDERR\n")

    def test_product_failure_is_distinct_from_infrastructure(self):
        code, _, _, receipt = self.run_leaf(["failure"])
        self.assertEqual(code, 7)
        self.assertEqual(receipt["productExitCode"], 7)
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertEqual(receipt["errors"], [])

    def test_stop_nonzero_never_becomes_expected_red_success(self):
        code, _, _, receipt = self.run_leaf(["failure"], env={**self.env, "FIXTURE_STOP_EXIT": "9"})
        self.assertEqual(code, 125)
        self.assertEqual(receipt["productExitCode"], 7)
        self.assertEqual(receipt["stopExitCode"], 9)
        self.assertTrue(receipt["errors"])

    def test_stop_timeout_is_infrastructure_and_drains_workers(self):
        code, _, _, receipt = self.run_leaf(["success"], env={**self.env, "FIXTURE_STOP_HANG": "yes"}, stop_timeout=.2)
        self.assertEqual(code, 125)
        self.assertEqual(receipt["ownedSurvivors"], [])
        self.assertTrue(any("stop timed out" in error for error in receipt["errors"]))

    def test_product_timeout_attempts_stop_and_is_infrastructure(self):
        code, _, _, receipt = self.run_leaf(["timeout"], timeout=.2)
        self.assertEqual(code, 125)
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertTrue(any("timed out" in error for error in receipt["errors"]))
        self.assertEqual(receipt["ownedSurvivors"], [])

    def test_source_mutation_is_retained_not_reset(self):
        code, _, _, receipt = self.run_leaf(["mutation"])
        self.assertEqual(code, 125)
        self.assertFalse(receipt["sourceUnchanged"])
        self.assertEqual((self.root / "source.txt").read_text(), "mutated source\n")
        self.assertEqual(receipt["stopExitCode"], 0)

    def test_exact_raw_argv_handles_spaces_unicode_empty_and_maven_path(self):
        arguments = ["argv", "two words", "Ω", "", "tail\\", "-Dmaven.repo.local=" + str(self.state / "isolated repository")]
        code, out, _, receipt = self.run_leaf(arguments)
        self.assertEqual(code, 0)
        self.assertEqual(receipt["requestedArgv"], arguments)
        self.assertEqual(json.loads(out)[:len(arguments)], arguments)

    def test_existing_optional_receipt_is_not_overwritten(self):
        path = self.state / "existing.json"
        path.write_text("keep these original bytes\n")
        capture, _ = self.start(["success"], receipt=path)
        code, _, _ = capture.finish(self.scope)
        self.assertEqual(code, 125)
        self.assertEqual(path.read_text(), "keep these original bytes\n")
        self.assertEqual(self.calls(), [])

    def test_missing_optional_parent_prevents_product_execution(self):
        capture, _ = self.start(["success"], receipt=self.state / "missing-parent" / "receipt.json")
        code, _, _ = capture.finish(self.scope)
        self.assertEqual(code, 125)
        self.assertEqual(self.calls(), [])

    def test_wrong_home_prevents_product_or_unrelated_stop(self):
        path = self.state / "wrong-home.json"
        arguments = [str(EXECUTOR), "--cwd", str(self.root), "--wrapper", str(self.wrapper), "--purpose", "wrong-home",
                     "--receipt", str(path), "--", "success"]
        # Mutate the input inside our already-owned controller. Do not forge a
        # contradictory OS ownership domain just to construct an admission control.
        bootstrap = ("import os,runpy,sys; sys.dont_write_bytecode=True; "
                     "sys.path.insert(0,sys.argv[1]); os.environ['GRADLE_USER_HOME']=sys.argv[2]; "
                     "sys.argv=sys.argv[3:]; runpy.run_path(sys.argv[0],run_name='__main__')")
        capture = Capture(self.scope.spawn([PYTHON, "-c", bootstrap, str(SCRIPTS), str(self.base / "shared"), *arguments],
                                           str(self.root), self.env))
        code, _, _ = capture.finish(self.scope)
        receipt = json.loads(path.read_text())
        self.assertEqual(code, 125)
        self.assertIsNone(receipt["productExitCode"])
        self.assertIsNone(receipt["stopExitCode"])
        self.assertEqual(self.calls(), [])

    def test_property_alias_admission_refusal_never_launches_product_or_stop(self):
        foreign = self.state / "must-not-create-foreign-home"
        for spelling in property_spellings("gradle.user.home=" + str(foreign)):
            with self.subTest(spelling=spelling):
                requested = ["success", *spelling]
                code, _, _, receipt = self.run_leaf(requested)
                self.assertEqual(code, 125)
                self.assertEqual(receipt["requestedArgv"], requested)
                self.assertIsNone(receipt["productExitCode"])
                self.assertIsNone(receipt["stopExitCode"])
                self.assertEqual(self.calls(), [])
                self.assertFalse(foreign.exists())

    def test_cleanup_failures_still_archive_authentic_receipts_and_preserve_unresolved_fixture(self):
        code, _, _, receipt = self.run_leaf(["success"])
        self.assertEqual(code, 0)
        sentinel = self.sentinel()
        sentinel_scope, capture = self.sentinel_scopes[-1]
        case = EVIDENCE_ROOT / self._testMethodName
        previous = set(case.glob("teardown-*"))
        with mock.patch.object(self.scope, "drain", side_effect=PermissionError("injected guard drain error")), \
                mock.patch.object(self.scope, "close", side_effect=OSError("injected guard close error")), \
                mock.patch.object(sentinel_scope, "drain", side_effect=PermissionError("injected sentinel drain error")), \
                mock.patch.object(capture, "finish", side_effect=OSError("injected sentinel capture error")), \
                mock.patch.object(sentinel_scope, "close", side_effect=OSError("injected sentinel close error")):
            with self.assertRaisesRegex(AssertionError, "Fixture guard drain"):
                self._cleanup_fixture()
        attempts = set(case.glob("teardown-*")) - previous
        self.assertEqual(len(attempts), 1)
        destination = attempts.pop()
        record = json.loads((destination / "cleanup.json").read_text())
        self.assertFalse(record["cleanupComplete"])
        self.assertFalse(record["fixtureDataRemoved"])
        self.assertIsNone(record["guardSurvivors"])
        self.assertIsNone(record["sentinels"][0]["survivors"])
        for stage in ("guard drain", "guard close", "sentinel 0 drain", "sentinel 0 capture", "sentinel 0 close"):
            self.assertTrue(any(stage in error for error in record["errors"]), stage)
        self.assertTrue(self.base.is_dir())
        self.assertTrue((self.base / f"unresolved-fixture-cleanup-{record['id']}.json").is_file())
        original = Path(receipt["evidenceDirectory"])
        retained = destination / "invocations" / original.name
        for name in ("start.json", "receipt.json", "product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log"):
            self.assertEqual((retained / name).read_bytes(), (original / name).read_bytes(), name)
        self.assertIsNone(sentinel.poll())
        # unittest's already-registered normal cleanup now performs the real
        # identity-scoped drain and a separately recorded recovery attempt.
        # The injected failure and its authentic evidence are never overwritten.

    def test_wrong_source_prevents_product_or_stop(self):
        (self.root / "source.txt").write_text("user changes\n")
        code, _, _, receipt = self.run_leaf(["success"])
        self.assertEqual(code, 125)
        self.assertIsNone(receipt["stopExitCode"])
        self.assertEqual(self.calls(), [])
        self.assertEqual((self.root / "source.txt").read_text(), "user changes\n")

    def test_home_policy_tampering_is_not_silently_rewritten(self):
        path = Path(self.context["gradleHome"]) / "gradle.properties"
        path.write_text(path.read_text() + "org.gradle.parallel=true\n")
        code, _, _, receipt = self.run_leaf(["success"])
        self.assertEqual(code, 125)
        self.assertIsNone(receipt)
        self.assertEqual(self.calls(), [])
        self.assertTrue(path.read_text().endswith("org.gradle.parallel=true\n"))

    def test_overlapping_leaf_is_refused_without_stopping_first(self):
        first, first_receipt = self.start(["hold"])
        self.ready(self.state / "product-ready")
        code, _, _, receipt = self.run_leaf(["success"])
        self.assertEqual(code, 125)
        self.assertIsNone(receipt["stopExitCode"])
        self.assertFalse(any("--stop" in call["argv"] for call in self.calls()))
        self.assertIsNone(first.child.poll())
        (self.state / "release-product").write_text("release\n")
        self.assertEqual(first.finish(self.scope)[0], 0)
        self.assertEqual(json.loads(first_receipt.read_text())["stopExitCode"], 0)

    def test_outer_command_nested_leaf_has_no_lease_deadlock(self):
        inner_receipt = self.state / "nested.json"
        inner = [PYTHON, str(EXECUTOR), "--cwd", str(self.root), "--wrapper", str(self.wrapper),
                 "--purpose", "nested-leaf", "--receipt", str(inner_receipt), "--", "success"]
        code, out, err, receipt = self.run_leaf(inner, kind="command")
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(out, b"PRODUCT-STDOUT\n")
        self.assertEqual(json.loads(inner_receipt.read_text())["finalExitCode"], 0)
        self.assertEqual(receipt["requestedArgv"], inner)
        calls = self.calls()
        self.assertEqual(len([call for call in calls if "--stop" in call["argv"]]), 2)
        chains = [call["chain"].split(":") for call in calls]
        self.assertEqual(len(chains[0]), len(self.env[processes.CHAIN_ENV].split(":")) + 2)
        self.assertEqual(len(chains[-1]), len(self.env[processes.CHAIN_ENV].split(":")) + 1)

    def test_leader_exited_detached_term_resistant_worker_dies_sentinel_survives(self):
        sentinel = self.sentinel()
        code, _, err, receipt = self.run_leaf(["escape"])
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(receipt["ownedSurvivors"], [])
        worker_pid = json.loads((self.state / "escaped-worker.json").read_text())["pid"]
        self.assertIn(worker_pid, {item["pid"] for item in receipt["ownership"]["startedIdentities"]})
        self.assertNotIn(worker_pid, {item["pid"] for item in self.scope.discover()})
        self.assertIsNone(sentinel.poll())

    def test_explicit_foreign_fixture_context_detached_worker_remains_parent_owned(self):
        sentinel = self.sentinel()
        foreign_state = self.state / "foreign-fixture"
        foreign_state.mkdir()
        ready = foreign_state / "worker.json"
        foreign_job, foreign_leaf = uuid.uuid4().hex, uuid.uuid4().hex
        control = r'''import json, os, pathlib, subprocess, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import audit_processes as p
state, job, leaf, ready = sys.argv[2:]
home = str(pathlib.Path(state, 'gradle-home'))
scope = p.make_scope(job, leaf, state, home)
env = p.ownership_environment(dict(os.environ), job, leaf, state, home, allow_new_context=True)
worker = "import json,os,pathlib,signal,sys,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); pathlib.Path(sys.argv[1]).write_text(json.dumps({'pid':os.getpid()})); time.sleep(120)"
producer = "import os,subprocess,sys; options={'creationflags':0x208} if os.name=='nt' else {'start_new_session':True}; subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**options)"
scope.spawn([sys.executable, '-c', producer, worker, ready], os.getcwd(), env)
while True:
    scope.discover()
    time.sleep(.05)
'''
        capture = Capture(self.scope.spawn([PYTHON, "-c", control, str(SCRIPTS), str(foreign_state), foreign_job,
                                             foreign_leaf, str(ready)], str(self.root), self.env))
        self.ready(ready)
        worker_pid = json.loads(ready.read_text())["pid"]
        deadline = time.monotonic() + 5
        while worker_pid not in {row["pid"] for row in self.scope.discover()}:
            self.assertLess(time.monotonic(), deadline, "Parent lost ownership across explicit fixture context")
            time.sleep(.05)
        self.assertEqual(self.scope.drain(grace=.3, kill_wait=5), [])
        capture.finish(self.scope)
        self.assertIsNone(sentinel.poll())
        if EVIDENCE_ROOT is not None:
            (EVIDENCE_ROOT / self._testMethodName / "cross-context-proof.json").write_text(json.dumps({
                "parentJob": self.context["id"], "parentInvocation": self.guard_id, "foreignJob": foreign_job,
                "foreignInvocation": foreign_leaf, "workerPid": worker_pid, "unrelatedSentinelSurvived": True}) + "\n")

    def test_changed_report_is_retained_but_identical_xml_is_not_called_fresh(self):
        first = self.run_leaf(["report"])
        self.assertEqual(first[0], 0)
        rows = first[3]["reports"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["classification"], "changed-since-admission")
        retained = Path(first[3]["evidenceDirectory"]) / rows[0]["retained"]
        self.assertTrue(retained.is_file())
        second = self.run_leaf(["report"])
        self.assertEqual(second[0], 0)
        self.assertEqual(second[3]["reports"][0]["classification"], "preexisting-unchanged")
        self.assertNotIn("retained", second[3]["reports"][0])

    def test_external_owned_project_reports_are_retained_before_caller_cleanup(self):
        fixture = self.state / "work/consumer/consumer"
        fixture.mkdir(parents=True)
        code, _, _, receipt = self.run_leaf(["project-report", "-p", str(fixture)])
        self.assertEqual(code, 0)
        rows = receipt["reports"]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["source"].startswith("external/work/consumer/consumer/build/test-results/"))
        retained = Path(receipt["evidenceDirectory"]) / rows[0]["retained"]
        self.assertEqual(retained.read_bytes(), (fixture / "build/test-results/fixture/result.xml").read_bytes())

    def cleanup_command(self, path):
        capture = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "cleanup", "--state", str(self.state),
                                             "--path", str(path)], str(self.root), self.env))
        return capture.finish(self.scope)

    def test_cleanup_exact_output_only_preserves_source_and_evidence(self):
        code, _, _, receipt = self.run_leaf(["report"])
        self.assertEqual(code, 0)
        self.assertEqual(self.cleanup_command(self.root / "build")[0], 0)
        self.assertFalse((self.root / "build").exists())
        self.assertTrue((Path(receipt["evidenceDirectory"]) / "receipt.json").is_file())
        source = self.root / "buildSrc/src/main/java/dev/p2pkit/build"
        self.assertEqual(self.cleanup_command(source)[0], 125)
        self.assertTrue((source / "Source.java").is_file())

    def test_cleanup_tracked_output_rejects_without_deleting_any_source(self):
        directory = self.root / "build"
        directory.mkdir()
        (directory / "user-source.txt").write_text("preserve\n")
        self.git("add", "-f", "build/user-source.txt")
        self.assertEqual(self.cleanup_command(directory)[0], 125)
        self.assertEqual((directory / "user-source.txt").read_text(), "preserve\n")

    def test_cleanup_only_exact_new_xcode_project_and_preserves_preexisting_project(self):
        project = self.root / "samples/iosApp/p2pkit-sample.xcodeproj"
        project.mkdir(parents=True)
        (project / "project.pbxproj").write_text("generated fixture\n")
        self.assertEqual(self.cleanup_command(project)[0], 0)
        self.assertFalse(project.exists())
        project.mkdir()
        (project / "project.pbxproj").write_text("preexisting project\n")
        second_state = self.base / "second-context"
        initialize = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "init", "--root", str(self.root), "--state",
            str(second_state), "--expected-commit", self.commit, "--host", processes.host_role()], str(self.root), self.env))
        self.assertEqual(initialize.finish(self.scope)[0], 0)
        clean = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "cleanup", "--state", str(second_state), "--path",
                                          str(project)], str(self.root), self.env))
        self.assertEqual(clean.finish(self.scope)[0], 125)
        self.assertEqual((project / "project.pbxproj").read_text(), "preexisting project\n")
        if CASE_EVIDENCE is not None:
            shutil.copy2(second_state / "context.json", CASE_EVIDENCE / "preexisting-project-context.json")

    def cleanup_record(self):
        records = [json.loads(path.read_text()) for path in (self.state / "evidence").glob("cleanup-*.json")
                   if not path.name.endswith("-start.json")]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["errors"], [])
        return records[0]

    def test_cleanup_unlinks_child_symlinks_without_following_external_broken_or_loop_targets(self):
        directory = self.root / "build"
        directory.mkdir()
        outside = self.base / "outside-output"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_bytes(b"outside-output sentinel\x00\xff\n")
        targets = {"file-link": (sentinel, False), "directory-link": (outside, True),
                   "broken-link": (outside / "absent", False), "loop-link": (directory, True)}
        try:
            for name, (target, is_directory) in targets.items():
                (directory / name).symlink_to(target, target_is_directory=is_directory)
        except OSError as error:
            self.fail(f"Native no-follow cleanup fixture requires real symlink capability: {error}")
        expected = {name: runner.digest(os.fsencode(os.readlink(directory / name))) for name in targets}
        code, _, err = self.cleanup_command(directory)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertFalse(directory.exists())
        self.assertTrue(outside.is_dir())
        self.assertEqual(sentinel.read_bytes(), b"outside-output sentinel\x00\xff\n")
        self.assertFalse((outside / "absent").exists())
        self.assertEqual((self.root / "source.txt").read_text(), "original source\n")
        record = self.cleanup_record()
        self.assertEqual(record["removed"], [str(directory)])
        self.assertTrue((self.state / "evidence" / f"cleanup-{record['id']}-start.json").is_file())
        inspection = record["inspections"][0]
        self.assertTrue(inspection["noTargetTraversal"])
        self.assertEqual(inspection["entryCount"], len(targets))
        self.assertEqual({row["path"]: row["targetSha256"] for row in inspection["links"]}, expected)
        self.assertTrue(all(row["kind"] == "symlink" and
                            row["policy"] == "unlink-entry-only; do-not-traverse-target"
                            for row in inspection["links"]))

    def test_cleanup_root_or_ancestor_symlink_is_still_rejected(self):
        outside = self.base / "outside-root"
        outside.mkdir()
        (outside / "nested").mkdir()
        (outside / "sentinel.txt").write_bytes(b"preserve root target\n")
        link = self.root / "build"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.fail(f"Native root/ancestor rejection fixture requires real symlink capability: {error}")
        for path in (link, link / "nested"):
            code, _, err = self.cleanup_command(path)
            self.assertEqual(code, 125)
            self.assertIn(b"Symlink/reparse-point", err)
        self.assertTrue(link.is_symlink())
        self.assertEqual((outside / "sentinel.txt").read_bytes(), b"preserve root target\n")

    def test_wrong_native_host_is_rejected_at_initialization(self):
        wrong = next(host for host in runner.HOSTS if host != processes.host_role())
        capture = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "init", "--root", str(self.root), "--state",
            str(self.base / "wrong-host"), "--expected-commit", self.commit, "--host", wrong], str(self.root), self.env))
        self.assertEqual(capture.finish(self.scope)[0], 125)
        self.assertFalse((self.base / "wrong-host").exists())

    def test_cooperative_cancellation_is_real_and_attempts_same_home_stop(self):
        invocation = uuid.uuid4().hex
        capture, path = self.start(["hold"], invocation=invocation)
        self.ready(self.state / "product-ready")
        cancel = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "request-cancel", "--state", str(self.state),
                                            "--id", invocation], str(self.root), self.env))
        self.assertEqual(cancel.finish(self.scope)[0], 0)
        code, _, _ = capture.finish(self.scope)
        self.assertEqual(code, 125)
        receipt = json.loads(path.read_text())
        self.assertTrue(receipt["cancelRequested"])
        self.assertEqual(receipt["cancelledSignals"], [])
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertEqual(receipt["ownedSurvivors"], [])


class PosixNativeTests(ExecutorFixtureTests):
    def consumer_environment(self):
        temporary = self.state / "work/consumer-temp"
        temporary.mkdir(parents=True, mode=0o700)
        environment = {**self.env, "TMPDIR": str(temporary), "TMP": str(temporary), "TEMP": str(temporary)}
        environment.setdefault("P2PKIT_AUDIT_INVOCATION", "private-native-parent-" + uuid.uuid4().hex)
        environment.setdefault("P2PKIT_AUDIT_FIXTURE_ANCESTOR", "future native fixture ancestor must survive")
        return temporary, environment

    def assert_consumer_ancestors(self, observation, environment, invocation):
        ancestors = processes.ownership_domains(environment[processes.CHAIN_ENV], environment[processes.DOMAINS_ENV])
        ancestors.append({"id": invocation, "job": self.context["id"], "state": str(self.state),
                          "home": self.context["gradleHome"]})
        actual = processes.ownership_domains(observation[processes.CHAIN_ENV] or "",
                                              observation[processes.DOMAINS_ENV] or "")
        self.assertEqual(actual[:len(ancestors)], ancestors)
        self.assertEqual(observation[processes.JOB_ENV], actual[-1]["job"])
        self.assertEqual(observation[processes.STATE_ENV], actual[-1]["state"])
        self.assertEqual(observation["GRADLE_USER_HOME"], actual[-1]["home"])
        for name in ("P2PKIT_AUDIT_INVOCATION", "P2PKIT_AUDIT_FIXTURE_ANCESTOR"):
            self.assertEqual(observation[name], environment[name])

    def consumer_token_signal(self, entry, signum):
        # Use the independently acquired kernel capability, never a PID signal or
        # a process-name sweep. No reacquisition from a possibly reused PID occurs.
        if isinstance(self.scope, processes.LinuxScope):
            signal.pidfd_send_signal(entry["handle"], signum)
        elif isinstance(self.scope, processes.DarwinScope):
            result = self.scope.proc.proc_signal_with_audittoken(ctypes.byref(entry["handle"]), signum)
            if result == errno.ESRCH:
                raise ProcessLookupError(entry["identity"]["pid"])
            if result != 0:
                raise processes.OwnershipError(f"Fixture identity-scoped signal failed: errno {result}")
        else:
            raise processes.OwnershipError("Consumer cancellation requires the actual POSIX native backend")

    def consumer_identity_live(self, entry):
        previous = entry["identity"]
        current = self.scope._identity(previous["pid"])
        same = current is not None and self.scope._key(current) == self.scope._key(previous)
        try:
            self.consumer_token_signal(entry, 0)
        except ProcessLookupError:
            # The process may have exited between our identity read and token
            # probe. Reinspect before calling a still-live same-key identity an
            # expired-token fault (e.g. an unexpected Darwin exec-version change).
            current = self.scope._identity(previous["pid"])
            same = current is not None and self.scope._key(current) == self.scope._key(previous)
            runner.require(not (same and current["live"]),
                           "Recorded consumer token expired while the same process remains live")
            return False
        runner.require(same and current["uid"] == previous["uid"],
                       "Live consumer token cannot be reconciled with its recorded same-UID identity")
        return current["live"]

    def consumer_obligation_record(self, obligation):
        capture = obligation.get("capture")
        return {key: obligation[key] for key in ("id", "invocation", "producerEvidence", "fixtureBase", "pending", "recoveryOf",
                "bindingComplete", "observedAncestry", "verifiedAncestry", "bindingErrors", "retentionReasons")} | {
            "controllerPid": capture.child.pid if capture is not None else None,
            "controller": obligation.get("controller"), "product": obligation.get("product"),
            "ready": obligation.get("ready"), "readySha256": obligation.get("readySha256"),
            "producerPid": obligation.get("producerPid"), "producerSha256": obligation.get("producerSha256"),
            "acquiredIdentities": [{"identity": entry["identity"], "released": entry["released"]}
                                   for entry in obligation["entries"]],
        }

    def consumer_obligation_event(self, obligation, event, **fields):
        path = CASE_EVIDENCE / f"consumer-cancellation-{obligation['id']}-{event}-{uuid.uuid4().hex}.json"
        runner.write_new_json(path, {"schema": 1, "kind": event, "utc": runner.utc(),
                                     "obligation": self.consumer_obligation_record(obligation), **fields})
        return path

    def consumer_retention_error(self, obligation, label, error):
        message = f"Consumer cancellation {obligation['id']} {label}: {type(error).__name__}: {error}"
        obligation["retentionReasons"].append(message)
        self.fixture_retention_errors.append(message)
        return message

    def begin_consumer_cancellation_obligation(self, invocation, evidence, *, recovery_of=None):
        identifier = uuid.uuid4().hex
        pending = f"Consumer cancellation {identifier}: whole-chain retirement remains unproven; preserve fixture data"
        obligation = {"id": identifier, "invocation": invocation, "producerEvidence": str(evidence),
                      "fixtureBase": str(self.base), "pending": True, "bindingComplete": False,
                      "observedAncestry": [], "verifiedAncestry": [], "entries": [], "bindingErrors": [],
                      "retentionReasons": [pending], "retirementProof": None, "recoveryOf": recovery_of}
        # Establish both in-memory retention and registered cleanup BEFORE any
        # producer launch/readiness/identity acquisition can fail. Marker-scope
        # drain alone cannot discharge this obligation for an erasure mutant.
        self.fixture_retention_errors.append(pending)
        self.addCleanup(self.cleanup_consumer_cancellation_fallback, obligation)
        try:
            self.consumer_obligation_event(obligation, "pending-recovery" if recovery_of else "pending-before-start")
        except BaseException as error:
            self.consumer_retention_error(obligation, "pending record", error)
            raise
        return obligation

    def start_consumer_cancellation_producer(self, obligation, command, environment):
        try:
            self.assertTrue(obligation["pending"])
            capture, receipt_path = self.start(command, kind="command", invocation=obligation["invocation"], env=environment)
            obligation["capture"] = capture
            evidence = Path(obligation["producerEvidence"])
            self.ready(evidence / "ready.json")
            return capture, receipt_path, runner.read_json(evidence / "ready.json"), runner.read_json(evidence / "producer-start.json")
        except BaseException as error:
            message = self.consumer_retention_error(obligation, "launch/readiness", error)
            obligation["bindingErrors"].append(message)
            try:
                self.consumer_obligation_event(obligation, "launch-or-readiness-failed")
            except BaseException as record_error:
                self.consumer_retention_error(obligation, "launch/readiness failure record", record_error)
            raise

    def bind_consumer_cancellation_fallback(self, obligation, capture, ready, producer):
        # Readiness is a locator, not signal authority. Keep the independently
        # expected WHOLE chain separate from the possibly partial handle subset.
        try:
            self.assertTrue(obligation["pending"])
            self.assertIs(obligation.get("capture"), capture)
            self.assertFalse(obligation["entries"], "A failed binding needs a separate explicit recovery proof")
            obligation["ready"] = ready
            obligation["producerPid"] = producer["pid"]
            evidence = Path(obligation["producerEvidence"])
            obligation["readySha256"] = runner.file_digest(evidence / "ready.json")
            obligation["producerSha256"] = runner.file_digest(evidence / "producer-start.json")
            controller = self.scope._identity(capture.child.pid)
            self.assertIsNone(capture.child.poll())
            self.assertIsNotNone(controller)
            self.assertTrue(controller["live"])
            self.assertEqual(controller["uid"], os.getuid())
            obligation["controller"] = controller
            product = self.scope._identity(producer["pid"])
            self.assertIsNotNone(product)
            self.assertTrue(product["live"])
            self.assertEqual(product["uid"], os.getuid())
            self.assertEqual(product["parentPid"], capture.child.pid)
            obligation["product"] = product
            identities, seen, pid = obligation["observedAncestry"], set(), ready["workerPid"]
            for _ in range(32):
                identity = self.scope._identity(pid)
                self.assertIsNotNone(identity, "Consumer cancellation ancestry disappeared before binding")
                self.assertTrue(identity["live"])
                self.assertEqual(identity["uid"], os.getuid())
                self.assertNotIn(self.scope._key(identity), seen)
                seen.add(self.scope._key(identity))
                identities.append(identity)
                if pid == producer["pid"]:
                    self.assertEqual(self.scope._key(identity), self.scope._key(product))
                    break
                pid = identity["parentPid"]
            else:
                self.fail("Consumer cancellation ancestry did not reach its actual product within 32 entries")
            self.assertEqual(identities[0]["parentPid"], ready["producerPid"])
            self.assertEqual(identities[0]["group"], ready["workerPid"], "Fixture worker did not detach its process group")
            self.assertEqual(identities[-1]["parentPid"], capture.child.pid)
            for child, parent in zip(identities, identities[1:]):
                self.assertEqual(child["parentPid"], parent["pid"])
                if "parentUniqueId" in child:
                    self.assertEqual(child["parentUniqueId"], parent["uniqueId"])
            obligation["verifiedAncestry"] = list(identities)
            for identity in identities:
                entry = {"identity": identity, "handle": self.scope._acquire(identity), "released": False}
                obligation["entries"].append(entry)
                current = self.scope._identity(identity["pid"])
                self.assertIsNotNone(current)
                self.assertEqual(self.scope._key(current), self.scope._key(identity))
                self.assertEqual(current["parentPid"], identity["parentPid"])
                self.assertEqual(current["uid"], os.getuid())
                self.assertTrue(self.consumer_identity_live(entry))
            self.consumer_obligation_event(obligation, "identity-binding", allChainCapabilitiesAcquired=True,
                signalAuthority=self.scope.name,
                scope="Fixture-specific ancestry proof; not a replacement for inherited native ownership.")
            obligation["bindingComplete"] = True
            return obligation["entries"]
        except BaseException as error:
            message = self.consumer_retention_error(obligation, "binding/acquisition", error)
            obligation["bindingErrors"].append(message)
            try:
                self.consumer_obligation_event(obligation, "binding-failed")
            except BaseException as record_error:
                self.consumer_retention_error(obligation, "binding failure record", record_error)
            raise

    def resolve_consumer_retention(self, obligation, proof_obligation, proof, proof_path):
        # A failure-control recovery may supply a SECOND fully bound capability
        # set. It must identify this exact capture/product/ready/source instance,
        # cover every observed/acquired stable key, and have a durable complete
        # retirement record. A marker-only drain is never recovery authority.
        self.assertTrue(obligation["pending"])
        self.assertTrue(proof_obligation["bindingComplete"])
        self.assertTrue(proof["wholeChainRetired"])
        self.assertEqual(proof["errors"], [])
        if proof_obligation is not obligation:
            self.assertFalse(proof_obligation["pending"])
            self.assertEqual(proof_obligation["recoveryOf"], obligation["id"])
            self.assertEqual(proof_obligation["retirementProof"], (proof, proof_path))
        self.assertIsNotNone(obligation.get("capture"))
        self.assertIs(obligation["capture"], proof_obligation["capture"])
        for key in ("invocation", "producerEvidence", "fixtureBase", "producerPid", "readySha256", "producerSha256"):
            self.assertEqual(obligation[key], proof_obligation[key], key)
        self.assertEqual(obligation["ready"], proof_obligation["ready"])
        expected = [self.scope._key(identity) for identity in proof_obligation["verifiedAncestry"]]
        self.assertTrue(expected)
        self.assertEqual(proof["expectedIdentityKeys"], [list(key) for key in expected])
        self.assertEqual([self.scope._key(identity) for identity in obligation["observedAncestry"]],
                         expected[:len(obligation["observedAncestry"])])
        if obligation["verifiedAncestry"]:
            self.assertEqual([self.scope._key(identity) for identity in obligation["verifiedAncestry"]], expected)
        for entry in obligation["entries"]:
            self.assertIn(self.scope._key(entry["identity"]), expected)
            self.assertTrue(entry["released"], "A recovery must not orphan an acquired capability")
        for key in ("controller", "product"):
            if obligation.get(key) is not None:
                self.assertEqual(self.scope._key(obligation[key]), self.scope._key(proof_obligation[key]))
        self.assertEqual(runner.read_json(proof_path)["cleanup"], proof)
        self.consumer_obligation_event(obligation, "retention-resolved", proofObligation=proof_obligation["id"],
            proofPath=str(proof_path), proofSha256=runner.file_digest(proof_path), wholeChainRetired=True,
            completeIdentityKeys=[list(key) for key in expected], historicalFailuresPreserved=True, retentionPendingAfter=False)
        # Remove only this obligation's exact, UUID-qualified current blockers.
        # Its error list and immutable failure journals remain historical evidence.
        owned = set(obligation["retentionReasons"])
        self.fixture_retention_errors[:] = [reason for reason in self.fixture_retention_errors if reason not in owned]
        obligation["pending"] = False
        obligation["retirementProof"] = (proof, proof_path)

    def cleanup_consumer_cancellation_fallback(self, obligation):
        if not obligation["pending"]:
            return
        entries = [entry for entry in obligation["entries"] if not entry["released"]]
        identities = obligation["verifiedAncestry"]
        expected = [self.scope._key(identity) for identity in identities]
        acquired = [self.scope._key(entry["identity"]) for entry in entries]
        complete = obligation["bindingComplete"] and bool(expected) and acquired == expected
        errors, fatal = [], []
        record = {"schema": 1, "kind": "consumer-identity-fallback-cleanup", "controller": obligation.get("controller"),
                  "verifiedAncestry": identities, "expectedIdentityKeys": [list(key) for key in expected],
                  "wholeChainCovered": complete, "wholeChainRetired": False, "retirementProven": False,
                  "unobservedAncestry": not bool(identities),
                  "unacquiredIdentities": [identity for identity in identities if self.scope._key(identity) not in acquired],
                  "bindingErrors": list(obligation["bindingErrors"]), "backend": self.scope.name, "fallbackUsed": False,
                  "signalledIdentities": [], "remainingAcquiredIdentities": None,
                  "acquiredSubsetRetired": None, "errors": errors,
                  "scope": "Any fallback use FAILS the native ownership test; it never converts the mutant into approval."}

        def attempt(label, action):
            try:
                return action()
            except BaseException as error:
                errors.append(f"{label}: {type(error).__name__}: {error}")
                if not isinstance(error, Exception):
                    fatal.append(error)
                return None

        def remaining():
            live = []
            for entry in entries:
                observation = attempt("Recorded consumer identity observation", lambda: self.consumer_identity_live(entry))
                if observation is None or observation:
                    live.append(entry)
            return live

        live = remaining()
        record["liveBeforeFallback"] = [entry["identity"] for entry in live]
        for entry in live:
            # An uncertain observation never authorizes a signal. A positive
            # recheck is mandatory immediately before using the bound capability.
            if attempt("Consumer pre-signal identity recheck", lambda: self.consumer_identity_live(entry)) is True:
                record["fallbackUsed"] = True
                record["signalledIdentities"].append(entry["identity"])
                def terminate():
                    try:
                        self.consumer_token_signal(entry, processes.SIG_KILL)
                    except ProcessLookupError:
                        pass
                attempt("Recorded consumer identity SIGKILL", terminate)
        deadline = time.monotonic() + 5
        while live and time.monotonic() < deadline:
            time.sleep(.05)
            live = remaining()
        record["remainingAcquiredIdentities"] = [entry["identity"] for entry in live]
        record["acquiredSubsetRetired"] = not errors and not live if entries else None
        if live:
            errors.append("Recorded consumer fixture retirement is unproven; preserve its generated data")
        for entry in entries:
            def release():
                self.scope._release(entry["handle"])
                entry["released"] = True
            attempt("Recorded consumer handle release", release)
        if not complete:
            errors.append("Whole-chain retirement remains unproven: binding/acquisition did not cover every expected identity")
        record["wholeChainRetired"] = complete and not errors and not live
        record["retirementProven"] = record["wholeChainRetired"]
        path = attempt("Consumer identity fallback evidence", lambda: self.consumer_obligation_event(
            obligation, "identity-cleanup", cleanup=record))
        if path is not None and record["wholeChainRetired"] and not errors:
            attempt("Consumer complete-proof retention resolution", lambda: self.resolve_consumer_retention(
                obligation, obligation, record, path))
        for error in errors:
            self.consumer_retention_error(obligation, "identity cleanup", AssertionError(error))
        if fatal:
            raise fatal[0]
        if errors or record["fallbackUsed"]:
            self.fail("Consumer native ownership required recorded exact-identity fallback cleanup; " + "; ".join(errors))

    def retain_consumer_fixture_states(self, temporary, evidence, *, expect_native=False):
        # Invoked after the fixture's actual ownership drain, including assertion
        # failures. Child native evidence is outside the outer state/evidence, so
        # it must move there before automatic TMPDIR disposal can be permitted.
        created = runner.read_json(evidence / "fixture-created.json")
        base = runner.absolute_path(created["fixtureBase"])
        runner.require(base != temporary and runner.within(base, temporary), "Consumer fixture escaped owned TMPDIR")
        destination = evidence / f"dependent-state-archive-{uuid.uuid4().hex}"
        destination.mkdir(mode=0o700)
        errors, records = [], []
        budget = {"entries": 0, "bytes": 0}
        # These are the producer's two explicit fixture contexts, not a search
        # for arbitrary directories named state or build. Partial setup remains
        # inspectable if producer.json was never successfully finalized.
        for name in ("audit state with spaces", "native audit state"):
            state = base / name
            try:
                present = runner.physical_directory_present(state)
                runner.require(present or (name == "native audit state" and not expect_native),
                               "Required consumer fixture state is missing; preserve unresolved fixture data")
                if not present:
                    continue
                target = destination / name
                target.mkdir(mode=0o700)
                for relative in ("context.json", "gradle-home/gradle.properties"):
                    source = state / relative
                    present = runner.existing_lstat(source) is not None
                    runner.require(present or (relative != "context.json" and name != "native audit state"),
                                   "Required consumer fixture context/policy is missing")
                    if present:
                        records.append(archive_fixture_file(source, target / relative, budget))
                child_evidence = state / "evidence"
                present = runner.existing_lstat(child_evidence) is not None
                runner.require(present or name != "native audit state", "Required native child evidence root is missing")
                if present:
                    records.extend(archive_fixture_tree(child_evidence, target / "evidence", errors, budget))
                with os.scandir(state) as entries:
                    for count, entry in enumerate(entries, start=1):
                        runner.require(count <= runner.MAX_ARCHIVE_FILES, "Child fixture state entry count exceeds its bound")
                        if entry.name.startswith("consumer-receipts."):
                            records.extend(archive_fixture_tree(Path(entry.path), target / entry.name, errors, budget))
            except Exception as error:
                errors.append(f"Consumer child state {state}: {type(error).__name__}: {error}")
        record = {"schema": 1, "kind": "consumer-dependent-state-archive", "fixtureBase": str(base),
                  "destination": str(destination), "archive": records, "errors": errors,
                  "complete": not errors, "scope": "Authentic fixture receipts/logs; wrapper/report bytes are synthetic."}
        runner.write_new_json(destination / "archive.json", record)
        self.assertFalse(errors, "; ".join(errors))
        return record

    def test_posix_launch_trace_keeps_logical_and_resolved_executable_distinct(self):
        requested = [Path(PYTHON).name, "-c", "print('TRACE-NATIVE')"]
        environment = {**self.env, "PATH": str(Path(PYTHON).parent) + os.pathsep + self.env.get("PATH", "")}
        code, out, err, receipt = self.run_leaf(requested, kind="command", env=environment)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(out, b"TRACE-NATIVE\n")
        self.assertEqual(receipt["requestedArgv"], requested)
        self.assertEqual(receipt["executedArgv"], requested)
        launch = receipt["ownership"]["launches"][receipt["productLaunchIndex"]]
        self.assertEqual(launch["api"], "subprocess.Popen")
        self.assertEqual(launch["resolvedArgv"], [PYTHON, *requested[1:]])
        self.assertEqual(launch["executable"], PYTHON)
        self.assertFalse(launch["shell"])
        self.assertNotIn("commandLine", launch)

    def test_real_controller_cancellation_finalizes_and_preserves_sentinel(self):
        sentinel = self.sentinel()
        capture, receipt_path = self.start(["hold"])
        self.ready(self.state / "product-ready")
        identity = self.scope._identity(capture.child.pid)
        self.assertIsNotNone(identity)
        self.scope.discover()
        key = self.scope._key(identity)
        self.scope._send(identity, self.scope.handles[key], processes.SIG_TERM)
        code, _, _ = capture.finish(self.scope)
        self.assertEqual(code, 125)
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["cancelledSignals"], [signal.SIGTERM])
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertEqual(receipt["ownedSurvivors"], [])
        self.assertIsNone(sentinel.poll())

    def test_actual_consumer_fixture_cancellation_retires_detached_child_and_preserves_sentinel(self):
        sentinel = self.sentinel()
        temporary, environment = self.consumer_environment()
        evidence = self.state / "evidence" / f"consumer-cancellation-{uuid.uuid4().hex}"
        ready_path = evidence / "ready.json"
        producer_script = SCRIPTS / "tests/audit-consumer-test.py"
        invocation = uuid.uuid4().hex
        self.fixture_archivists.append(lambda: self.retain_consumer_fixture_states(temporary, evidence))
        command = [PYTHON, str(producer_script), "--ownership-cancellation-fixture", str(ready_path),
                   "--fixture-evidence", str(evidence)]
        obligation = self.begin_consumer_cancellation_obligation(invocation, evidence)
        capture, receipt_path, ready, producer = self.start_consumer_cancellation_producer(obligation, command, environment)
        entries = self.bind_consumer_cancellation_fallback(obligation, capture, ready, producer)

        # Cancel and wait for the authentic outer final receipt BEFORE any marker
        # preservation assertion. The original-erasure negative must still get
        # its applicable wrapper stop; cleanup then retires only bound leftovers.
        cancel = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "request-cancel", "--state", str(self.state),
                                           "--id", invocation], str(self.root), self.env))
        cancelled = cancel.finish(self.scope)
        code, _, err = capture.finish(self.scope)
        receipt = runner.read_json(receipt_path)
        self.assertEqual(cancelled[0], 0, cancelled[2].decode(errors="replace"))
        self.assertEqual(code, 125, err.decode(errors="replace"))
        self.assertTrue(receipt["cancelRequested"])
        self.assertEqual(receipt["cancelledSignals"], [])
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertEqual(receipt["ownedSurvivors"], [])
        self.assertEqual(receipt["productPid"], producer["pid"])
        self.assertEqual(receipt["requestedArgv"], command)
        self.assertEqual(receipt["gradleHome"], self.context["gradleHome"])
        self.assertEqual(receipt["stopArgv"][0], str(self.wrapper))
        self.assertTrue(receipt["sourceUnchanged"])
        self.assertIsNone(sentinel.poll())
        self.assertEqual(ready["schema"], 1)
        self.assertEqual(ready["kind"], "consumer-ownership-cancellation-fixture")
        self.assert_consumer_ancestors(ready["ownership"], environment, invocation)
        self.assert_consumer_ancestors(producer["parentOwnership"], environment, invocation)
        binding = runner.read_json(evidence / "producer.json")
        for observation in (binding["fixtureSetupOwnership"], binding["adapterOwnership"]):
            self.assert_consumer_ancestors(observation, environment, invocation)
        started = {self.scope._key(identity) for identity in receipt["ownership"]["startedIdentities"]}
        self.assertIn(self.scope._key(entries[0]["identity"]), started)
        self.assertTrue(all(not self.consumer_identity_live(entry) for entry in entries),
                        "Authentic cancellation left a bound consumer ancestor/worker live")
        self.assertEqual(producer["producerSha256"], runner.file_digest(producer_script))
        self.assertEqual(producer["consumerScriptSha256"], runner.file_digest(SCRIPTS / "check-published-consumers.sh"))
        self.assertTrue((evidence / "calls.jsonl").is_file())
        self.assertTrue((evidence / "consumer.stdout.log").is_file())
        self.assertTrue((evidence / "consumer.stderr.log").is_file())
        directory = Path(receipt["evidenceDirectory"])
        self.assertEqual((directory / "stop.stdout.log").read_bytes(), b"STOP-ONLY-STDOUT\n")
        self.assertEqual((directory / "stop.stderr.log").read_bytes(), b"STOP-ONLY-STDERR\n")
        runner.write_new_json(CASE_EVIDENCE / "consumer-cancellation-verdict.json", {
            "schema": 1, "receipt": str(receipt_path), "receiptSha256": runner.file_digest(receipt_path),
            "retiredWorker": entries[0]["identity"], "unrelatedSentinelPid": sentinel.pid,
            "unrelatedSentinelSurvived": True, "scope": "Actual native cancellation of synthetic consumer fixture only.",
        })

    def assert_consumer_binding_failure_retains_fixture(self, *, partial_acquisition):
        original_errors = list(self.fixture_retention_errors)
        temporary, environment = self.consumer_environment()
        evidence = self.state / "evidence" / f"consumer-binding-fault-{uuid.uuid4().hex}"
        invocation = uuid.uuid4().hex
        self.fixture_archivists.append(lambda: self.retain_consumer_fixture_states(temporary, evidence))
        command = [PYTHON, str(SCRIPTS / "tests/audit-consumer-test.py"),
                   "--ownership-cancellation-fixture", str(evidence / "ready.json"), "--fixture-evidence", str(evidence)]
        primary = self.begin_consumer_cancellation_obligation(invocation, evidence)
        self.assertTrue(primary["pending"])
        self.assertTrue(set(primary["retentionReasons"]).issubset(self.fixture_retention_errors))
        self.assertFalse((evidence / "ready.json").exists(), "Retention must be established before producer startup")
        capture, receipt_path, ready, producer = self.start_consumer_cancellation_producer(primary, command, environment)
        # Deliberate failure controls use the intact real caller, NEVER the strip
        # mutant. Its real marker scope can be cancelled normally. Independently
        # acquired full-chain tokens are the later recovery authority, not that
        # marker-scope empty survivor list or the incomplete primary binding.
        self.assert_consumer_ancestors(ready["ownership"], environment, invocation)
        recovery = self.begin_consumer_cancellation_obligation(invocation, evidence, recovery_of=primary["id"])
        recovery["capture"] = capture
        recovery_entries = self.bind_consumer_cancellation_fallback(recovery, capture, ready, producer)
        self.assertGreater(len(recovery_entries), 1)
        if partial_acquisition:
            actual_acquire, attempts = self.scope._acquire, []

            def fail_second_acquire(identity):
                attempts.append(dict(identity))
                if len(attempts) == 2:
                    raise PermissionError("injected second consumer capability acquisition failure")
                return actual_acquire(identity)

            with mock.patch.object(self.scope, "_acquire", side_effect=fail_second_acquire):
                with self.assertRaisesRegex(PermissionError, "injected second consumer capability"):
                    self.bind_consumer_cancellation_fallback(primary, capture, ready, producer)
            self.assertEqual(len(attempts), 2)
            self.assertEqual(len(primary["entries"]), 1)
            self.assertGreater(len(primary["verifiedAncestry"]), len(primary["entries"]))
        else:
            with mock.patch.object(self.scope, "_identity", side_effect=PermissionError("injected consumer prebind failure")):
                with self.assertRaisesRegex(PermissionError, "injected consumer prebind"):
                    self.bind_consumer_cancellation_fallback(primary, capture, ready, producer)
            self.assertEqual(primary["entries"], [])
            self.assertEqual(primary["verifiedAncestry"], [])
        self.assertFalse(primary["bindingComplete"])
        self.assertTrue(primary["bindingErrors"])
        self.assertTrue(set(primary["bindingErrors"]).issubset(self.fixture_retention_errors))
        with self.assertRaisesRegex(AssertionError, "Whole-chain retirement remains unproven"):
            self.cleanup_consumer_cancellation_fallback(primary)
        paths = list(CASE_EVIDENCE.glob(f"consumer-cancellation-{primary['id']}-identity-cleanup-*.json"))
        self.assertEqual(len(paths), 1)
        failed = runner.read_json(paths[0])["cleanup"]
        self.assertFalse(failed["wholeChainCovered"])
        self.assertFalse(failed["wholeChainRetired"])
        self.assertFalse(failed["retirementProven"])
        self.assertEqual(failed["acquiredSubsetRetired"], True if partial_acquisition else None)
        self.assertEqual(failed["fallbackUsed"], partial_acquisition)
        self.assertEqual(len(failed["unacquiredIdentities"]),
                         len(primary["verifiedAncestry"]) - len(primary["entries"]))
        self.assertEqual(failed["unobservedAncestry"], not partial_acquisition)
        self.assertTrue(primary["pending"])
        self.assertIsNone(primary["retirementProof"])
        self.assertTrue(any(self.consumer_identity_live(entry) for entry in recovery_entries[1:]),
                        "Control did not exercise still-live unacquired ancestors")

        cancel = Capture(self.scope.spawn([PYTHON, str(EXECUTOR), "request-cancel", "--state", str(self.state),
                                           "--id", invocation], str(self.root), self.env))
        cancelled = cancel.finish(self.scope)
        code, _, err = capture.finish(self.scope)
        receipt = runner.read_json(receipt_path)
        self.assertEqual(cancelled[0], 0)
        self.assertEqual(code, 125, err.decode(errors="replace"))
        self.assertTrue(receipt["cancelRequested"])
        self.assertEqual(receipt["stopExitCode"], 0)
        self.assertEqual(receipt["ownedSurvivors"], [])
        self.assertTrue(receipt["sourceUnchanged"])
        self.cleanup_consumer_cancellation_fallback(recovery)
        self.assertFalse(recovery["pending"])
        proof, proof_path = recovery["retirementProof"]
        self.assertTrue(proof["wholeChainRetired"])
        self.assertFalse(proof["fallbackUsed"])
        self.assertTrue(primary["pending"], "A separate recovery proof must not implicitly resolve the failed primary")
        before = set(CASE_EVIDENCE.glob("teardown-*"))
        with self.assertRaisesRegex(AssertionError, "whole-chain retirement remains unproven"):
            self._cleanup_fixture()
        retained = set(CASE_EVIDENCE.glob("teardown-*")) - before
        self.assertEqual(len(retained), 1)
        retained = retained.pop()
        record = runner.read_json(retained / "cleanup.json")
        self.assertFalse(record["cleanupComplete"])
        self.assertFalse(record["fixtureDataRemoved"])
        self.assertEqual(record["guardSurvivors"], [])
        self.assertTrue(set(primary["retentionReasons"]).issubset(record["errors"]))
        self.assertTrue(self.base.is_dir())
        self.assertTrue(temporary.is_dir())
        self.assertTrue((self.base / f"unresolved-fixture-cleanup-{record['id']}.json").is_file())
        original = Path(receipt["evidenceDirectory"])
        for name in ("start.json", "receipt.json", "product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log"):
            self.assertEqual((retained / "invocations" / original.name / name).read_bytes(), (original / name).read_bytes())

        # Only now explicitly apply the complete same-capture/product/ready/key
        # recovery proof. The failed attempt and no-disposal archive stay intact.
        unrelated = f"test-only unrelated retention marker {uuid.uuid4().hex}"
        self.fixture_retention_errors.append(unrelated)
        self.resolve_consumer_retention(primary, recovery, proof, proof_path)
        self.assertFalse(primary["pending"])
        self.assertIn(unrelated, self.fixture_retention_errors)
        self.fixture_retention_errors.remove(unrelated)  # Only this deliberate test-owned marker, not a real cleanup error.
        self.assertEqual(self.fixture_retention_errors, original_errors)
        self.assertEqual(runner.read_json(paths[0])["cleanup"], failed)
        self.assertFalse(runner.read_json(retained / "cleanup.json")["fixtureDataRemoved"])
        # Registered cleanup sees resolved obligations and performs a separate
        # genuine evidence/disposal attempt; no mutation of native ownership.

    def test_consumer_prebind_failure_preserves_fixture_until_complete_recovery_proof(self):
        self.assert_consumer_binding_failure_retains_fixture(partial_acquisition=False)

    def test_consumer_partial_acquisition_never_promotes_subset_retirement_or_disposes_fixture(self):
        self.assert_consumer_binding_failure_retains_fixture(partial_acquisition=True)

    def test_actual_consumer_caller_with_real_executor_retains_external_report_and_receipts(self):
        sentinel = self.sentinel()
        temporary, environment = self.consumer_environment()
        evidence = self.state / "evidence" / f"consumer-integration-{uuid.uuid4().hex}"
        producer_script = SCRIPTS / "tests/audit-consumer-test.py"
        invocation = uuid.uuid4().hex
        self.fixture_archivists.append(lambda: self.retain_consumer_fixture_states(temporary, evidence, expect_native=True))
        command = [PYTHON, str(producer_script), "--executor-integration-fixture", "--executor", str(EXECUTOR),
                   "--fixture-evidence", str(evidence)]
        code, _, err, outer = self.run_leaf(command, kind="command", invocation=invocation, env=environment)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual([outer[key] for key in ("productExitCode", "stopExitCode", "finalExitCode")], [0, 0, 0])
        self.assertEqual(outer["ownedSurvivors"], [])
        self.assertEqual(outer["errors"], [])
        self.assertTrue(outer["sourceUnchanged"])
        self.assertIsNone(sentinel.poll())
        producer = runner.read_json(evidence / "producer-start.json")
        binding = runner.read_json(evidence / "producer.json")
        completion = runner.read_json(evidence / "producer-completion.json")
        self.assertEqual(completion["exitCode"], 0)
        self.assertEqual(binding["executor"], str(EXECUTOR))
        self.assertEqual(binding["executorSha256"], runner.file_digest(EXECUTOR))
        self.assertEqual(producer["producerSha256"], runner.file_digest(producer_script))
        self.assertEqual(producer["consumerScriptSha256"], runner.file_digest(SCRIPTS / "check-published-consumers.sh"))
        self.assertEqual(outer["productPid"], producer["pid"])
        self.assert_consumer_ancestors(producer["parentOwnership"], environment, invocation)
        self.assert_consumer_ancestors(binding["fixtureSetupOwnership"], environment, invocation)
        self.assert_consumer_ancestors(binding["adapterOwnership"], environment, invocation)
        paths = {key: runner.absolute_path(binding[key]) for key in
                 ("fixtureBase", "fixtureRoot", "fixtureState", "childState", "consumerWorkDir", "fixtureReport")}
        for key, path in paths.items():
            self.assertTrue(runner.within(path, temporary) and path != temporary, key)
            self.assertEqual(completion[key], str(path))
        self.assertEqual(paths["childState"], paths["fixtureBase"] / "native audit state")
        self.assertEqual(paths["consumerWorkDir"].parent, paths["childState"] / "work")
        child_state, fixture_root = paths["childState"], paths["fixtureRoot"]
        context = runner.read_json(child_state / "context.json")
        self.assertEqual(context["host"], processes.host_role())
        self.assertEqual(context["root"], str(fixture_root))
        self.assertEqual(context["source"], runner.source_snapshot(fixture_root))
        self.assertEqual(context["gradleHome"], str(child_state / "gradle-home"))
        self.assertEqual(context["gradlePropertiesSha256"],
                         runner.file_digest(child_state / "gradle-home/gradle.properties"))
        directories = list((child_state / "evidence").iterdir())
        self.assertEqual(len(directories), 2)
        receipts = {}
        for directory in directories:
            receipt_path = directory / "receipt.json"
            receipt = runner.read_json(receipt_path)
            self.assertEqual(receipt["id"], directory.name)
            self.assertEqual(receipt["evidenceDirectory"], str(directory))
            self.assertNotIn(receipt["purpose"], receipts)
            receipts[receipt["purpose"]] = receipt
            self.assertEqual(receipt["schema"], 1)
            self.assertEqual(receipt["host"], processes.host_role())
            self.assertEqual(receipt["jobId"], context["id"])
            self.assertEqual(receipt["kind"], "gradle")
            self.assertEqual(receipt["cwd"], str(fixture_root))
            self.assertEqual(receipt["wrapper"], str(fixture_root / "gradlew"))
            self.assertEqual(receipt["gradleHome"], context["gradleHome"])
            self.assertEqual(receipt["sourceBefore"], context["source"])
            self.assertEqual(receipt["sourceAfter"], context["source"])
            self.assertTrue(receipt["sourceUnchanged"])
            self.assertEqual([receipt[key] for key in ("productExitCode", "stopExitCode", "finalExitCode")], [0, 0, 0])
            self.assertEqual(receipt["errors"], [])
            self.assertEqual(receipt["ownedSurvivors"], [])
            self.assertEqual(receipt["ownership"]["backend"], self.scope.name)
            self.assertEqual(receipt["ownership"]["discoveryErrors"], [])
            self.assertIn(invocation, receipt["ancestorInvocationIds"])
            self.assertEqual(receipt["executedArgv"],
                             [str(fixture_root / "gradlew"), *receipt["requestedArgv"], *runner.AUDIT_FLAGS])
            self.assertEqual(receipt["stopArgv"], [str(fixture_root / "gradlew"), "--stop", "--console=plain",
                             "--no-parallel", "--max-workers=2", f"-Dorg.gradle.jvmargs={runner.JVM_ARGUMENTS}"])
            self.assertEqual(runner.read_json(directory / "start.json")["id"], receipt["id"])
            self.assertEqual((directory / "stop.stdout.log").read_bytes(), b"SYNTHETIC CONSUMER WRAPPER STOP\n")
            self.assertEqual((directory / "stop.stderr.log").read_bytes(), b"")
        self.assertEqual(set(receipts), {"consumer-publish", "consumer-build"})
        self.assertEqual(receipts["consumer-publish"]["requestedArgv"], ["--no-daemon", "--console=plain",
            "publishToMavenLocal", "-Dmaven.repo.local=" + str(paths["consumerWorkDir"] / "repository")])
        build = receipts["consumer-build"]
        self.assertEqual(build["requestedArgv"][:5], ["--no-daemon", "--console=plain", "-p",
            str(paths["consumerWorkDir"] / "consumer"), "-PconsumerRepo=" + str(paths["consumerWorkDir"] / "repository")])
        self.assertEqual(build["requestedArgv"][5:], [":coreJvm:compileKotlin", ":coreJvm:compileJava",
            ":lanJvm:compileKotlin", ":desktopJvm:compileKotlin", ":androidConsumer:compileDebugKotlin",
            ":androidConsumer:processDebugManifest", ":kmpConsumer:compileKotlinJvm", ":kmpConsumer:compileAndroidMain",
            ":kmpConsumer:compileKotlinIosSimulatorArm64", ":kmpConsumer:linkDebugFrameworkIosSimulatorArm64"])
        self.assertEqual(receipts["consumer-publish"]["reports"], [])
        self.assertEqual(len(build["reports"]), 1)
        report = build["reports"][0]
        expected = b'{"fixtureOnly":true,"result":"synthetic-consumer-report-not-compilation"}\n'
        self.assertEqual(report["source"], "external/" + paths["fixtureReport"].relative_to(child_state).as_posix())
        self.assertEqual(report["classification"], "changed-since-admission")
        self.assertEqual(report["sha256"], runner.digest(expected))
        self.assertEqual(report["bytes"], len(expected))
        self.assertEqual(paths["fixtureReport"].read_bytes(), expected)
        self.assertEqual(completion["fixtureReportSha256"], runner.digest(expected))
        self.assertEqual((Path(build["evidenceDirectory"]) / report["retained"]).read_bytes(), expected)
        optional = list(child_state.glob("consumer-receipts.*"))
        self.assertEqual(len(optional), 1)
        self.assertEqual({path.name for path in optional[0].iterdir()}, {"consumer-publish.json", "consumer-build.json"})
        for purpose, receipt in receipts.items():
            self.assertEqual((optional[0] / f"{purpose}.json").read_bytes(),
                             (Path(receipt["evidenceDirectory"]) / "receipt.json").read_bytes())
        calls = [json.loads(line) for line in (evidence / "calls.jsonl").read_text().splitlines()]
        leaves = [call for call in calls if call["kind"] == "gradle"]
        stops = [call for call in calls if call["kind"] == "gradle-stop"]
        self.assertEqual(len(leaves), 2)
        self.assertEqual(len(stops), 2)
        self.assertFalse(any(call["kind"] in ("executor", "curl") for call in calls))
        for call, receipt in zip(leaves, (receipts["consumer-publish"], build)):
            self.assertEqual(call["argv"], receipt["executedArgv"][1:])
            self.assertEqual(call["home"], context["gradleHome"])
            self.assert_consumer_ancestors(call["ownership"], environment, invocation)
        for call, receipt in zip(stops, (receipts["consumer-publish"], build)):
            self.assertEqual(call["argv"], receipt["stopArgv"][1:])
            self.assertEqual(call["home"], context["gradleHome"])
        runner.write_new_json(CASE_EVIDENCE / "consumer-native-integration-verdict.json", {
            "schema": 1, "outerReceipt": outer["evidenceDirectory"], "childState": str(child_state),
            "realNativeReceiptIds": [receipt["id"] for receipt in receipts.values()],
            "retainedReportSha256": report["sha256"], "unrelatedSentinelSurvived": True,
            "scope": "Native executor/caller/report integration with synthetic tools; not product compilation or Apple approval.",
        })


class LinuxNativeTests(PosixNativeTests):
    def test_real_pidfd_stale_handle_cannot_signal_unrelated_sentinel(self):
        child = self.scope.spawn([PYTHON, "-c", "import time; time.sleep(120)"], str(self.root), self.env)
        capture = Capture(child)
        self.scope.discover()
        identity = self.scope._identity(child.pid)
        self.assertIsNotNone(identity)
        handle = self.scope._acquire(identity)
        sentinel = self.sentinel()
        try:
            signal.pidfd_send_signal(handle, signal.SIGTERM)
            capture.finish(self.scope)
            with self.assertRaises(ProcessLookupError):
                signal.pidfd_send_signal(handle, signal.SIGTERM)
            self.assertIsNone(sentinel.poll())
        finally:
            os.close(handle)


class DarwinNativeTests(PosixNativeTests):
    def test_real_opaque_task_token_and_stale_token_leave_sentinel_alive(self):
        self.assertIsInstance(self.scope, processes.DarwinScope)
        child = self.scope.spawn([PYTHON, "-c", "import time; time.sleep(120)"], str(self.root), self.env)
        capture = Capture(child)
        identity = self.scope._identity(child.pid)
        self.assertIsNotNone(identity)
        token = self.scope._acquire(identity)
        sentinel = self.sentinel()
        result = self.scope.proc.proc_signal_with_audittoken(ctypes.byref(token), signal.SIGTERM)
        self.assertEqual(result, 0, "Actual Darwin identity-scoped signal was not admitted")
        capture.finish(self.scope)
        result = self.scope.proc.proc_signal_with_audittoken(ctypes.byref(token), signal.SIGTERM)
        self.assertEqual(result, errno.ESRCH, "Exited audit token must not be accepted or converted to a PID signal")
        self.assertIsNone(sentinel.poll())


class WindowsNativeTests(ExecutorFixtureTests):
    def test_windows_launch_trace_records_exact_system_cmd_framing(self):
        requested = ["argv", "two words", "Ω", "", "tail\\"]
        code, out, err, receipt = self.run_leaf(requested)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(json.loads(out)[:len(requested)], requested)
        launches = receipt["ownership"]["launches"]
        self.assertEqual(len(launches), 2)
        for key, argv in (("productLaunchIndex", receipt["executedArgv"]), ("stopLaunchIndex", receipt["stopArgv"])):
            launch = launches[receipt[key]]
            self.assertEqual(launch["api"], "CreateProcessW")
            self.assertEqual(launch["resolvedArgv"], argv)
            self.assertEqual(launch["applicationName"], self.scope.api.cmd())
            self.assertEqual(launch["commandLine"], processes.batch_command_line(self.scope.api.cmd(), argv))
            self.assertTrue(launch["batch"] and launch["created"] and launch["resumed"])
            self.assertTrue(launch["jobAssignedBeforeResume"])

    def test_windows_cleanup_removes_actual_child_junction_not_external_sentinel(self):
        directory = self.root / "build"
        directory.mkdir()
        outside = self.base / "outside-junction"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_bytes(b"junction target sentinel\x00\xff\n")
        link = directory / "runtime junction"
        command = [self.scope.api.cmd(), "/d", "/v:off", "/c", "mklink", "/J", str(link), str(outside)]
        capture = Capture(self.scope.spawn(command, str(self.root), self.env))
        code, _, err = capture.finish(self.scope)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertEqual(link.lstat().st_reparse_tag, 0xA0000003)
        target_bytes = os.fsencode(os.readlink(link))
        code, _, err = self.cleanup_command(directory)
        self.assertEqual(code, 0, err.decode(errors="replace"))
        self.assertFalse(directory.exists())
        self.assertTrue(outside.is_dir())
        self.assertEqual(sentinel.read_bytes(), b"junction target sentinel\x00\xff\n")
        inspection = self.cleanup_record()["inspections"][0]
        self.assertEqual(inspection["entryCount"], 1)
        self.assertEqual(inspection["links"], [{"path": link.name, "kind": "junction", "reparseTag": 0xA0000003,
            "targetSha256": runner.digest(target_bytes), "targetBytes": len(target_bytes),
            "policy": "unlink-entry-only; do-not-traverse-target"}])

    def test_actual_job_membership_is_verified_before_resume(self):
        marker = self.state / "resumed-marker"
        original_resume = self.scope.api.ResumeThread
        observed = []

        def inspect_before_real_resume(thread):
            members = self.scope._member_pids()
            self.assertTrue(members)
            self.assertFalse(marker.exists(), "Suspended child ran before membership admission")
            observed.extend(members)
            return original_resume(thread)

        self.scope.api.ResumeThread = inspect_before_real_resume
        try:
            capture = Capture(self.scope.spawn([PYTHON, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text('ran')",
                                                 str(marker)], str(self.root), self.env))
        finally:
            self.scope.api.ResumeThread = original_resume
        self.assertEqual(capture.finish(self.scope)[0], 0)
        self.assertIn(capture.child.pid, observed)
        self.assertEqual(marker.read_text(), "ran")

    def test_batch_injection_is_refused_without_product_or_shell_side_effect(self):
        side_effect = self.state / "injected"
        code, _, _, receipt = self.run_leaf(["argv", "x&echo injected>" + str(side_effect)])
        self.assertEqual(code, 125)
        self.assertFalse(side_effect.exists())
        self.assertIsNone(receipt["productExitCode"])

    def test_kernel_job_kills_child_when_controller_exits_without_finally(self):
        ready = self.state / "crash-worker-ready.json"
        control = r'''import json, os, pathlib, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import audit_processes as p
job, leaf, state, home, ready = sys.argv[2:]
scope = p.make_scope(job, leaf, state, home)
env = p.ownership_environment(dict(os.environ), job, leaf, state, home)
code = "import json,os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(json.dumps({'pid':os.getpid()})); time.sleep(120)"
child = scope.spawn([sys.executable, '-c', code, ready], os.getcwd(), env)
end = time.monotonic() + 10
while not pathlib.Path(ready).exists():
    if time.monotonic() > end: os._exit(9)
    time.sleep(.02)
os._exit(0)
'''
        capture = Capture(self.scope.spawn([PYTHON, "-c", control, str(SCRIPTS), self.context["id"], uuid.uuid4().hex,
            str(self.state), self.context["gradleHome"], str(ready)], str(self.root), self.env))
        self.assertEqual(capture.finish(self.scope)[0], 0)
        pid = json.loads(ready.read_text())["pid"]
        deadline = time.monotonic() + 5
        while pid in {row["pid"] for row in self.scope.discover()} and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertNotIn(pid, {row["pid"] for row in self.scope.discover()}, "Kill-on-controller-close did not drain its job")

def main():
    global EVIDENCE_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-host", choices=runner.HOSTS, default=processes.host_role())
    parser.add_argument("--evidence-root", "--evidence-dir", dest="evidence_root")
    args = parser.parse_args()
    if args.expected_host != processes.host_role():
        parser.error("Requested host does not match this native interpreter")
    if args.evidence_root:
        EVIDENCE_ROOT = runner.absolute_path(args.evidence_root, exists=False)
        EVIDENCE_ROOT.mkdir(mode=0o700)
    elif os.environ.get(processes.STATE_ENV):
        state = runner.absolute_path(os.environ[processes.STATE_ENV])
        EVIDENCE_ROOT = state / "evidence" / f"executor-fixtures-{uuid.uuid4().hex}"
        EVIDENCE_ROOT.mkdir(mode=0o700)
    else:
        EVIDENCE_ROOT = Path(tempfile.mkdtemp(prefix="p2pkit-executor-fixture-evidence-")).resolve()
    native = {"Linux": LinuxNativeTests, "Darwin": DarwinNativeTests, "Windows": WindowsNativeTests}.get(
        __import__("platform").system())
    if native is None:
        parser.error("No native ownership fixture suite for this host")
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(PurePolicyTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(native)])
    print(f"Running current-host real executor fixtures: {processes.host_role()}; no other-host/native claims", flush=True)
    print(f"Retained fixture receipts/logs: {EVIDENCE_ROOT}", flush=True)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
