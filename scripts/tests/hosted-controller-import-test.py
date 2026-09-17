#!/usr/bin/env python3
"""Cold source-import and lazy-reader models; not native Windows qualification.

Run in a fresh isolated interpreter. No product/native entrypoint, clock query,
network connection or child is allowed. Removing APIs models their absence only.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
import ctypes
import http.client
import importlib.util
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ImportModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        # Each case restores the complete module map, so a preceding case cannot
        # accidentally turn this cold graph regression into a warm-import pass.
        self.stack.enter_context(patch.dict(sys.modules))
        for name in ("hosted_full_job_budget", "hosted_full_supplements", "hosted_lock_resources"):
            self.assertNotIn(name, sys.modules, "run this test in a fresh interpreter")
        for module, names in (
            (ctypes, ("CDLL", "PyDLL", "WinDLL")),
            (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
            (os, ("system", "popen", "fork", "posix_spawn", "posix_spawnp")),
            (socket, ("socket", "create_connection", "getaddrinfo")),
            (http.client, ("HTTPConnection", "HTTPSConnection")),
            (ssl, ("create_default_context",)),
            (time, ("clock_gettime_ns", "time", "monotonic", "perf_counter")),
        ):
            for name in names:
                self.stack.enter_context(patch.object(module, name,
                    side_effect=AssertionError("unmodeled native/network/child/clock call"), create=True))

    def test_cold_actual_controller_graph_needs_no_unix_api(self):
        self.assertEqual((sys.flags.isolated, sys.flags.no_site, sys.dont_write_bytecode), (1, 1, True))
        with patch.dict(os.__dict__), patch.dict(time.__dict__):
            for name in ("statvfs", "getuid", "geteuid", "getgid", "getegid", "fork", "killpg"):
                os.__dict__.pop(name, None)
            for name in ("clock_gettime_ns", "CLOCK_MONOTONIC_RAW"):
                time.__dict__.pop(name, None)
            controller = load("cold_ordinary_controller", SCRIPTS / "run-hosted-test-custody.py")
        budget = sys.modules["hosted_full_job_budget"]
        self.assertEqual(Path(budget.__file__), SCRIPTS / "hosted_full_job_budget.py")
        self.assertIs(controller.job_time, budget)
        self.assertIs(controller.supplements.job_time, budget)
        self.assertNotIn("hosted_lock_resources", sys.modules)
        self.assertNotIn("hosted_job_clock", sys.modules)

    def test_domain_matches_unchanged_original_supplier(self):
        tree = ast.parse((SCRIPTS / "hosted_lock_resources.py").read_bytes())
        values = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "RAW_CLOCK_DOMAIN" for target in node.targets)]
        self.assertEqual(values, [DOMAIN])
        budget = load("tested_job_budget", SCRIPTS / "hosted_full_job_budget.py")
        self.assertEqual(budget.RAW_CLOCK_DOMAIN, DOMAIN)
        self.assertNotIn("hosted_lock_resources", sys.modules)

    def test_lazy_reader_preserves_integer_and_original_exception(self):
        budget = load("tested_job_budget", SCRIPTS / "hosted_full_job_budget.py")
        value = (1 << 63) + 17
        reader = Mock(return_value=value)
        original = RuntimeError("synthetic original supplier refusal")
        with patch.dict(sys.modules, {"hosted_lock_resources": SimpleNamespace(
                RAW_CLOCK_DOMAIN=DOMAIN, shared_raw_ns=reader)}):
            reader.assert_not_called()
            self.assertIs(budget.shared_raw_ns(), value)
            reader.assert_called_once_with()
            reader.side_effect = original
            with self.assertRaises(RuntimeError) as caught:
                budget.shared_raw_ns()
            self.assertIs(caught.exception, original)
            self.assertEqual(reader.call_count, 2)

    def test_changed_supplier_domain_refuses_without_reading(self):
        budget = load("tested_job_budget", SCRIPTS / "hosted_full_job_budget.py")
        reader = Mock(side_effect=AssertionError("changed supplier must not be read"))
        with patch.dict(sys.modules, {"hosted_lock_resources": SimpleNamespace(
                RAW_CLOCK_DOMAIN="foreign-or-changed-domain", shared_raw_ns=reader)}):
            with self.assertRaisesRegex(budget.BudgetError, "JOB_TIME_RAW_DOMAIN"):
                budget.shared_raw_ns()
            reader.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
