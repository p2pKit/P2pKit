#!/usr/bin/env python3
"""Authored-only B0 DATA codec and source-shape controls; no native execution.

No old tests/fixtures or custody module are imported. The custody source is
parsed as AST, not executed. No real/fake seal, owner, clock observation,
output file, current authority or workflow is constructed. Source assertions
are not runtime coverage of the original seal/fence or provider qualification.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
import ctypes
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("SEAL_DEADLINE_DATA_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_continuity as C

CONTINUITY = ast.parse((ROOT / "scripts/hosted_initial_recipient_continuity.py").read_text(encoding="utf-8"))
CUSTODY = ast.parse((ROOT / "scripts/run-hosted-initial-recipient-custody.py").read_text(encoding="utf-8"))
FIELDS = frozenset(("initialSealSha256", "initialSealEndNs", "initialSealClockRole", "initialSealClockDomain",
    "initialSealClockTicksPerSecond", "initialSealBootSha256"))
DOMAINS = {"linux-x64": "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-x64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-arm64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "windows-x64": "windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns"}
NS, UINT64, INT64 = 1_000_000_000, (1 << 64) - 1, (1 << 63) - 1


def values(role="linux-x64", *, end=385_000_000_000, frequency=None):
    return {"initialSealSha256": "a" * 64, "initialSealEndNs": str(end), "initialSealClockRole": role,
        "initialSealClockDomain": DOMAINS[role], "initialSealClockTicksPerSecond":
            str((7_000_003 if role == "windows-x64" else NS) if frequency is None else frequency),
        "initialSealBootSha256": "b" * 64}


def guarded(function, *args):
    global GUARDED
    previous, GUARDED = GUARDED, True
    try:
        return function(*args)
    finally:
        GUARDED = previous


def shape(node):
    return ast.dump(node, include_attributes=False)


def function(tree, name, owner=None):
    body = tree.body
    if owner is not None:
        matches = [node for node in body if isinstance(node, ast.ClassDef) and node.name == owner]
        if len(matches) != 1:
            raise AssertionError("EXACT_SOURCE_CLASS")
        body = matches[0].body
    matches = [node for node in body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError("EXACT_SOURCE_FUNCTION")
    return matches[0]


def calls(node, name):
    return sorted((item for item in ast.walk(node) if isinstance(item, ast.Call) and
        ast.unparse(item.func) == name), key=lambda item: (item.lineno, item.col_offset))


class CodecDataControls(unittest.TestCase):
    """Twelve pure DATA controls, not native or successful-Step observations."""

    def reject(self, data):
        for operation in (C.seal_deadline_data, C._output_bytes):
            with self.subTest(operation=operation.__name__), self.assertRaises(C.ContinuityError):
                guarded(operation, data)

    def test_exact_four_role_codec(self):
        self.assertEqual(C.SEAL_DEADLINE_FIELDS, FIELDS)
        self.assertEqual(C.SEAL_DEADLINE_LIMIT, 512)
        self.assertEqual(C.clocks.DOMAINS, DOMAINS)
        for role in DOMAINS:
            with self.subTest(role=role):
                data = values(role)
                before = data.copy()
                seal_hash, end, identity, boot_hash = guarded(C.seal_deadline_data, data)
                self.assertEqual((seal_hash, end, boot_hash), ("a" * 64, 385_000_000_000, "b" * 64))
                self.assertIs(type(identity), C.clocks.ClockIdentity)
                self.assertEqual((identity.role, identity.domain, identity.ticks_per_second),
                    (role, DOMAINS[role], 7_000_003 if role == "windows-x64" else NS))
                raw = guarded(C._output_bytes, data)
                self.assertEqual(raw, "".join(key + "=" + data[key] + "\n" for key in sorted(FIELDS)).encode("ascii"))
                self.assertEqual(len(raw.splitlines()), 6)
                self.assertLessEqual(len(raw), 512)
                self.assertEqual(data, before)

    def test_uint64_and_actual_qpc_frequency_boundaries(self):
        for end in (1, UINT64):
            for frequency in (1, 7_000_003, NS, INT64):
                with self.subTest(end=end, frequency=frequency):
                    data = values("windows-x64", end=end, frequency=frequency)
                    decoded = guarded(C.seal_deadline_data, data)
                    self.assertEqual((decoded[1], decoded[2].ticks_per_second), (end, frequency))
                    self.assertIn(("initialSealClockTicksPerSecond=" + str(frequency) + "\n").encode("ascii"),
                        guarded(C._output_bytes, data))

    def test_end_decimal_aliases_and_overflow_rejected(self):
        for text in ("", "0", "00", "01", "+1", "-1", "1.0", "1e3", " 1", "1 ", "1\n", "1\r", "1\0",
                "١", "１", str(UINT64 + 1), "9" * 21, "9" * 513):
            with self.subTest(text=text):
                self.reject({**values(), "initialSealEndNs": text})

    def test_frequency_decimal_aliases_and_overflow_rejected(self):
        for text in ("", "0", "00", "01", "+1", "-1", "1.0", "1e9", " 1", "1 ", "1\n", "1\t", "１",
                str(INT64 + 1), str(UINT64), "9" * 21, "9" * 513):
            with self.subTest(text=text):
                self.reject({**values("windows-x64"), "initialSealClockTicksPerSecond": text})

    def test_exact_key_set_no_partial_extra_or_legacy_mix(self):
        for name in FIELDS:
            data = values()
            data.pop(name)
            with self.subTest(missing=name):
                self.reject(data)
        for extra in ("originalBootId", "sealEndNs", "initialExporterReturnSha256", "recipientStepSha256", "token"):
            with self.subTest(extra=extra):
                self.reject({**values(), extra: "c" * 64})
        self.reject({name.lower(): value for name, value in values().items()})

    def test_exact_types_no_subclass_aliases(self):
        class String(str):
            pass
        class Dictionary(dict):
            pass
        for data in (None, False, [], tuple(values().items()), Dictionary(values())):
            with self.subTest(container=type(data).__name__):
                self.reject(data)
        self.reject({String(name): original for name, original in values().items()})
        for name, original in values().items():
            for replacement in (None, True, 1, 1.0, original.encode("ascii"), String(original), [original]):
                with self.subTest(name=name, replacement=type(replacement).__name__):
                    self.reject({**values(), name: replacement})

    def test_lowercase_hash_grammar(self):
        for name in ("initialSealSha256", "initialSealBootSha256"):
            for text in ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64, "a" * 64 + "\n", " " + "a" * 64,
                    "a" * 32 + "/" + "a" * 31, "é" * 64):
                with self.subTest(name=name, text=text):
                    self.reject({**values(), name: text})

    def test_role_domain_and_posix_frequency(self):
        for role in DOMAINS:
            for domain in (*set(DOMAINS.values()), "", "CLOCK_MONOTONIC", "arbitrary-clock", DOMAINS[role] + "\n"):
                if domain != DOMAINS[role]:
                    with self.subTest(role=role, domain=domain):
                        self.reject({**values(role), "initialSealClockDomain": domain})
            if role != "windows-x64":
                for frequency in (1, 7_000_003, NS - 1, NS + 1, INT64):
                    with self.subTest(role=role, frequency=frequency):
                        self.reject(values(role, frequency=frequency))
        for role in ("", "Linux-X64", "macos", "windows-arm64", "linux-x64\n"):
            self.reject({**values(), "initialSealClockRole": role})

    def test_legacy_closed_hash_sets_keep_exact_bytes(self):
        groups = (("recipientSenderSha256", "recipientStepSha256"),
            ("recipientSenderSha256", "recipientStepSha256", "recipientCryptoOriginalsSha256"),
            ("initializationSha256",), ("initializationSha256", "workerHandoffSha256"),
            ("initialOriginalsSha256", "gateHandoffSha256"), ("initialCryptoStepSha256", "initialExporterReturnSha256"),
            ("initialCustodySha256", "initialExporterReturnSha256"), ("initialSealSha256",))
        for names in groups:
            data = {name: str(index) * 64 for index, name in enumerate(names)}
            with self.subTest(names=names):
                self.assertEqual(guarded(C._output_bytes, data),
                    "".join(name + "=" + data[name] + "\n" for name in sorted(names)).encode("ascii"))
        self.assertEqual(guarded(C._output_bytes, {"initialSealSha256": "a" * 64}),
            b"initialSealSha256=" + b"a" * 64 + b"\n")

    def test_no_arbitrary_string_output_branch(self):
        for data in ({}, {"anything": "a" * 64}, {"initialSealEndNs": "123"}, {"initialSealSha256": "123"},
                {"initialSealSha256": "a" * 64, "initialSealEndNs": "123"},
                {"initialSealSha256": "a" * 64, "initialExporterReturnSha256": "b" * 64},
                {"initializationSha256": "a" * 64 + "\n"}):
            with self.subTest(names=tuple(data)), self.assertRaises(C.ContinuityError):
                guarded(C._output_bytes, data)

    def test_valid_changed_data_is_not_authority(self):
        original = values()
        encoded = guarded(C._output_bytes, original)
        for name, replacement in (("initialSealSha256", "c" * 64), ("initialSealBootSha256", "d" * 64),
                ("initialSealEndNs", "385000000001")):
            with self.subTest(name=name):
                changed = {**original, name: replacement}
                # Syntactically valid declarations are allowed as DATA. Only
                # the real seal registry/Step/BEFORE authority can authenticate.
                self.assertNotEqual(guarded(C._output_bytes, changed), encoded)
                self.assertIs(type(guarded(C.seal_deadline_data, changed)), tuple)

    def test_codec_never_observes_or_does_io(self):
        def forbidden(*_args, **_kwargs):
            raise AssertionError("PURE_DATA_MUST_NOT_OBSERVE")
        with ExitStack() as stack:
            for owner, name in ((C, "boot_digest"), (C.clocks, "observe"), (C.clocks, "checked_now"),
                    (C.clocks, "local_deadline"), (C.clocks.processes, "host_role"), (C.os, "open")):
                stack.enter_context(patch.object(owner, name, forbidden))
            for role in DOMAINS:
                guarded(C.seal_deadline_data, values(role))
                guarded(C._output_bytes, values(role))


class SourceBindingControls(unittest.TestCase):
    """Seven AST assertions only; never construct a stand-in native seal."""

    def has(self, node, expression):
        expected = shape(ast.parse(expression, mode="eval").body)
        self.assertTrue(any(shape(item) == expected for item in ast.walk(node)), expression)

    def method(self, name):
        return function(CUSTODY, name, "_TailOutputFence")

    def test_original_live_return_is_mandatory(self):
        checked = function(CUSTODY, "_checked_tail_seal")
        self.has(checked, 'type(result) is _TailSeal and type(saved) is tuple and saved[0] is result')
        self.has(checked, 'result.__dict__ is dictionary')
        self.has(checked, 'metadata.owner.closed')
        self.has(checked, 'not metadata.owner.unknown')
        self.has(checked, '(clock, clock.work, {"initialSealSha256": O.digest(raw)})')
        fresh = function(CUSTODY, "_tail_output_values")
        self.assertEqual(len(calls(fresh, "_checked_tail_seal")), 1)
        self.has(fresh, 'type(for_before) is bool')
        allowed = {"require", "type", "_checked_tail_seal", "canonical", "_custody_authority_frame", "_same", "str",
            "C.seal_deadline_data"}
        self.assertTrue(all(ast.unparse(item.func) in allowed for item in ast.walk(fresh) if isinstance(item, ast.Call)))

    def test_handoff_uses_original_window_but_keeps_limit(self):
        fresh = function(CUSTODY, "_tail_output_values")
        self.has(fresh, 'canonical(result.raw)["originalWindow"]')
        self.has(fresh, '_same(frame, clock.frame, "TAIL_OUTPUT_ORIGINAL_WINDOW")')
        self.has(fresh, '{"initialSealSha256": values["initialSealSha256"], '
            '"initialSealEndNs": str(frame["sealEndNs"]), "initialSealClockRole": declared.role, '
            '"initialSealClockDomain": declared.domain, "initialSealClockTicksPerSecond": '
            'str(declared.ticks_per_second), "initialSealBootSha256": frame["originalBootDigest"]}')
        self.has(fresh, '(clock, limit, values)')
        self.assertEqual(len(calls(fresh, "C.seal_deadline_data")), 1)

    def test_mode_appended_no_legacy_index_shift_and_crossmode_once(self):
        constructor = self.method("__init__")
        self.assertEqual([arg.arg for arg in constructor.args.kwonlyargs], ["for_before"])
        self.assertIs(constructor.args.kw_defaults[0].value, False)
        self.has(constructor, 'not any(saved[1][0] is result for saved in _TAIL_OUTPUTS.values())')
        self.has(constructor, '{"forBefore": for_before}')
        assignments = [item for item in ast.walk(constructor) if isinstance(item, ast.Assign) and
            any(ast.unparse(target) == "self._binding" for target in item.targets)]
        self.assertEqual(len(assignments), 1)
        self.assertEqual([ast.unparse(item) for item in assignments[0].value.elts[:7]],
            ["result", "returned", "result.__dict__", "clock", "limit", "values", "value"])
        self.assertEqual(len(assignments[0].value.elts), 9)
        self.assertEqual(ast.unparse(assignments[0].value.elts[7]), "N._history_graph(values, value, mode)")
        self.assertEqual(ast.unparse(assignments[0].value.elts[8]), "mode")

    def test_current_rechecks_mode_graph_same_seal(self):
        current = self.method("_current")
        graphs, check = calls(current, "N._check_history"), calls(current, "_tail_output_values")
        self.assertEqual((len(graphs), len(check)), (2, 1))
        self.assertLess(graphs[0].lineno, check[0].lineno)
        self.assertLess(check[0].lineno, graphs[1].lineno)
        self.has(current, '_tail_output_values(result, for_before=mode["forBefore"])')
        self.has(current, 'current[0] is clock and type(current[1]) is int and current[1] == limit and current[2] == values')
        self.has(current, '_TAIL_SEALS.get(id(result)) is returned')
        self.has(current, 'result.__dict__ is dictionary')

    def test_one_append_failure_latch_and_exact_two_late_checks(self):
        appended, guard, late, failed = (self.method(name) for name in ("append", "_append_guard", "now", "_fail"))
        self.assertEqual(len(calls(appended, "C.append_outputs")), 1)
        self.has(appended, 'C.append_outputs(values, self._append_guard)')
        self.has(appended, 'saved[2]["phase"] == "NEW" and saved[2]["checks"] == 0')
        self.has(guard, 'clock.now(final=True, limit=limit)')
        self.has(late, '0 <= saved[2]["checks"] < 2')
        self.has(late, 'type(minimum) is int')
        self.has(late, 'minimum == 0')
        self.has(late, 'limit == saved[1][4]')
        self.has(late, 'clock.now(final=True, limit=original_limit)')
        self.has(failed, 'saved[2]["failure"] is None')
        self.assertEqual(len(calls(late, "self._current")), 2)

    def test_one_fixed_seal_episode_and_distinct_cli(self):
        for name, selected in (("seal", False), ("seal_for_before", True)):
            wrapper = function(CUSTODY, name)
            self.assertEqual(len(calls(wrapper, "_seal")), 1)
            self.has(wrapper, "_seal(kind, cancelled, for_before=" + str(selected) + ")")
        episode = function(CUSTODY, "_seal")
        for name in ("_tail_begin", "_tail_pre_metadata", "_retain_tail_seal", "_TailOutputFence"):
            self.assertEqual(len(calls(episode, name)), 1)
        self.has(episode, '_tail_begin("seal-entry")')
        self.has(episode, '_TailOutputFence(result, for_before=for_before).append()')
        main = function(CUSTODY, "main")
        self.has(main, '("collect-export", "collect-close", "seal", "seal-for-before")')
        self.has(main, '{"collect-export": collect_export, "collect-close": collect_close, '
            '"seal": seal, "seal-for-before": seal_for_before}')
        flags = [item.args[0].value for item in calls(main, "entry.add_argument")]
        self.assertEqual(flags, ["--kind"])

    def test_file_writer_still_one_write_fsync_readback_close(self):
        writer = function(CONTINUITY, "append_outputs")
        order = []
        for name in ("os.open", "os.write", "os.fsync", "os.lseek", "os.read", "os.close"):
            found = calls(writer, name)
            self.assertEqual(len(found), 1, name)
            order.append((found[0].lineno, found[0].col_offset))
        self.assertEqual(order, sorted(order))
        self.has(writer, 'before.st_size == 0')
        self.has(writer, 'os.write(descriptor, raw) == len(raw)')
        self.has(writer, 'os.read(descriptor, len(raw) + 1) == raw')
        self.assertGreater(calls(writer, "check")[-1].lineno, calls(writer, "os.close")[0].lineno)
        self.assertEqual(len(calls(writer, "_output_bytes")), 1)


if __name__ == "__main__":
    unittest.main()
