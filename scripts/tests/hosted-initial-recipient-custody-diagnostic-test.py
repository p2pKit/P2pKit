#!/usr/bin/env python3
"""Tiny offline failure-site controls, NOT Stage1/native/custody qualification.

Import the original custody controller after stdlib initialization and the
persistent offline fence. No previous test/fixture is imported. Original pure
require failures supply source frames; explicitly supplied traceback links test
limits and malformed metadata. Main's guard and selected operation are supplied
in-memory seams: no authority, reader, acquisition, clock, process or crypto runs.
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
    def invoke(self, operation="collect-export", kind="gate", *, failure=None, guard_failure=False, stderr=None):
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
                        patch.object(D, "_failure_sites", side_effect=AssertionError("unexpected diagnostic")) as sites:
                    self.assertEqual(self.invoke(operation, kind), (0, "", ""))
                    if operation != "collect-export":
                        self.assertEqual(self.invoke(operation, kind, failure=PrivateFailure()), (125, "", REFUSAL))
                    sites.assert_not_called()

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


if __name__ == "__main__":
    unittest.main(failfast=True)
