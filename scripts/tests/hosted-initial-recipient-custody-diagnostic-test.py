#!/usr/bin/env python3
"""Offline failure-site/progress controls, NOT Stage1/native/custody qualification.

Import the original custody controller after stdlib initialization and the
persistent offline fence. No previous test/fixture is imported. Original pure
require failures supply source frames; explicitly supplied traceback links test
limits and malformed metadata. Main's guard and selected operation are supplied
in-memory seams: no authority, reader, acquisition, real clock, process or crypto
runs. Progress uses the actual scalar helpers and supplied CPU samples; one
direct collect-export reuse control stops at a supplied pre-crypto failure.
First-head controls use real reraises and the original remember method with
declared anchor/error-callback seams, never constructed native custody owners.
First-LOCAL deadline controls use the actual Window with supplied clock/CPU
samples only; they neither acquire a native owner nor replay hosted evidence.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import ctypes
import dataclasses
import datetime
import errno
import gzip
import hashlib
import http.client
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import platform
import plistlib
import re
import select
import shutil
import signal
import socket
import ssl
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from types import SimpleNamespace, TracebackType
import unittest
from unittest.mock import patch
import urllib.parse
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
THIS = Path(__file__).resolve()
STDLIB = Path(os.__file__).resolve().parent
SOURCE_TOKENS = {
    "run-hosted-initial-recipient-custody.py": "CUSTODY",
    "run-hosted-initial-recipient.py": "PRIMARY",
    "run-hosted-cache-bootstrap.py": "NATIVE",
    "hosted_test_query.py": "QUERY",
    "hosted_test_identity.py": "IDENTITY",
    "hosted_cache_bootstrap_origin.py": "ORIGIN",
    "hosted_initial_recipient_originals.py": "ORIGINALS",
    "hosted_job_clock.py": "CLOCK",
    "hosted_initial_recipient_continuity.py": "CONTINUITY",
    "hosted_cache_bootstrap_service_time.py": "SERVICE_TIME",
}
PATH_TOKENS = {str(SCRIPTS / name): token for name, token in SOURCE_TOKENS.items()}
REFUSAL = "INITIAL_RECIPIENT_CUSTODY_NOT_ACCEPTED\n"
PROGRESS_SCOPE = "INITIAL_RECIPIENT_CUSTODY_FAILURE_PROGRESS_V1"
NS = 1_000_000_000
TIME_FIELDS = ("windowLocalMs", "copyRawMs", "authoritySetupRawMs", "phaseRawMs", "phaseWorkBudgetMs",
    "phaseWorkAtLaunchMs", "localRemainingMs", "rawRemainingMs", "sampledParentGuardMs",
    "phaseSampledParentGuardMs", "parentCpuMs", "phaseParentCpuMs")
PROGRESS_FIELDS = {"schema", "scope", "kind", "phase", "reason", "launchReturned", "polls", "pollsSaturated",
    "lastPoll", *TIME_FIELDS, "diagnosticComplete", "acceptance"}
ACTIVE, BLOCKED, PRIVATE_TOUCHES = False, [], []
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND


def offline(event, args):
    denied = event.startswith(("subprocess.", "socket.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "pty.spawn",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink", "os.truncate",
        "os.chmod", "os.chown", "os.utime", "os.chdir", "os.setuid", "os.seteuid", "os.setgid",
        "os.setegid", "os.setgroups", "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
    }
    if event == "open":
        path = Path(os.fsdecode(args[0])) if isinstance(args[0], (str, bytes)) else None
        public_source = path is not None and ".." not in path.parts and (
            path == THIS or path.parent == SCRIPTS and path.suffix == ".py" or
            path.parent == SCRIPTS / "__pycache__" and path.suffix == ".pyc" or
            STDLIB in path.parents and path.suffix in (".py", ".pyc"))
        write = isinstance(args[1], str) and any(letter in args[1] for letter in "wax+") or (
            type(args[2]) is int and args[2] & WRITE_FLAGS != 0)
        denied = denied or ACTIVE or write or not public_source
    if ACTIVE and event in ("os.listdir", "os.scandir"):
        denied = True
    if denied:
        BLOCKED.append(event)  # Never retain paths or private values.
        raise AssertionError("OFFLINE_CUSTODY_DIAGNOSTIC_REAL_EFFECT")


# Initialize argparse's public stdlib machinery before the import/read fence.
argparse.ArgumentParser(add_help=False).parse_args([])
sys.dont_write_bytecode = True
sys.addaudithook(offline)


def setUpModule():
    global D, MODULES
    if not (sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.flags.dont_write_bytecode == 1):
        raise AssertionError("use actual python3 -I -B -S for offline custody diagnostic controls")
    spec = importlib.util.spec_from_file_location("custody_diagnostic_original_source",
        SCRIPTS / "run-hosted-initial-recipient-custody.py")
    D = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = D
    spec.loader.exec_module(D)
    MODULES = ((D, ("CUSTODY", "IDENTITY")), (D.N, ("PRIMARY", "IDENTITY")),
        (D.native, ("NATIVE", "ORIGIN")), (D.Q, ("QUERY",)), (D.I, ("IDENTITY",)),
        (D.O, ("ORIGIN",)), (D.A, ("ORIGINALS", "IDENTITY")),
        (D.O.clocks, ("CLOCK",)), (D.C, ("CONTINUITY",)),
        (D.native.service_time, ("SERVICE_TIME",)))


def capture_require(module, value="SYNTHETIC_FAILURE_ONLY"):
    try:
        module.require(False, value)
    except BaseException as error:
        return error
    raise AssertionError("original pure require did not refuse")


def original_nodes(error):
    """Only tiny actual call stacks, never the supplied traversal-limit chains."""
    nodes, node = [], error.__traceback__
    for _ in range(16):
        if node is None:
            return nodes
        nodes.append(node)
        node = node.tb_next
    raise AssertionError("unexpected non-tiny original stack")


def original_sites(error):
    return [{"module": PATH_TOKENS[node.tb_frame.f_code.co_filename], "line": node.tb_lineno}
        for node in original_nodes(error) if node.tb_frame.f_code.co_filename in PATH_TOKENS]


def borrowed_node(module):
    node = capture_require(module).__traceback__.tb_next
    if node.tb_frame.f_code is not module.require.__code__:
        raise AssertionError("not the original imported source frame")
    return node


def prepend_cleanup(error, count=64):
    """Real Python reraises, not fabricated traceback links or native cleanup."""
    for _ in range(count):
        try:
            raise error
        except BaseException as observed:
            if observed is not error:
                raise AssertionError("cleanup changed the supplied first error")


def supplied_traceback(rows, tail=None):
    """Declared metadata model; neither authentic frames nor exception authority."""
    for filename, line in reversed(rows):
        tail = SimpleNamespace(tb_frame=SimpleNamespace(f_code=SimpleNamespace(co_filename=filename)),
            tb_lineno=line, tb_next=tail)
    return SimpleNamespace(__traceback__=tail)


class Unprintable:
    def __str__(self):
        PRIVATE_TOUCHES.append("format")
        raise AssertionError("synthetic private DATA must not be formatted")

    __repr__ = __str__


class PrivateFailure(RuntimeError):
    __str__ = Unprintable.__str__
    __repr__ = __str__

    def __getattribute__(self, name):
        if name in ("args", "__class__", "__dict__", "__cause__", "__context__"):
            PRIVATE_TOUCHES.append(name)
            raise AssertionError("synthetic exception metadata must not be inspected")
        return super().__getattribute__(name)

    def __bool__(self):
        return False


class IdentityOnlyFailure(PrivateFailure):
    def __eq__(self, _other):
        PRIVATE_TOUCHES.append("exception-equality")
        raise AssertionError("first-error binding must use identity only")

    __ne__ = __eq__


class OfflineCase(unittest.TestCase):
    def setUp(self):
        global ACTIVE
        self.assertEqual(BLOCKED, [])
        self.assertEqual(PRIVATE_TOUCHES, [])
        ACTIVE = True

    def tearDown(self):
        global ACTIVE
        ACTIVE = False
        self.assertEqual(BLOCKED, [], "even a swallowed forbidden operation fails this control")
        self.assertEqual(PRIVATE_TOUCHES, [], "even a swallowed formatting attempt fails this control")

    def assert_sites(self, error, sites, truncated=False):
        observed = D._failure_sites(error)
        self.assertEqual(observed, {"sites": sites, "truncated": truncated})
        self.assertIs(type(observed), dict)
        self.assertIs(type(observed["truncated"]), bool)
        self.assertIs(type(observed["sites"]), list)
        for row in observed["sites"]:
            self.assertIs(type(row), dict)
            self.assertIs(type(row["module"]), str)
            self.assertIs(type(row["line"]), int)


class FailureSites(OfflineCase):
    def test_all_ten_original_source_frames_and_exact_lines(self):
        for module, tokens in MODULES:
            with self.subTest(module=tokens[0]):
                error = capture_require(module)
                expected = original_sites(error)
                self.assertEqual(tuple(row["module"] for row in expected), tokens)
                self.assert_sites(error, expected)

    def test_empty_and_foreign_original_tracebacks(self):
        self.assert_sites(PrivateFailure(Unprintable()), [])
        try:
            raise PrivateFailure(Unprintable())
        except PrivateFailure as error:
            self.assert_sites(error, [])

    def test_private_args_locals_text_class_and_chains_are_not_observed(self):
        original = capture_require(D.I, Unprintable())
        error = PrivateFailure(Unprintable()).with_traceback(original.__traceback__)
        error.__cause__ = capture_require(D.C)
        error.__context__ = capture_require(D.O)
        expected = original_sites(original)
        self.assertEqual([row["module"] for row in expected], ["IDENTITY"])
        self.assert_sites(error, expected)

    def test_only_exact_paths_match_not_basenames_prefixes_suffixes_or_normalized_paths(self):
        for name, token in SOURCE_TOKENS.items():
            exact = str(SCRIPTS / name)
            foreign = (name, "scripts/" + name, str(SCRIPTS.parent / "other" / name),
                str(SCRIPTS) + "-lookalike/" + name, exact + ".bak", exact + "/child",
                str(SCRIPTS / "nested" / name), str(SCRIPTS / ".." / "scripts" / name))
            for filename in foreign:
                with self.subTest(module=token, variant=foreign.index(filename)):
                    error = supplied_traceback(((filename, 5), (exact, 7)))
                    self.assert_sites(error, [{"module": token, "line": 7}])

    def test_line_bounds_require_exact_int_and_omissions_are_not_truncation(self):
        class IntSubclass(int):
            pass
        path = str(SCRIPTS / "hosted_test_identity.py")
        for line in (True, False, -1, 0, 1_000_001, 1.0, "1", None, IntSubclass(1), Unprintable()):
            self.assert_sites(supplied_traceback(((path, line),)), [])
        for line in (1, 1_000_000):
            self.assert_sites(supplied_traceback(((path, line),)), [{"module": "IDENTITY", "line": line}])

    def test_original_borrowed_frames_keep_last_twelve_with_independent_32_node_limit(self):
        for module, token in ((D.I, "IDENTITY"), (D.native.service_time, "SERVICE_TIME")):
            leaf = borrowed_node(module)
            for count, lines, truncated in ((12, range(1, 13), False), (13, range(2, 14), True),
                    (32, range(21, 33), True), (33, range(21, 33), True)):
                head = None
                for line in range(count, 0, -1):
                    head = TracebackType(head, leaf.tb_frame, leaf.tb_lasti, line)
                error = PrivateFailure().with_traceback(head)
                with self.subTest(module=token, nodes=count):
                    self.assert_sites(error, [{"module": token, "line": line} for line in lines], truncated)
            head = None
            for _ in range(13):
                head = TracebackType(head, leaf.tb_frame, leaf.tb_lasti, 7)
            self.assert_sites(PrivateFailure().with_traceback(head), [{"module": token, "line": 7}] * 12, True)

    def test_omitted_nodes_neither_evict_valid_sites_nor_create_site_truncation(self):
        path = str(SCRIPTS / "hosted_test_identity.py")
        for count in (12, 13):
            for omitted in (("foreign.py", 1), (path, 0)):
                rows = [row for line in range(1, count + 1) for row in ((path, line), omitted)]
                expected = [{"module": "IDENTITY", "line": line} for line in range(count - 11, count + 1)]
                self.assert_sites(supplied_traceback(rows), expected, count > 12)

    def test_foreign_and_invalid_nodes_count_toward_traversal_without_reading_node_33(self):
        path = str(SCRIPTS / "hosted_test_identity.py")
        for omitted in (("foreign.py", 1), (path, 0)):
            rows = [omitted] * 31 + [(path, 99)]
            expected = [{"module": "IDENTITY", "line": 99}]
            self.assert_sites(supplied_traceback(rows), expected)
            # A bare object would fail immediately if node33 were inspected.
            self.assert_sites(supplied_traceback(rows, tail=object()), expected, True)
            self.assert_sites(supplied_traceback([omitted] * 32), [])
            self.assert_sites(supplied_traceback([omitted] * 32, tail=object()), [], True)


class MainFailureSites(OfflineCase):
    def invoke(self, operation="collect-export", kind="gate", *, failure=None, guard_failure=False, stderr=None,
            supplied=None):
        events, signals = [], object()
        stdout = io.StringIO()
        stderr = io.StringIO() if stderr is None else stderr

        def supplied_guard(callback):
            events.append("guard")
            if guard_failure:
                raise failure
            return callback(signals)

        def supplied_operation(actual_kind, cancelled):
            events.append((operation, actual_kind))
            self.assertTrue(callable(cancelled))  # Never call the native cancellation supplier.
            if supplied is not None:
                return supplied(actual_kind, cancelled)
            if failure is not None:
                raise failure

        with patch.object(D.native, "guarded", new=supplied_guard), \
                patch.object(D, operation.replace("-", "_"), new=supplied_operation), \
                patch.object(sys, "argv", [str(THIS), operation, "--kind", kind]), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            code = D.main()
        self.assertEqual(events, ["guard"] if guard_failure else ["guard", (operation, kind)])
        return code, stdout.getvalue(), stderr.getvalue()

    def assert_failure_record(self, result, kind, error, tokens):
        code, stdout, stderr = result
        self.assertEqual((code, stdout), (125, ""))
        self.assertTrue(stderr.startswith(REFUSAL))
        raw = stderr[len(REFUSAL):]
        self.assertTrue(raw.isascii())
        self.assertTrue(raw.endswith("\n"))
        self.assertEqual(len(raw.splitlines()), 1)
        self.assertLessEqual(len(raw), 2049)
        expected = original_sites(error)
        self.assertEqual([row["module"] for row in expected], tokens)
        value = json.loads(raw)
        self.assertIs(type(value["schema"]), int)
        self.assertIs(type(value["truncated"]), bool)
        self.assertEqual(value, {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_FAILURE_SITES_V1",
            "operation": "collect-export", "kind": kind, "sites": expected, "truncated": False})

    def test_gate_and_worker_failures_preserve_generic_125_with_one_private_free_record(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind):
                error = PrivateFailure(Unprintable()).with_traceback(borrowed_node(D.I))
                error.__cause__ = capture_require(D.C)
                error.__context__ = capture_require(D.O)
                self.assert_failure_record(self.invoke(kind=kind, failure=error), kind, error,
                    ["CUSTODY", "CUSTODY", "IDENTITY"])

    def test_synthetic_service_time_arithmetic_failures_expose_distinct_original_sites_without_values(self):
        service_time = D.native.service_time
        arithmetic_lines = []
        # Synthetic invalid final end/charge only; no real hosted operands.
        cases = (("final-end-underflow", service_time.job_end_arithmetic, (-5400 * D.O.NS - 1,)),
            ("charge-product", service_time.basis_arithmetic, (D.O.clocks.UINT64, 0, 253402300799)))
        for branch, operation, values in cases:
            try:
                operation(*values)
            except service_time.ServiceTimeError as original:
                frame = next(node for node in original_nodes(original)
                    if node.tb_frame.f_code is operation.__code__)
                sites = original_sites(original)
                self.assertEqual([row["module"] for row in sites], ["SERVICE_TIME"] * 3)
                self.assertEqual(sites[0]["line"], frame.tb_lineno)
                arithmetic_lines.append(frame.tb_lineno)
                for kind in ("gate", "worker"):
                    with self.subTest(branch=branch, kind=kind):
                        error = PrivateFailure(Unprintable()).with_traceback(original.__traceback__)
                        error.__cause__ = capture_require(D.C, Unprintable())
                        error.__context__ = capture_require(D.O, Unprintable())
                        self.assert_failure_record(self.invoke(kind=kind, failure=error), kind, error,
                            ["CUSTODY", "CUSTODY"] + ["SERVICE_TIME"] * 3)
            else:
                self.fail("synthetic arithmetic did not refuse")
        self.assertEqual(len(set(arithmetic_lines)), 2)

    def test_negative_virtual_basis_is_valid_data_without_failure_sites(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(D, "_failure_sites", side_effect=AssertionError("VALID_ARITHMETIC_HAS_NO_FAILURE")) as sites, \
                redirect_stdout(stdout), redirect_stderr(stderr):
            value = D.native.service_time.basis_arithmetic(0, 0, 0)
            self.assertEqual(value["chargedAgeNs"], 66 * D.O.NS)
            self.assertEqual(value["jobStartBasisNs"], -66 * D.O.NS)
            self.assertEqual(D.native.service_time.job_end_arithmetic(value["jobStartBasisNs"]), 5334 * D.O.NS)
        sites.assert_not_called()
        self.assertEqual((stdout.getvalue(), stderr.getvalue()), ("", ""))

    def test_guard_baseexceptions_are_diagnosed_without_entering_operation(self):
        for error in (KeyboardInterrupt(), SystemExit(17)):
            self.assert_failure_record(self.invoke(failure=error, guard_failure=True), "gate", error, ["CUSTODY"])

    def test_success_and_other_public_command_failures_never_collect_diagnostics(self):
        for operation in ("collect-export", "collect-close", "seal", "seal-for-before"):
            for kind in ("gate", "worker"):
                with self.subTest(operation=operation, kind=kind), \
                        patch.object(D, "_failure_sites", side_effect=AssertionError("unexpected diagnostic")) as sites, \
                        patch.object(D.native, "_custody_progress_traceback",
                            side_effect=AssertionError("unexpected first-head access")) as head:
                    self.assertEqual(self.invoke(operation, kind), (0, "", ""))
                    if operation != "collect-export":
                        self.assertEqual(self.invoke(operation, kind, failure=PrivateFailure()), (125, "", REFUSAL))
                    sites.assert_not_called()
                    head.assert_not_called()

    def test_invalid_kind_is_parser_rejected_before_guard_or_diagnostic(self):
        with patch.object(sys, "argv", [str(THIS), "collect-export", "--kind", "gate-extra"]), \
                patch.object(D.native, "guarded") as guard, patch.object(D, "collect_export") as operation, \
                patch.object(D, "_failure_sites") as sites, \
                redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(SystemExit) as caught:
                D.main()
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn(REFUSAL.strip(), stderr.getvalue())
        self.assertNotIn("INITIAL_RECIPIENT_CUSTODY_FAILURE_SITES_V1", stderr.getvalue())
        guard.assert_not_called()
        operation.assert_not_called()
        sites.assert_not_called()

    def test_child_argument_failures_without_kind_keep_only_the_generic_refusal(self):
        commands = (("_authority", "custody_authority_child"), ("_crypto", "custody_crypto_child"),
            ("_post-export-authority", "_collect_authority_child"), ("_tail-authority", "_tail_authority_child"),
            ("_before-authority", "_before_authority_child"))
        for command, function in commands:
            argv = [str(THIS), command, "--context-sha256", "not-a-sha", "--minimum-ns", "0"]
            if command == "_before-authority":
                for _field, _environment, flag in D.B.SEED_FIELDS:
                    argv.extend((flag, "0"))
                for _field, flag in D.B.PHASE_FIELDS:
                    argv.extend((flag, "0"))
            # Pure invalid digest rejection precedes every native command/supplier.
            with self.subTest(command=command), patch.object(sys, "argv", argv), \
                    patch.object(D.native, "guarded") as guard, patch.object(D, function) as operation, \
                    patch.object(D, "_failure_sites") as sites, \
                    redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(D.main(), 125)
            self.assertEqual((stdout.getvalue(), stderr.getvalue()), ("", REFUSAL))
            guard.assert_not_called()
            operation.assert_not_called()
            sites.assert_not_called()

    def test_collection_formatting_and_oversize_faults_keep_original_refusal_and_125(self):
        for kind in ("gate", "worker"):
            for fault in ("collection", "formatting", "oversize"):
                with self.subTest(kind=kind, fault=fault), ExitStack() as stack:
                    if fault == "collection":
                        diagnostic = stack.enter_context(patch.object(D, "_failure_sites", side_effect=KeyboardInterrupt()))
                    else:
                        diagnostic = stack.enter_context(patch.object(D.json, "dumps",
                            **({"side_effect": SystemExit(19)} if fault == "formatting" else {"return_value": "x" * 2049})))
                    self.assertEqual(self.invoke(kind=kind, failure=PrivateFailure()), (125, "", REFUSAL))
                    diagnostic.assert_called_once()

    def test_only_added_json_write_failure_is_swallowed_without_retry(self):
        class FailingDiagnosticStream(io.StringIO):
            attempts = 0

            def write(self, text):
                if text.startswith("{"):
                    self.attempts += 1
                    raise BrokenPipeError("SYNTHETIC_DIAGNOSTIC_WRITE_FAILURE")
                return super().write(text)

        for kind in ("gate", "worker"):
            stream = FailingDiagnosticStream()
            self.assertEqual(self.invoke(kind=kind, failure=PrivateFailure(), stderr=stream), (125, "", REFUSAL))
            self.assertEqual(stream.attempts, 1)


class FailureProgress(OfflineCase):
    def setUp(self):
        super().setUp()
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(D.native, "_CUSTODY_PROGRESS", None))
        self.patches.enter_context(patch.object(D.native, "time", SimpleNamespace(process_time_ns=self.cpu_sample)))
        self.cpu_values, self.cpu_calls = iter((10_000_000, 20_000_000, 50_000_000)), 0

    def cpu_sample(self):
        self.cpu_calls += 1
        value = next(self.cpu_values)  # Finite supplied script, never a real CPU/acceptance clock.
        if type(value) in (RuntimeError, KeyboardInterrupt, SystemExit):
            raise value
        return value

    def begin(self, kind="gate", phase="AUTHORITY_CHILD", *, launch=True,
            cpu=(10_000_000, 20_000_000, 50_000_000)):
        self.cpu_values, self.cpu_calls = iter(cpu), 0
        D.native._custody_progress_begin(kind)
        D.native._custody_progress_copy_start(100.0, 1000 * NS)
        if phase == "PRIMARY_COPY":
            return
        D.native._custody_progress_copy_complete(1005 * NS)
        D.native._custody_progress_stage("AUTHORITY_SETUP")
        if phase == "AUTHORITY_SETUP":
            return
        D.native._custody_progress_phase(1010 * NS, 1055 * NS, 1100 * NS)
        if launch:
            D.native._custody_progress_launch(1011 * NS)
        if phase != "AUTHORITY_CHILD":
            D.native._custody_progress_stage(phase)

    def window_failure(self, error, *, reason="LOCAL_DEADLINE"):
        # Supplied already-observed operands, not a reimplemented Window/phase.
        D.native._custody_progress_window(128.0, 130.0, 1030 * NS, 130.0, 1055 * NS,
            error=error, reason=reason)

    def record(self, error, kind="gate"):
        D.native._custody_progress_finish(error)
        value = D.native._custody_progress_record(error, kind)
        self.assert_progress(value, kind)
        return value

    def assert_progress(self, value, kind="gate"):
        self.assertIs(type(value), dict)
        self.assertEqual(set(value), PROGRESS_FIELDS)
        self.assertEqual(len(value), 23)
        self.assertIs(type(value["schema"]), int)
        self.assertEqual((value["schema"], value["scope"], value["kind"], value["acceptance"]),
            (1, PROGRESS_SCOPE, kind, "NOT_ESTABLISHED"))
        for name in ("scope", "kind", "acceptance"):
            self.assertIs(type(value[name]), str)
        for name, allowed in (("phase", ("PRIMARY_COPY", "AUTHORITY_SETUP", "AUTHORITY_CHILD",
                "AUTHORITY_POST_CHILD", "CRYPTO_EXPORT", "EXPORT_OUTPUT", "UNAVAILABLE")),
                ("reason", ("LOCAL_BACKWARDS", "LOCAL_DEADLINE", "OTHER")),
                ("lastPoll", ("NOT_POLLED", "RUNNING", "EXITED_ZERO", "EXITED_NONZERO", "INVALID"))):
            self.assertIs(type(value[name]), str)
            self.assertIn(value[name], allowed)
        for name in ("launchReturned", "pollsSaturated", "diagnosticComplete"):
            self.assertIs(type(value[name]), bool)
        self.assertIs(type(value["polls"]), int)
        self.assertTrue(0 <= value["polls"] <= 65535)
        for name in TIME_FIELDS:
            if value[name] is not None:
                self.assertIs(type(value[name]), int)
                low = -900000 if name in ("localRemainingMs", "rawRemainingMs") else 0
                self.assertTrue(low <= value[name] <= 900000)
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        self.assertTrue(raw.isascii())
        self.assertLessEqual(len(raw.encode("ascii")), 2048)

    def failed_operation(self, error, *, cpu=(10_000_000, 20_000_000, 50_000_000)):
        def supplied(kind, _cancelled):
            self.begin(kind, cpu=cpu)
            self.window_failure(error)
            D.native._custody_progress_finish(error)
            raise error
        return supplied

    def invoke(self, **kwargs):
        return MainFailureSites.invoke(self, **kwargs)

    def test_exact_23_field_packet_contains_only_bounded_supplied_measurements(self):
        for kind in ("gate", "worker"):
            self.begin(kind)
            D.native._custody_progress_poll(None)
            D.native._custody_progress_poll(0)
            error = PrivateFailure(Unprintable())
            self.window_failure(error)
            state = D.native._CUSTODY_PROGRESS
            value = self.record(error, kind)
            self.assertIsNot(value, state)
            self.assertEqual(tuple(value[name] for name in TIME_FIELDS),
                (30000, 5000, 5000, 20000, 45000, 44000, 0, 25000, 2000, 2000, 40, 30))
            self.assertEqual((value["phase"], value["polls"], value["lastPoll"]), ("AUTHORITY_CHILD", 2, "EXITED_ZERO"))
            self.assertTrue(value["diagnosticComplete"])
            self.assertEqual(self.cpu_calls, 3)
            self.assertIsNone(D.native._custody_progress_record(error, kind))

    def test_poll_enums_use_exact_observed_types_and_never_invent_an_unlaunched_poll(self):
        for code, expected in ((None, "RUNNING"), (0, "EXITED_ZERO"), (7, "EXITED_NONZERO"),
                (-1, "EXITED_NONZERO"), (True, "INVALID"), (0.0, "INVALID"), (Unprintable(), "INVALID")):
            self.begin()
            D.native._custody_progress_poll(code)
            error = PrivateFailure()
            self.window_failure(error)
            value = self.record(error)
            self.assertEqual((value["polls"], value["lastPoll"]), (1, expected))
            self.assertIs(value["diagnosticComplete"], expected != "INVALID")
        self.begin(launch=False)
        D.native._custody_progress_poll(0)
        error = PrivateFailure()
        self.window_failure(error)
        value = self.record(error)
        self.assertEqual((value["launchReturned"], value["polls"], value["lastPoll"]), (False, 0, "NOT_POLLED"))
        self.assertIsNone(value["phaseWorkAtLaunchMs"])
        self.assertTrue(value["diagnosticComplete"])

    def test_poll_counter_saturates_at_65535_and_only_the_next_observation_sets_the_flag(self):
        self.begin()
        for _ in range(65535):
            D.native._custody_progress_poll(None)
        state = D.native._CUSTODY_PROGRESS
        self.assertEqual(state["polls"], 65535)
        self.assertIs(state["polls_saturated"], False)
        D.native._custody_progress_poll(0)
        error = PrivateFailure()
        self.window_failure(error)
        value = self.record(error)
        self.assertEqual((value["polls"], value["pollsSaturated"], value["lastPoll"]), (65535, True, "EXITED_ZERO"))

    def test_corrupt_poll_state_is_discarded_before_increment_could_normalize_it(self):
        for polls, saturated in ((True, False), (False, False), (-1, False), (65536, False),
                (0.0, False), (Unprintable(), False), (0, 0), (0, None), (1, True)):
            self.begin()
            D.native._CUSTODY_PROGRESS.update(polls=polls, polls_saturated=saturated)
            D.native._custody_progress_poll(None)
            self.assertIsNone(D.native._CUSTODY_PROGRESS)
            self.assertIsNone(D.native._custody_progress_record(PrivateFailure(), "gate"))

    def test_first_error_freezes_phase_poll_samples_and_cpu_before_cleanup_notes(self):
        self.begin()
        D.native._custody_progress_poll(None)
        error = IdentityOnlyFailure(Unprintable()).with_traceback(borrowed_node(D.I))
        later = IdentityOnlyFailure(Unprintable()).with_traceback(borrowed_node(D.C))
        head = error.__traceback__
        self.window_failure(error)
        D.native._custody_progress_stage("EXPORT_OUTPUT")
        D.native._custody_progress_phase(1040 * NS, 1085 * NS, 1130 * NS)
        D.native._custody_progress_launch(1041 * NS)
        D.native._custody_progress_poll(19)
        D.native._custody_progress_window(150.0, 155.0, 1080 * NS, 151.0, 1090 * NS, error=later)
        D.native._custody_progress_failure(later)
        self.assertIs(D.native._CUSTODY_PROGRESS["traceback"], head)
        value = self.record(error)
        self.assertEqual((value["phase"], value["polls"], value["lastPoll"], value["windowLocalMs"]),
            ("AUTHORITY_CHILD", 1, "RUNNING", 30000))
        self.assertEqual((value["sampledParentGuardMs"], value["parentCpuMs"], value["phaseParentCpuMs"]),
            (2000, 40, 30))
        self.assertEqual(self.cpu_calls, 3)

    def test_first_traceback_survives_real_cleanup_reraises_before_main(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind):
                error = capture_require(D.I, Unprintable())
                first_head, expected = error.__traceback__, original_sites(error)
                observed_heads = []

                def fail(actual_kind, _cancelled):
                    self.begin(actual_kind)
                    self.window_failure(error)
                    prepend_cleanup(error)
                    self.assertEqual(D._failure_sites(error), {"sites": [], "truncated": True})
                    D.native._custody_progress_failure(capture_require(D.C, Unprintable()))
                    D.native._custody_progress_finish(error)
                    observed_heads.append(D.native._custody_progress_traceback(error, actual_kind))
                    raise error

                code, stdout, stderr = self.invoke(kind=kind, supplied=fail)
                self.assertEqual((code, stdout), (125, ""))
                lines = stderr.splitlines()
                self.assertEqual((len(lines), lines[0]), (3, REFUSAL.strip()))
                self.assertEqual(json.loads(lines[1]), {"schema": 1,
                    "scope": "INITIAL_RECIPIENT_CUSTODY_FAILURE_SITES_V1", "operation": "collect-export",
                    "kind": kind, "sites": expected, "truncated": False})
                self.assertEqual([row["module"] for row in expected], ["IDENTITY"])
                self.assertEqual(len(observed_heads), 1)
                self.assertIs(observed_heads[0], first_head)
                self.assert_progress(json.loads(lines[2]), kind)
                self.assertTrue(stderr.isascii() and stderr.endswith("\n"))
                self.assertTrue(all(len(line) <= 2048 for line in lines[1:]))
                self.assertEqual(self.cpu_calls, 3)
                self.assertIsNone(D.native._CUSTODY_PROGRESS)

    def test_primary_remember_freezes_first_head_before_callback_and_preserves_failure_flags(self):
        for owner_first in (False, True):
            for mode in ("clean", "unknown", "callback-fault"):
                with self.subTest(owner_first=owner_first, mode=mode):
                    self.begin()
                    first = IdentityOnlyFailure(Unprintable()).with_traceback(borrowed_node(D.I))
                    later = IdentityOnlyFailure(Unprintable()).with_traceback(borrowed_node(D.C))
                    head, calls = first.__traceback__, []
                    # Hook-only DATA seams: no native Owner, registry, resource or acceptance is constructed.
                    owner = SimpleNamespace(original=first if owner_first else None, unknown=False)
                    anchor = SimpleNamespace(binding=(owner,), failure=None)
                    handle = SimpleNamespace(_anchor=lambda: anchor)

                    def report(label, incoming, *, unknown):
                        calls.append((label, incoming, unknown))
                        if unknown:
                            owner.unknown = True
                        prepend_cleanup(first)
                        if mode == "callback-fault":
                            raise KeyboardInterrupt()

                    owner.error = report
                    incoming = later if owner_first else first
                    with patch.object(D, "_PRIMARY_QUARANTINE", []), \
                            patch.object(D.native, "_custody_progress_failure",
                                wraps=D.native._custody_progress_failure) as freeze:
                        self.assertIs(D._PrimaryOwner.remember(handle, incoming, unknown=mode == "unknown"), first)
                        self.assertIs(D._PrimaryOwner.remember(handle, later), first)
                        self.assertIs(anchor.failure, first)
                        self.assertEqual([(label, unknown) for label, _error, unknown in calls],
                            [("custody-primary", mode == "unknown"), ("custody-primary", False)])
                        self.assertIs(calls[0][1], incoming)
                        self.assertIs(calls[1][1], later)
                        freeze.assert_called_once()
                        self.assertIs(freeze.call_args.args[0], first)
                        self.assertIs(owner.unknown, mode != "clean")
                        self.assertEqual(len(D._PRIMARY_QUARANTINE), 0 if mode == "clean" else 1)
                        if mode != "clean":
                            self.assertIs(D._PRIMARY_QUARANTINE[0], handle)
                        D.native._custody_progress_finish(first)
                        self.assertIs(D.native._custody_progress_traceback(first, "gate"), head)
                        self.assertEqual(D._failure_sites(first), {"sites": [], "truncated": True})
                        self.assertEqual(self.cpu_calls, 3)
                        self.record(first)

        for fault in (KeyboardInterrupt(), SystemExit(17)):
            self.begin()
            first, calls = IdentityOnlyFailure(Unprintable()), []
            owner = SimpleNamespace(original=None, unknown=False,
                error=lambda label, error, *, unknown: calls.append((label, error, unknown)))
            anchor = SimpleNamespace(binding=(owner,), failure=None)
            handle = SimpleNamespace(_anchor=lambda: anchor)
            with patch.object(D, "_PRIMARY_QUARANTINE", []), \
                    patch.object(D.native, "_custody_progress_failure", side_effect=fault) as freeze:
                self.assertIs(D._PrimaryOwner.remember(handle, first), first)
                self.assertIs(anchor.failure, first)
                self.assertEqual(len(calls), 1)
                self.assertEqual((calls[0][0], calls[0][2]), ("custody-primary", False))
                self.assertIs(calls[0][1], first)
                self.assertIs(owner.unknown, False)
                self.assertEqual(D._PRIMARY_QUARANTINE, [])
                freeze.assert_called_once()
                self.assertEqual(self.cpu_calls, 2)
                self.assertIsNone(D.native._custody_progress_traceback(first, "gate"))

    def test_traceback_getter_requires_exact_finished_lifecycle_and_does_not_consume_progress(self):
        class OtherKind(str):
            pass
        error = IdentityOnlyFailure(Unprintable()).with_traceback(borrowed_node(D.I))
        foreign = IdentityOnlyFailure(Unprintable()).with_traceback(borrowed_node(D.C))
        for mode in ("absent", "active", "success", "unfinished", "foreign-error", "foreign-finish",
                "wrong-kind", "new-begin", "malformed-state"):
            with self.subTest(mode=mode):
                self.begin()
                if mode not in ("active", "success"):
                    self.window_failure(error)
                if mode == "success":
                    D.native._custody_progress_finish()
                elif mode not in ("active", "unfinished"):
                    D.native._custody_progress_finish(foreign if mode == "foreign-finish" else error)
                if mode == "absent":
                    D.native._custody_progress_clear()
                elif mode == "new-begin":
                    self.begin()
                elif mode == "malformed-state":
                    D.native._CUSTODY_PROGRESS = Unprintable()
                current = foreign if mode == "foreign-error" else error
                state = D.native._CUSTODY_PROGRESS
                head = D.native._custody_progress_traceback(current, "worker" if mode == "wrong-kind" else "gate")
                self.assertIsNone(head)
                self.assertIs(D.native._CUSTODY_PROGRESS, state)
                self.assertEqual(D._failure_sites(current, head),
                    {"sites": original_sites(current), "truncated": False})

        self.begin()
        self.window_failure(error)
        D.native._custody_progress_finish(error)
        state, original_head = D.native._CUSTODY_PROGRESS, error.__traceback__
        for kind in (True, "gate-extra", OtherKind("gate"), Unprintable()):
            self.assertIsNone(D.native._custody_progress_traceback(error, kind))
        for field, invalid in (("active", 0), ("finished", 1), ("kind", OtherKind("gate")),
                ("traceback", None), ("traceback", []), ("traceback", Unprintable())):
            saved = state[field]
            state[field] = invalid
            self.assertIsNone(D.native._custody_progress_traceback(error, "gate"))
            self.assertIs(D.native._CUSTODY_PROGRESS, state)
            state[field] = saved
        for _ in range(2):
            self.assertIs(D.native._custody_progress_traceback(error, "gate"), original_head)
            self.assertIs(D.native._CUSTODY_PROGRESS, state)
        self.record(error)
        self.assertEqual(self.cpu_calls, 3)
        self.assertIsNone(D.native._custody_progress_traceback(error, "gate"))
        self.assertIsNone(D.native._custody_progress_record(error, "gate"))

    def test_traceback_descriptor_bypasses_private_callbacks_and_capture_faults_keep_progress(self):
        class PrivateTracebackFailure(IdentityOnlyFailure):
            def __getattribute__(self, name):
                if name == "__traceback__":
                    PRIVATE_TOUCHES.append("traceback-override")
                    raise AssertionError("capture must use the built-in traceback descriptor")
                return super().__getattribute__(name)
        head = borrowed_node(D.I)
        error = PrivateTracebackFailure(Unprintable()).with_traceback(head)
        error.__cause__, error.__context__ = PrivateFailure(Unprintable()), PrivateFailure(Unprintable())
        self.begin()
        self.window_failure(error)
        D.native._custody_progress_finish(error)
        saved = D.native._custody_progress_traceback(error, "gate")
        self.assertIs(saved, head)
        self.assertEqual(D._failure_sites(error, saved),
            {"sites": [{"module": "IDENTITY", "line": head.tb_lineno}], "truncated": False})
        self.record(error)
        self.assertEqual(self.cpu_calls, 3)
        # No traceback yet, and malformed non-BaseException descriptor input, respectively.
        for unavailable in (PrivateFailure(Unprintable()), Unprintable()):
            self.begin()
            self.window_failure(unavailable)
            D.native._custody_progress_finish(unavailable)
            self.assertIsNone(D.native._custody_progress_traceback(unavailable, "gate"))
            self.record(unavailable)
            self.assertEqual(self.cpu_calls, 3)
        late = PrivateFailure(Unprintable())
        code, stdout, stderr = self.invoke(supplied=self.failed_operation(late))
        self.assertEqual((code, stdout, len(stderr.splitlines())), (125, "", 3))
        self.assertEqual(json.loads(stderr.splitlines()[1])["sites"], original_sites(late))
        self.assert_progress(json.loads(stderr.splitlines()[2]))
        self.assertEqual(PRIVATE_TOUCHES, [])

    def test_saved_real_head_keeps_original_32_node_12_site_path_and_line_bounds(self):
        leaf = borrowed_node(D.I)

        def project(head):
            self.begin()
            error = PrivateFailure(Unprintable()).with_traceback(head)
            self.window_failure(error)
            D.native._custody_progress_finish(error)
            prepend_cleanup(error)
            saved = D.native._custody_progress_traceback(error, "gate")
            self.assertIs(saved, head)
            self.assertEqual(D._failure_sites(error), {"sites": [], "truncated": True})
            self.assertEqual(self.cpu_calls, 3)
            return D._failure_sites(error, saved)

        for count, lines, truncated in ((12, range(1, 13), False), (13, range(2, 14), True),
                (32, range(21, 33), True), (33, range(21, 33), True)):
            head = None
            for line in range(count, 0, -1):
                head = TracebackType(head, leaf.tb_frame, leaf.tb_lasti, line)
            self.assertEqual(project(head),
                {"sites": [{"module": "IDENTITY", "line": line} for line in lines], "truncated": truncated})
        foreign = original_nodes(capture_require(D.I))[0]
        self.assertIs(foreign.tb_frame.f_code, capture_require.__code__)
        self.assertNotIn(foreign.tb_frame.f_code.co_filename, PATH_TOKENS)
        head = None
        for node, line in reversed(((leaf, 0), (foreign, 7), (leaf, 1), (leaf, 1_000_000), (leaf, 1_000_001))):
            head = TracebackType(head, node.tb_frame, node.tb_lasti, line)
        self.assertEqual(project(head), {"sites": [{"module": "IDENTITY", "line": 1},
            {"module": "IDENTITY", "line": 1_000_000}], "truncated": False})
        current = capture_require(D.C)
        for invalid in (None, True, [], SimpleNamespace(), Unprintable()):
            self.assertEqual(D._failure_sites(current, invalid),
                {"sites": original_sites(current), "truncated": False})

    def test_main_traceback_accessor_faults_use_one_legacy_walk_without_losing_progress(self):
        for fault in (KeyboardInterrupt(), SystemExit(19)):
            error = PrivateFailure(Unprintable()).with_traceback(borrowed_node(D.I))
            with patch.object(D.native, "_custody_progress_traceback", side_effect=fault) as head, \
                    patch.object(D, "_failure_sites", wraps=D._failure_sites) as sites:
                code, stdout, stderr = self.invoke(supplied=self.failed_operation(error))
            head.assert_called_once()
            sites.assert_called_once()
            self.assertIs(sites.call_args.args[0], error)
            self.assertIsNone(sites.call_args.args[1])
            self.assertEqual((code, stdout), (125, ""))
            lines = stderr.splitlines()
            self.assertEqual((len(lines), lines[0]), (3, REFUSAL.strip()))
            self.assertEqual(json.loads(lines[1])["sites"], original_sites(error))
            self.assert_progress(json.loads(lines[2]))
            self.assertIsNone(D.native._CUSTODY_PROGRESS)
            self.assertEqual(self.cpu_calls, 3)

    def test_absent_active_success_unfinished_and_foreign_lifecycles_never_emit(self):
        error, foreign = PrivateFailure(), PrivateFailure()
        self.assertIsNone(D.native._custody_progress_record(error, "gate"))
        for mode in ("active", "success", "unfinished", "foreign-error", "foreign-finish", "wrong-kind", "new-begin"):
            self.begin()
            if mode not in ("active", "success"):
                self.window_failure(error)
            if mode == "success":
                D.native._custody_progress_finish()
            elif mode == "foreign-finish":
                D.native._custody_progress_finish(foreign)
            elif mode not in ("active", "unfinished"):
                D.native._custody_progress_finish(error)
            if mode == "new-begin":
                self.begin()  # Same kind, but an old completed failure is no authority for this parent.
            result = D.native._custody_progress_record(foreign if mode == "foreign-error" else error,
                "worker" if mode == "wrong-kind" else "gate")
            self.assertIsNone(result)
            self.assertIsNone(D.native._custody_progress_record(error, "gate"))

    def test_cpu_faults_baseexceptions_bad_types_and_backwards_samples_are_independently_nullable(self):
        cases = (((KeyboardInterrupt(), 20_000_000, 50_000_000), (None, 30)),
            ((10_000_000, SystemExit(9), 50_000_000), (40, None)),
            ((10_000_000, 20_000_000, RuntimeError()), (None, None)),
            ((True, 20_000_000, 50_000_000), (None, 30)),
            ((10_000_000, Unprintable(), 50_000_000), (40, None)),
            ((10_000_000, 20_000_000, 2 ** 63), (None, None)),
            ((60_000_000, 20_000_000, 50_000_000), (None, 30)),
            ((10_000_000, 60_000_000, 50_000_000), (40, None)),
            ((0, 10_000_000, 900 * NS + 1), (None, 899990)))
        for samples, expected in cases:
            self.begin(cpu=samples)
            error = PrivateFailure()
            self.window_failure(error)
            value = self.record(error)
            self.assertEqual((value["parentCpuMs"], value["phaseParentCpuMs"]), expected)
            self.assertFalse(value["diagnosticComplete"])
            self.assertEqual((value["rawRemainingMs"], self.cpu_calls), (25000, 3))

    def test_numeric_bounds_are_checked_before_truncation_without_coercing_objects(self):
        class OtherInt(int):
            pass
        ms = D.native._custody_progress_ms
        self.assertEqual((ms(0, 0), ms(0, 900), ms(900, 0, signed=True)), (0, 900000, -900000))
        self.assertEqual((ms(0, 900 * NS, ns=True), ms(900 * NS, 0, ns=True, signed=True)), (900000, -900000))
        self.assertIsNone(ms(0, math.nextafter(900.0, math.inf)))
        self.assertIsNone(ms(0, 900 * NS + 1, ns=True))
        self.assertIsNone(ms(1.0, math.nextafter(1.0, 0.0)))
        self.assertIsNone(ms(1, 0, ns=True))
        self.assertIsNone(ms(900 * NS + 1, 0, ns=True, signed=True))
        for invalid in (True, -1, math.nan, math.inf, "0", OtherInt(0), Unprintable()):
            self.assertIsNone(ms(invalid, invalid))
            self.assertIsNone(ms(invalid, invalid, ns=True))
        self.assertIsNone(ms(2 ** 64, 2 ** 64, ns=True))

    def test_unavailable_or_invalid_window_spans_poison_both_guard_subtotals_not_to_zero(self):
        for first, last in ((None, None), (128.0, 127.0), (128.0, math.nan),
                (0.0, math.nextafter(900.0, math.inf))):
            self.begin()
            D.native._custody_progress_window(112.0, 113.0, 1015 * NS, 130.0, 1055 * NS)
            error = PrivateFailure()
            D.native._custody_progress_window(first, last, 1030 * NS, 130.0, 1055 * NS, error=error)
            value = self.record(error)
            self.assertIsNone(value["sampledParentGuardMs"])
            self.assertIsNone(value["phaseSampledParentGuardMs"])
            self.assertFalse(value["diagnosticComplete"])

    def test_completeness_requires_reached_stage_operands_and_later_stages_remain_incomplete(self):
        for phase in ("PRIMARY_COPY", "AUTHORITY_SETUP", "AUTHORITY_CHILD", "AUTHORITY_POST_CHILD",
                "CRYPTO_EXPORT", "EXPORT_OUTPUT"):
            self.begin(phase=phase)
            error = PrivateFailure()
            self.window_failure(error)
            value = self.record(error)
            self.assertEqual(value["phase"], phase)
            self.assertIs(value["diagnosticComplete"], phase in ("PRIMARY_COPY", "AUTHORITY_SETUP", "AUTHORITY_CHILD"))
            if phase in ("PRIMARY_COPY", "AUTHORITY_SETUP"):
                self.assertEqual((value["launchReturned"], value["polls"], value["lastPoll"]), (False, 0, "NOT_POLLED"))
                self.assertIsNone(value["phaseRawMs"])
                self.assertIsNone(value["phaseParentCpuMs"])
        for field, public in (("first_local", "windowLocalMs"), ("first_raw", "copyRawMs"),
                ("copy_close", "authoritySetupRawMs"), ("phase_work", "phaseWorkBudgetMs"),
                ("phase_guard_seconds", "phaseSampledParentGuardMs")):
            self.begin()
            D.native._CUSTODY_PROGRESS[field] = None
            error = PrivateFailure()
            self.window_failure(error)
            value = self.record(error)
            self.assertIsNone(value[public])
            self.assertFalse(value["diagnosticComplete"])

    def test_phase_raw_and_guard_subtotal_stop_at_post_child_but_overall_samples_continue(self):
        self.begin()
        D.native._custody_progress_window(112.0, 112.5, 1015 * NS, 130.0, 1055 * NS)
        D.native._custody_progress_stage("AUTHORITY_POST_CHILD")
        D.native._custody_progress_window(113.0, 114.0, 1020 * NS, 130.0, 1055 * NS)
        D.native._custody_progress_stage("CRYPTO_EXPORT")
        D.native._custody_progress_stage("EXPORT_OUTPUT")
        error = PrivateFailure()
        self.window_failure(error)
        value = self.record(error)
        self.assertEqual((value["phase"], value["phaseRawMs"], value["phaseSampledParentGuardMs"],
            value["sampledParentGuardMs"]), ("EXPORT_OUTPUT", 5000, 500, 3500))
        self.assertFalse(value["diagnosticComplete"])

    def test_outer_other_failure_never_labels_a_prior_success_sample_as_failure_local(self):
        self.begin()
        D.native._custody_progress_window(112.0, 113.0, 1020 * NS, 130.0, 1055 * NS)
        error = PrivateFailure()
        D.native._custody_progress_failure(error)
        value = self.record(error)
        self.assertEqual((value["reason"], value["sampledParentGuardMs"], value["phaseRawMs"]), ("OTHER", 1000, 10000))
        for field in ("windowLocalMs", "localRemainingMs", "rawRemainingMs"):
            self.assertIsNone(value[field])
        self.assertFalse(value["diagnosticComplete"])

    def test_corrupt_record_enums_types_ranges_and_backing_state_are_omitted(self):
        class OtherKind(str):
            pass
        error = PrivateFailure(Unprintable())
        for state in (None, [], Unprintable(), {"active": False, "finished": True, "error": error}):
            D.native._CUSTODY_PROGRESS = state
            self.assertIsNone(D.native._custody_progress_record(error, "gate"))
        for field, invalid in (("kind", True), ("phase", "FOREIGN"), ("reason", Unprintable()),
                ("launch_returned", 1), ("polls", True), ("polls", -1), ("polls", 65536),
                ("polls_saturated", 0), ("last_poll", "RUNNING"), ("local_remaining", True),
                ("raw_remaining", 900001)):
            self.begin()
            self.window_failure(error)
            D.native._custody_progress_finish(error)
            D.native._CUSTODY_PROGRESS[field] = invalid
            self.assertIsNone(D.native._custody_progress_record(error, "gate"))
            self.assertIsNone(D.native._CUSTODY_PROGRESS)
        for kind in (True, "gate-extra", OtherKind("gate"), Unprintable()):
            D.native._custody_progress_begin(kind)
            self.assertIsNone(D.native._CUSTODY_PROGRESS)

    def test_unprintable_exception_environment_token_native_rows_and_captures_are_not_traversed(self):
        class PrivateValue(Unprintable):
            def denied(self, *_args, **_kwargs):
                PRIVATE_TOUCHES.append("traversal-or-coercion")
                raise AssertionError("supplied private canary must remain unread")
            __getitem__ = __iter__ = __len__ = __int__ = __float__ = get = items = keys = values = denied
        canary = PrivateValue()
        with patch.object(D.native.os, "environ", canary):
            self.begin()
            D.native._CUSTODY_PROGRESS.update(environment=canary, token=canary, native_row=canary, captures=canary)
            error = PrivateFailure(canary)
            error.__cause__, error.__context__ = PrivateFailure(canary), PrivateFailure(canary)
            self.window_failure(error)
            value = self.record(error)
        self.assertEqual(set(value), PROGRESS_FIELDS)
        self.assertEqual(PRIVATE_TOUCHES, [])

    def test_direct_same_kind_same_latched_error_clears_unconsumed_finished_snapshot_before_registration(self):
        head = borrowed_node(D.I)
        error, calls = PrivateFailure(Unprintable()).with_traceback(head), []
        def fail(kind, _cancelled):
            calls.append(kind)
            D.native._custody_progress_copy_start(100.0, 1000 * NS)
            self.window_failure(error)
            raise error
        with patch.object(D, "_COLLECT_ATTEMPTS", {}), patch.object(D, "_export_pre_crypto", new=fail):
            with self.assertRaises(PrivateFailure) as first:
                D.collect_export("gate", lambda: None)
            self.assertIs(first.exception, error)
            self.assertIs(D.native._CUSTODY_PROGRESS["error"], error)
            self.assertIs(D.native._CUSTODY_PROGRESS["finished"], True)
            self.assertIs(D.native._custody_progress_traceback(error, "gate"), head)
            # Deliberately do not consume the first parent's completed packet.
            with self.assertRaises(PrivateFailure) as second:
                D.collect_export("gate", lambda: None)
            self.assertIs(second.exception, error)
            self.assertEqual(calls, ["gate"])
            self.assertEqual(self.cpu_calls, 2)
            self.assertIsNone(D.native._custody_progress_traceback(error, "gate"))
            self.assertIsNone(D.native._custody_progress_record(error, "gate"))

    def test_main_keeps_generic_then_original_sites_then_one_compact_progress_line(self):
        for kind in ("gate", "worker"):
            error = PrivateFailure(Unprintable()).with_traceback(borrowed_node(D.I))
            expected_sites = original_sites(error)
            code, stdout, stderr = self.invoke(kind=kind, supplied=self.failed_operation(error))
            self.assertEqual((code, stdout), (125, ""))
            lines = stderr.splitlines()
            self.assertEqual((len(lines), lines[0]), (3, REFUSAL.strip()))
            sites = json.loads(lines[1])
            self.assertEqual(sites, {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_FAILURE_SITES_V1",
                "operation": "collect-export", "kind": kind, "sites": expected_sites, "truncated": False})
            value = json.loads(lines[2])
            self.assert_progress(value, kind)
            self.assertEqual(lines[2], json.dumps(value, sort_keys=True, separators=(",", ":"),
                ensure_ascii=True, allow_nan=False))
            self.assertTrue(stderr.endswith("\n"))
            self.assertIsNone(D.native._custody_progress_record(error, kind))

    def test_main_success_cpu_faults_and_same_error_guard_failure_cannot_publish_stale_progress(self):
        def success(kind, _cancelled):
            self.begin(kind, cpu=(KeyboardInterrupt(), SystemExit(7)))
            D.native._custody_progress_finish()
        with patch.object(D.native, "_custody_progress_record", wraps=D.native._custody_progress_record) as record:
            self.assertEqual(self.invoke(supplied=success), (0, "", ""))
            record.assert_not_called()
        self.assertEqual(self.cpu_calls, 2)
        self.assertIsNone(D.native._CUSTODY_PROGRESS)
        error = PrivateFailure()
        self.begin()
        self.window_failure(error)
        D.native._custody_progress_finish(error)
        code, stdout, stderr = self.invoke(failure=error, guard_failure=True)
        self.assertEqual((code, stdout, len(stderr.splitlines())), (125, "", 2))
        self.assertNotIn(PROGRESS_SCOPE, stderr)
        self.assertIsNone(D.native._CUSTODY_PROGRESS)
        code, stdout, stderr = self.invoke(supplied=self.failed_operation(error,
            cpu=(10_000_000, 20_000_000, SystemExit(8))))
        value = json.loads(stderr.splitlines()[2])
        self.assertEqual((code, stdout, self.cpu_calls), (125, "", 3))
        self.assertIsNone(value["parentCpuMs"])
        self.assertIsNone(value["phaseParentCpuMs"])
        self.assertFalse(value["diagnosticComplete"])

        def corrupt(kind, _cancelled):
            self.begin(kind)
            self.window_failure(error)
            D.native._custody_progress_finish(error)
            D.native._CUSTODY_PROGRESS = Unprintable()
            raise error
        code, stdout, stderr = self.invoke(supplied=corrupt)
        self.assertEqual((code, stdout, len(stderr.splitlines())), (125, "", 2))
        self.assertNotIn(PROGRESS_SCOPE, stderr)

    def test_new_progress_format_oversize_and_write_faults_keep_generic_sites_and_125_without_retry(self):
        original_dumps = json.dumps
        for fault in ("format", "oversize", "write"):
            attempts = []
            class ProgressStream(io.StringIO):
                def write(self, text):
                    if fault == "write" and PROGRESS_SCOPE in text:
                        attempts.append("write")
                        raise BrokenPipeError("SUPPLIED_PROGRESS_ONLY_WRITE_FAULT")
                    return super().write(text)
            def dumps(value, **kwargs):
                if value.get("scope") == PROGRESS_SCOPE:
                    attempts.append("format")
                    if fault == "format":
                        raise SystemExit(11)
                    if fault == "oversize":
                        return "x" * 2049
                return original_dumps(value, **kwargs)
            error = PrivateFailure(Unprintable())
            with patch.object(D.json, "dumps", new=dumps):
                code, stdout, stderr = self.invoke(supplied=self.failed_operation(error), stderr=ProgressStream())
            self.assertEqual((code, stdout), (125, ""))
            self.assertEqual(stderr.splitlines()[0], REFUSAL.strip())
            self.assertEqual(len(stderr.splitlines()), 2)
            self.assertEqual(json.loads(stderr.splitlines()[1])["sites"], original_sites(error))
            self.assertEqual(attempts, ["format", "write"] if fault == "write" else ["format"])
            self.assertIsNone(D.native._CUSTODY_PROGRESS)


class WindowDeadlineFirstLocalTests(OfflineCase):
    """Original Window semantics with synthetic readings, no real clock/owner."""

    def setUp(self):
        super().setUp()
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(D, "_WINDOWS", {}))
        self.patches.enter_context(patch.object(D, "_RETIRED_PRODUCTIVE_WINDOWS", {}))
        self.patches.enter_context(patch.object(D.native, "_CUSTODY_PROGRESS", None))
        self.patches.enter_context(patch.object(D, "time", SimpleNamespace(monotonic=self.local_sample)))
        self.patches.enter_context(patch.object(D.native, "time", SimpleNamespace(process_time_ns=self.cpu_sample)))
        self.patches.enter_context(patch.object(D.O.clocks, "checked_now", new=self.raw_sample))
        self.patches.enter_context(patch.object(D.C, "boot_digest", new=self.boot_sample))

    def local_sample(self):
        self.trace.append(("LOCAL",))
        if self.local_fault is not None:
            raise self.local_fault
        return next(self.locals)

    def raw_sample(self, clock, *, minimum_ns):
        self.assertIs(clock, self.clock)
        self.trace.append(("RAW", minimum_ns))
        return next(self.raws)

    def boot_sample(self, role):
        self.assertEqual(role, "linux-x64")
        self.trace.append(("BOOT", role))
        return "a" * 64

    def cancel_sample(self):
        self.trace.append(("CANCEL",))

    def cpu_sample(self):
        self.cpu_calls += 1
        return self.cpu_calls * 10_000_000  # Supplied scalar samples, not a performance measurement.

    def new_window(self, *, active, phase="PRIMARY_COPY"):
        self.trace, self.cpu_calls, self.local_fault = [], 0, None
        self.locals, self.raws = iter(()), iter(())
        self.clock = D.O.clocks.ClockIdentity("linux-x64", D.O.clocks.DOMAINS["linux-x64"], NS)
        self.first = D.O.clocks.Reading(self.clock, 1000 * NS)
        self.window = D.Window(self.first, 100.0, "a" * 64, D.schedule("gate", 1000 * NS, 1000 * NS),
            self.cancel_sample)
        D.native._custody_progress_clear()
        if active:
            D.native._custody_progress_begin("gate")
            D.native._custody_progress_copy_start(100.0, 1000 * NS)
            if phase == "AUTHORITY_CHILD":
                # Supplied earlier progress only, never a real authority/native episode.
                D.native._custody_progress_copy_complete(1005 * NS)
                D.native._custody_progress_stage("AUTHORITY_SETUP")
                D.native._custody_progress_phase(1010 * NS, 1055 * NS, 1100 * NS)
                D.native._custody_progress_launch(1011 * NS)
                D.native._custody_progress_poll(0)
        return self.window._anchor()

    def sticky(self, original):
        trace, cpu = tuple(self.trace), self.cpu_calls
        for invoke in (self.window.now, lambda: self.window.deadline(0), lambda: self.window.now(final=True)):
            with self.assertRaises(type(original)) as caught:
                invoke()
            self.assertIs(caught.exception, original)
        self.assertEqual((tuple(self.trace), self.cpu_calls), (trace, cpu))
        self.assertIs(self.window._anchor().failure, original)
        self.assertFalse(self.window._anchor().busy)

    def record(self, error):
        D.native._custody_progress_finish(error)
        value = D.native._custody_progress_record(error, "gate")
        if value is not None:
            FailureProgress.assert_progress(self, value)
        return value

    def test_initial_local_refusal_active_and_inactive_keep_exact_observations_and_frontiers(self):
        for mode in ("backwards", "at-end", "after-end"):
            observations = []
            for active in (False, True):
                with self.subTest(mode=mode, active=active):
                    anchor = self.new_window(active=active)
                    raw_end, local_end = anchor.binding[4][0], anchor.binding[5][0]
                    local = 99.0 if mode == "backwards" else local_end if mode == "at-end" else local_end + 1.0
                    self.locals = iter((local,))
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with patch.object(D.native, "_custody_progress_window", wraps=D.native._custody_progress_window) as note, \
                            redirect_stdout(stdout), redirect_stderr(stderr), \
                            self.assertRaisesRegex(ValueError, "WINDOW_DEADLINE_LOCAL") as caught:
                        self.window.deadline(5)
                    error = caught.exception
                    self.assertEqual(note.call_count, 1)
                    self.assertEqual(note.call_args.args, (local, local, 1000 * NS, local_end, raw_end))
                    self.assertIs(note.call_args.kwargs["error"], error)
                    self.assertEqual(note.call_args.kwargs["reason"],
                        "LOCAL_BACKWARDS" if mode == "backwards" else "LOCAL_DEADLINE")
                    self.assertEqual((stdout.getvalue(), stderr.getvalue()), ("", ""))
                    self.assertEqual(self.trace, [("LOCAL",)])
                    self.assertEqual((anchor.last, anchor.local_last), (1000 * NS, 100.0))
                    self.sticky(error)
                    observations.append((type(error), str(error), tuple(self.trace), anchor.last, anchor.local_last))
                    value = self.record(error)
                    if active:
                        self.assertIsNotNone(value)
                        self.assertEqual(value["reason"], note.call_args.kwargs["reason"])
                        self.assertEqual(value["rawRemainingMs"], 180000)
                        self.assertEqual(value["sampledParentGuardMs"], 0)
                        self.assertEqual(value["localRemainingMs"], int((local_end - local) * 1000))
                        self.assertEqual(value["windowLocalMs"], None if mode == "backwards" else int((local - 100) * 1000))
                        self.assertEqual(value["diagnosticComplete"], mode != "backwards")
                    else:
                        self.assertIsNone(value)
            self.assertEqual(observations[0], observations[1])

    def test_equal_initial_local_success_keeps_original_trace_and_only_existing_observer_note(self):
        observations = []
        for active in (False, True):
            with self.subTest(active=active):
                anchor = self.new_window(active=active)
                self.locals = iter((100.0, 101.0, 102.0, 103.0))
                self.raws = iter((1000 * NS + 1, 1000 * NS + 2))
                with patch.object(D.native, "_custody_progress_window", wraps=D.native._custody_progress_window) as note:
                    result = self.window.deadline(5)
                self.assertEqual(result, math.nextafter(105.0, -math.inf))
                self.assertEqual(self.trace, [("LOCAL",), ("LOCAL",), ("RAW", 1000 * NS),
                    ("BOOT", "linux-x64"), ("CANCEL",), ("LOCAL",), ("RAW", 1000 * NS + 1), ("LOCAL",)])
                self.assertEqual(note.call_count, 1)
                self.assertEqual(note.call_args.args, (101.0, 103.0, 1000 * NS + 2,
                    anchor.binding[5][0], anchor.binding[4][0]))
                self.assertEqual(note.call_args.kwargs, {})
                self.assertEqual((anchor.last, anchor.local_last), (1000 * NS + 2, 103.0))
                self.assertIsNone(anchor.failure)
                self.assertFalse(anchor.busy)
                observations.append((result, tuple(self.trace), anchor.last, anchor.local_last))
                self.assertIsNone(self.record(None))
        self.assertEqual(observations[0], observations[1])

    def test_initial_failure_adds_zero_span_and_keeps_original_raw_limit_and_later_phase_incomplete(self):
        anchor = self.new_window(active=True, phase="AUTHORITY_CHILD")
        self.locals, self.raws = iter((111.0, 112.0, 113.0)), iter((1011 * NS, 1012 * NS))
        with patch.object(D.native, "_custody_progress_window", wraps=D.native._custody_progress_window) as note:
            self.assertEqual(self.window.now(), 1012 * NS)
            self.assertEqual(note.call_count, 1)
            before = tuple(self.trace)
            D.native._custody_progress_stage("CRYPTO_EXPORT")
            self.locals = iter((300.0,))
            with self.assertRaisesRegex(ValueError, "WINDOW_DEADLINE_LOCAL") as caught:
                self.window.deadline(5, limit=1040 * NS)
            self.assertEqual(note.call_count, 2)
            self.assertEqual(note.call_args.args, (300.0, 300.0, 1012 * NS, anchor.binding[5][0], 1040 * NS))
            self.assertIs(note.call_args.kwargs["error"], caught.exception)
            self.sticky(caught.exception)
            self.assertEqual(note.call_count, 2)
        self.assertEqual(tuple(self.trace), (*before, ("LOCAL",)))
        self.assertEqual((anchor.last, anchor.local_last), (1012 * NS, 113.0))
        value = self.record(caught.exception)
        self.assertIsNotNone(value)
        self.assertEqual((value["phase"], value["reason"], value["windowLocalMs"]),
            ("CRYPTO_EXPORT", "LOCAL_DEADLINE", 200000))
        self.assertEqual((value["sampledParentGuardMs"], value["phaseSampledParentGuardMs"], value["phaseRawMs"]),
            (2000, 2000, 2000))
        self.assertEqual(value["rawRemainingMs"], 28000)
        self.assertLess(value["localRemainingMs"], 0)
        self.assertFalse(value["diagnosticComplete"])

    def test_corrupt_progress_and_helper_baseexception_cannot_replace_original_initial_failure(self):
        for mode in ("corrupt-progress", "helper-baseexception"):
            with self.subTest(mode=mode):
                anchor = self.new_window(active=True)
                self.locals = iter((300.0,))
                if mode == "corrupt-progress":
                    D.native._CUSTODY_PROGRESS = object()
                with patch.object(D.native, "_custody_progress_window", wraps=D.native._custody_progress_window,
                        side_effect=KeyboardInterrupt() if mode == "helper-baseexception" else None) as note:
                    with self.assertRaisesRegex(ValueError, "WINDOW_DEADLINE_LOCAL") as caught:
                        self.window.deadline(5)
                    self.assertEqual(note.call_count, 1)
                    self.assertIs(note.call_args.kwargs["error"], caught.exception)
                    self.sticky(caught.exception)
                    self.assertEqual(note.call_count, 1)
                self.assertEqual(self.trace, [("LOCAL",)])
                self.assertEqual((anchor.last, anchor.local_last), (1000 * NS, 100.0))
                self.assertEqual(self.cpu_calls, 1)
                self.assertIsNone(self.record(caught.exception))

    def test_other_deadline_failures_never_fabricate_an_initial_local_failure_record(self):
        for mode in ("maximum", "stage", "unsampled-local", "conversion"):
            with self.subTest(mode=mode):
                anchor = self.new_window(active=True)
                self.locals, self.raws = iter((100.0, 101.0, 102.0, 103.0)), iter((1000 * NS + 1, 1000 * NS + 2))
                supplied = PrivateFailure() if mode in ("unsampled-local", "conversion") else None
                self.local_fault = supplied if mode == "unsampled-local" else None
                with ExitStack() as patches:
                    note = patches.enter_context(patch.object(D.native, "_custody_progress_window",
                        wraps=D.native._custody_progress_window))
                    if mode == "conversion":
                        patches.enter_context(patch.object(D.O.wire, "_directed_deadline", side_effect=supplied))
                    with self.assertRaises(PrivateFailure if supplied is not None else ValueError) as caught:
                        self.window.deadline(0 if mode == "maximum" else 5,
                            **({"stage": "NOT_A_STAGE"} if mode == "stage" else {}))
                    if supplied is not None:
                        self.assertIs(caught.exception, supplied)
                    self.assertEqual(note.call_count, 1 if mode == "conversion" else 0)
                    for call in note.call_args_list:
                        self.assertNotIn("error", call.kwargs)
                    self.assertIs(D.native._CUSTODY_PROGRESS["window_failure"], False)
                    # Model the outer failure freeze, without constructing an owner.
                    D.native._custody_progress_failure(caught.exception)
                    self.sticky(caught.exception)
                self.assertEqual(sum(row[0] == "LOCAL" for row in self.trace),
                    4 if mode == "conversion" else 1 if mode == "unsampled-local" else 0)
                self.assertEqual(sum(row[0] == "RAW" for row in self.trace), 2 if mode == "conversion" else 0)
                self.assertEqual(sum(row[0] == "BOOT" for row in self.trace), 1 if mode == "conversion" else 0)
                self.assertEqual(sum(row[0] == "CANCEL" for row in self.trace), 1 if mode == "conversion" else 0)
                self.assertEqual((anchor.last, anchor.local_last),
                    (1000 * NS + 2, 103.0) if mode == "conversion" else (1000 * NS, 100.0))
                value = self.record(caught.exception)
                self.assertIsNotNone(value)
                self.assertEqual(value["reason"], "OTHER")
                for name in ("windowLocalMs", "localRemainingMs", "rawRemainingMs"):
                    self.assertIsNone(value[name])
                self.assertFalse(value["diagnosticComplete"])


if __name__ == "__main__":
    unittest.main(failfast=True)
