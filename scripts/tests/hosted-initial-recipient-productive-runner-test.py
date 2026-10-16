#!/usr/bin/env python3
"""Strict final argv models; no child launch, hosted identity or clock observation."""
from __future__ import annotations

import ctypes
from contextlib import ExitStack, redirect_stderr
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise AssertionError("PRODUCTIVE_RUNNER_MODEL_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive as P
import hosted_initial_recipient_productive_custody as PC
import hosted_initial_recipient_productive_custody_data as CD

SPEC = importlib.util.spec_from_file_location("productive_runner_controls", ROOT / "scripts/run-hosted-initial-recipient-productive.py")
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class FinalArgvModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.calls = []
        self.stack.enter_context(patch.object(PC, "productive_authority_pre_child", self.pre))
        self.stack.enter_context(patch.object(PC, "productive_authority_post_child", self.post))
        self.stack.enter_context(patch.object(PC, "productive_crypto_child", self.crypto))
        self.stack.enter_context(patch.object(P.B, "guarded", lambda function: function([])))
        self.stack.enter_context(patch.object(P.O.clocks, "observe", side_effect=AssertionError("NO_OBSERVED_CLOCK")))

    def pre(self, *args):
        self.calls.append(("_final-authority-pre", args))
        return "MODEL_ONLY"

    def post(self, *args):
        self.calls.append(("_final-authority-post", args))
        return "MODEL_ONLY"

    def crypto(self, *args):
        self.calls.append(("_final-crypto", args))
        return "MODEL_ONLY"

    def argv(self, operation="_final-crypto"):
        flags = CD.FINAL_CRYPTO_CAP_FLAGS if operation == "_final-crypto" else CD.FINAL_AUTHORITY_CAP_FLAGS
        result = [operation, "--context-sha256", "a" * 64, "--minimum-ns", "10"]
        for index, name in enumerate(flags, 100):
            result += [name, str(index)]
        return result + ["--original-boot-digest", "b" * 64, "--clock-role", "linux-x64",
            "--clock-domain", P.O.clocks.DOMAINS["linux-x64"], "--clock-ticks-per-second", str(P.O.NS)]

    def refuses(self, argv):
        before = len(self.calls)
        with redirect_stderr(io.StringIO()), self.assertRaises((Exception, SystemExit)):
            R._final_child(argv)
        self.assertEqual(len(self.calls), before)

    def test_three_fixed_routes_pass_exact_ordered_caps_and_declared_clock(self):
        for operation in ("_final-authority-pre", "_final-authority-post", "_final-crypto"):
            self.assertEqual(R._final_child(self.argv(operation)), "MODEL_ONLY")
            actual, args = self.calls[-1]
            self.assertEqual(actual, operation)
            self.assertEqual(len(args), 6)
            self.assertEqual(args[:2], ("a" * 64, 10))
            self.assertEqual(args[2], tuple(range(100, 107 if operation == "_final-crypto" else 106)))
            self.assertIs(type(args[3]), P.O.clocks.ClockIdentity)
            self.assertEqual(args[4], "b" * 64)
            self.assertTrue(callable(args[5]))

    def test_reordered_duplicate_extra_or_abbreviated_flags_refuse(self):
        good = self.argv()
        reordered = good[:1] + good[3:5] + good[1:3] + good[5:]
        abbreviated = list(good)
        abbreviated[1] = "--context-sha"
        for value in (reordered, good + ["--minimum-ns", "10"], good + ["--scope", "anything"], abbreviated):
            self.refuses(value)

    def test_equals_spelling_is_not_canonical(self):
        good = self.argv()
        self.refuses([good[0], good[1] + "=" + good[2], *good[3:]])

    def test_prelaunch_without_actual_minimum_is_not_executable(self):
        good = self.argv()
        self.refuses(good[:3] + good[5:])

    def test_original_boot_digest_is_mandatory_and_exact(self):
        good = self.argv()
        index = good.index("--original-boot-digest")
        self.refuses(good[:index] + good[index + 2:])
        for value in ("B" * 64, "b" * 63, " " + "b" * 64):
            changed = list(good)
            changed[index + 1] = value
            self.refuses(changed)

    def test_all_cap_minimum_and_frequency_values_use_uint64_decimal(self):
        good = self.argv()
        for flag in ("--minimum-ns", *CD.FINAL_CRYPTO_CAP_FLAGS, "--clock-ticks-per-second"):
            for value in ("01", "-1", "+1", "1.0", "true", str(2 ** 64)):
                changed = list(good)
                changed[changed.index(flag) + 1] = value
                self.refuses(changed)

    def test_wrong_role_domain_or_frequency_refuses(self):
        for flag, value in (("--clock-role", "windows-arm64"), ("--clock-domain", "made-up"),
                ("--clock-ticks-per-second", "1")):
            changed = self.argv()
            changed[changed.index(flag) + 1] = value
            self.refuses(changed)

    def test_no_generic_route_or_cap_selector(self):
        good = self.argv()
        for operation in ("_final-authority", "_private-use", "_final-Crypto", "_service", "help"):
            self.refuses([operation, *good[1:]])


if __name__ == "__main__":
    unittest.main(failfast=True)
