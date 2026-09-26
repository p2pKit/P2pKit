#!/usr/bin/env python3
"""Authored B1-successor controls, not native BEFORE or hosted qualification.

Thirty-five DATA controls, eleven real in-memory latch controls and fourteen
AST assertions. No old suites/fixtures, operative custody/native imports, fake
owners, HTTP responses, native clocks, outputs, keys or provider processes run.
Latch controls use the small production state machine, not an operative B owner.
"""
from __future__ import annotations

import ast
import copy
import ctypes
import _strptime  # Preload datetime's lazy DATA parser before the no-file guard.
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("BEFORE_DATA_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_before as B

C = B.continuity
CUSTODY = ast.parse((ROOT / "scripts/run-hosted-initial-recipient-custody.py").read_text(encoding="utf-8"))
NATIVE = ast.parse((ROOT / "scripts/run-hosted-cache-bootstrap.py").read_text(encoding="utf-8"))
PRIMARY = ast.parse((ROOT / "scripts/run-hosted-initial-recipient.py").read_text(encoding="utf-8"))
NS = 1_000_000_000
DATE = B.wire.utc_epoch("2026-09-26T00:00:09Z")
ERRORS = (B.BeforeError, B.clocks.ClockError, C.ContinuityError, B.wire.BudgetError)


def seed(role="linux-x64"):
    return {"initialSealSha256": "a" * 64, "initialSealEndNs": str(385 * NS), "initialSealClockRole": role,
        "initialSealClockDomain": B.clocks.DOMAINS[role],
        "initialSealClockTicksPerSecond": str(7_000_003 if role == "windows-x64" else NS),
        "initialSealBootSha256": "b" * 64}


def reading(value, nanoseconds):
    return B.clocks.Reading(B.clocks.ClockIdentity(value["initialSealClockRole"], value["initialSealClockDomain"],
        int(value["initialSealClockTicksPerSecond"])), nanoseconds)


def step(name, number, *, status="completed", conclusion="success", start="00", end="01"):
    stamp = lambda value: None if value is None else "2026-09-26T00:00:" + value + "Z"
    return {"name": name, "number": number, "status": status, "conclusion": conclusion,
        "started_at": stamp(start), "completed_at": stamp(end)}


def job():
    names = dict(B.STEP_NAMES)
    return {"started_at": "2026-09-26T00:00:00Z", "steps": [step("Set up job", 1),
        step("Unused conditional source", 2, conclusion="skipped", start=None, end=None),
        step(names["export"], 3, start="02", end="03"), step(names["collect"], 4, start="03", end="04"),
        step(names["seal"], 6, start="04", end="05"),
        step(names["before"], 7, status="in_progress", conclusion=None, start="05", end=None),
        step("Future transport", 10, status="queued", conclusion=None, start=None, end=None)]}


def ids():
    return tuple(tuple(f"{value:032x}" for value in range(begin, end))
        for begin, end in ((1, 13), (13, 37), (37, 49)))


def file_metadata(role):
    if role == "windows-x64":
        return {"identity": [7, "c" * 32], "is_directory": False, "size": 11, "links": 1,
            "attributes": 128, "creation_100ns": 111, "modified_100ns": 222, "change_100ns": 333,
            "owner_sid": "S-1-5-21-123-456-789-1000", "protected_dacl": True}
    return {"device": 7, "inode": 19, "size": 11, "mtime_ns": 222, "ctime_ns": 333}


def guarded(function, *args, **kwargs):
    global GUARDED
    previous, GUARDED = GUARDED, True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = previous


def function(tree, name, owner=None):
    body = tree.body
    if owner is not None:
        classes = [node for node in body if isinstance(node, ast.ClassDef) and node.name == owner]
        if len(classes) != 1:
            raise AssertionError("BEFORE_EXACT_CLASS")
        body = classes[0].body
    matches = [node for node in body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError("BEFORE_EXACT_FUNCTION")
    return matches[0]


def calls(node, name):
    return sorted((value for value in ast.walk(node) if isinstance(value, ast.Call) and
        ast.unparse(value.func) == name), key=lambda value: (value.lineno, value.col_offset))


class BeforeDataControls(unittest.TestCase):
    """28 supplied-DATA controls. None constructs an operative B capability."""

    def reject(self, function, *args, **kwargs):
        with self.assertRaises(ERRORS):
            guarded(function, *args, **kwargs)

    def test_original_parent_end_all_four_roles(self):
        for role in B.clocks.DOMAINS:
            value = seed(role)
            self.assertEqual(guarded(B.first_caps, value, reading(value, 100 * NS), "b" * 64), (385 * NS, 385 * NS))

    def test_inherited_phase_has_no_child_first_renewal(self):
        value, caps = seed(), (300 * NS, 345 * NS, 385 * NS)
        for first in (300 * NS, 340 * NS, 345 * NS - 1):
            self.assertEqual(guarded(B.first_caps, value, reading(value, first), "b" * 64, inherited=caps), caps[1:])

    def test_parent_first_at_or_after_original_end(self):
        value = seed()
        for first in (385 * NS, 386 * NS, B.clocks.UINT64):
            self.reject(B.first_caps, value, reading(value, first), "b" * 64)

    def test_first_identity_and_boot_substitutions(self):
        value = seed("windows-x64")
        wrong = B.clocks.Reading(B.clocks.ClockIdentity("windows-x64", B.clocks.WINDOWS_DOMAIN, 7_000_004), 300 * NS)
        for actual, boot in ((wrong, "b" * 64), (reading(seed(), 300 * NS), "b" * 64),
                (reading(value, 300 * NS), "c" * 64), (reading(value, 300 * NS), None)):
            self.reject(B.first_caps, value, actual, boot)

    def test_phase_tuple_exact_shape_and_integer_types(self):
        for caps in (None, [], [300 * NS, 345 * NS, 385 * NS], (300 * NS, 345 * NS),
                (300 * NS, 345 * NS, 385 * NS, 385 * NS), (True, 345 * NS, 385 * NS),
                (300 * NS, 345.0 * NS, 385 * NS), (300 * NS, 345 * NS, str(385 * NS))):
            self.reject(B.phase_caps, seed(), caps)

    def test_phase_caps_exact_original_min_formulas(self):
        for caps in ((299 * NS, 345 * NS, 385 * NS), (300 * NS, 344 * NS, 385 * NS),
                (300 * NS, 345 * NS, 384 * NS), (300 * NS, 345 * NS, 386 * NS),
                (385 * NS, 385 * NS, 385 * NS), (0, 45 * NS, 90 * NS)):
            self.reject(B.phase_caps, seed(), caps)
        self.assertEqual(guarded(B.phase_caps, seed(), (380 * NS, 385 * NS, 385 * NS)), (380 * NS, 385 * NS, 385 * NS))

    def test_child_first_must_follow_phase_and_precede_work(self):
        value, caps = seed(), (300 * NS, 345 * NS, 385 * NS)
        for first in (299 * NS, 345 * NS, 350 * NS, 385 * NS):
            self.reject(B.first_caps, value, reading(value, first), "b" * 64, inherited=caps)

    def test_cli_phase_decimals_have_no_alternate_spellings(self):
        good = (str(300 * NS), str(345 * NS), str(385 * NS))
        self.assertEqual(guarded(B.decimal_caps, seed(), good), (300 * NS, 345 * NS, 385 * NS))
        for value in (None, 300 * NS, "0300000000000", "+300000000000", "300000000000 ", "3e11", "0", "-1",
                str(B.clocks.UINT64 + 1), "300000000000\n"):
            self.reject(B.decimal_caps, seed(), (value, *good[1:]))

    def test_data_codecs_do_not_mutate_inputs(self):
        value, selected = seed(), job()
        old_seed, old_job = copy.deepcopy(value), copy.deepcopy(selected)
        guarded(B.phase_caps, value, (300 * NS, 345 * NS, 385 * NS))
        guarded(B.first_caps, value, reading(value, 300 * NS), "b" * 64)
        guarded(B.step_rows, selected, DATE)
        self.assertEqual((value, selected), (old_seed, old_job))

    def test_exact_step_rows_and_nullable_skipped_history(self):
        result = guarded(B.step_rows, job(), DATE)
        self.assertEqual(tuple(role for role, _row in result), ("export", "collect", "seal", "before"))
        self.assertEqual(tuple(row["number"] for _role, row in result), (3, 4, 6, 7))
        self.assertEqual(result[-1][1]["status"], "in_progress")
        self.assertIsNone(result[-1][1]["conclusion"])

    def test_each_fixed_step_is_required(self):
        for _role, name in B.STEP_NAMES:
            value = job()
            value["steps"] = [row for row in value["steps"] if row["name"] != name]
            self.reject(B.step_rows, value, DATE)

    def test_each_prior_step_requires_actual_success(self):
        for number in (2, 3, 4):
            for conclusion in ("failure", "cancelled", "neutral", "skipped", None):
                value = job()
                value["steps"][number]["conclusion"] = conclusion
                self.reject(B.step_rows, value, DATE)

    def test_current_step_cannot_attest_its_success(self):
        for status, conclusion, completed in (("completed", "success", "2026-09-26T00:00:06Z"),
                ("queued", None, None), ("in_progress", "success", None), ("in_progress", None, "2026-09-26T00:00:06Z")):
            value = job()
            value["steps"][5].update(status=status, conclusion=conclusion, completed_at=completed)
            self.reject(B.step_rows, value, DATE)

    def test_named_predecessor_number_and_time_order(self):
        value = job()
        value["steps"][2]["name"], value["steps"][3]["name"] = value["steps"][3]["name"], value["steps"][2]["name"]
        self.reject(B.step_rows, value, DATE)
        value = job()
        value["steps"][4]["completed_at"] = "2026-09-26T00:00:06Z"
        self.reject(B.step_rows, value, DATE)

    def test_complete_step_schema_rejects_missing_and_extra_fields(self):
        for field in B.STEP_FIELDS:
            value = job()
            del value["steps"][0][field]
            self.reject(B.step_rows, value, DATE)
        value = job()
        value["steps"][0]["outcome"] = "success"
        self.reject(B.step_rows, value, DATE)

    def test_step_array_is_nonempty_finite_and_typed(self):
        for rows in (None, (), [], "steps", [None], job()["steps"] * 37):
            value = job()
            value["steps"] = rows
            self.reject(B.step_rows, value, DATE)

    def test_step_numbers_are_strict_unique_positive_integers(self):
        for number in (True, 0, -1, 1.0, "1", 2147483648):
            value = job()
            value["steps"][0]["number"] = number
            self.reject(B.step_rows, value, DATE)
        for number in (1, 2):
            value = job()
            value["steps"][2]["number"] = number
            self.reject(B.step_rows, value, DATE)

    def test_step_names_are_bounded_unique_and_control_free(self):
        for name in (None, "", "x" * 257, "set\nup", "set\x7fup", dict(B.STEP_NAMES)["seal"]):
            value = job()
            value["steps"][0]["name"] = name
            self.reject(B.step_rows, value, DATE)

    def test_unknown_service_status_or_conclusion_refuses(self):
        for field, replacement in (("status", "waiting"), ("status", 1), ("conclusion", "timedout"),
                ("conclusion", "stale"), ("conclusion", "startup_failure"), ("conclusion", True)):
            value = job()
            value["steps"][0][field] = replacement
            self.reject(B.step_rows, value, DATE)

    def test_step_timestamps_are_exact_original_second_utc(self):
        for stamp in (None, 1, "2026-09-26T00:00:00.000Z", "2026-09-26T00:00:00+00:00",
                "2026-02-30T00:00:00Z", "2026-09-26T00:00:00Z\n"):
            value = job()
            value["steps"][2]["started_at"] = stamp
            self.reject(B.step_rows, value, DATE)

    def test_steps_cannot_precede_job_or_follow_service_date(self):
        for stamp in ("2026-09-25T23:59:59Z", "2026-09-26T00:00:10Z"):
            value = job()
            value["steps"][0]["started_at"] = stamp
            self.reject(B.step_rows, value, DATE)
        for date in (True, DATE - 10, float(DATE), str(DATE), 0):
            self.reject(B.step_rows, job(), date)

    def test_stale_or_concurrent_step_frontier_refuses(self):
        value = job()
        value["steps"][0].update(status="queued", conclusion=None, started_at=None, completed_at=None)
        self.reject(B.step_rows, value, DATE)
        value = job()
        value["steps"][-1].update(status="in_progress", started_at="2026-09-26T00:00:06Z")
        self.reject(B.step_rows, value, DATE)

    def test_exact_280_files_and_58_directories(self):
        files, directories = guarded(B.member_grammar, *ids())
        self.assertEqual((len(files), len(directories)), (280, 58))
        self.assertEqual(sum(name.startswith("source-before/") for name in files), 67)
        self.assertEqual(sum(name.startswith("source-after/") for name in files), 67)
        self.assertEqual(sum(name.startswith("acquisition-queries/") for name in files), 137)
        self.assertIn("authority-close.json", files)

    def test_every_query_has_all_five_original_files(self):
        identifiers = ids()
        files, directories = guarded(B.member_grammar, *identifiers)
        for side, values in zip(("source-before", "acquisition-queries", "source-after"), identifiers):
            for identifier in values:
                root = side + "/query-" + identifier
                self.assertIn(root, directories)
                self.assertEqual({name.removeprefix(root + "/") for name in files if name.startswith(root + "/")},
                    {"start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"})

    def test_query_ids_cannot_be_missing_extra_or_aliased(self):
        a, b, c = ids()
        for first in (a[:-1], a + ("f" * 32,), [*a], (a[0], *a[:-1]), ("x" * 32, *a[1:])):
            self.reject(B.member_grammar, first, b, c)
        self.reject(B.member_grammar, a, (a[0], *b[1:]), c)

    def test_acquisition_42_cap_and_only_declared_close_addition(self):
        files, directories = guarded(B.member_grammar, *ids())
        before = dict(guarded(B.directory_members, files, directories, closed=False))
        after = dict(guarded(B.directory_members, files, directories, closed=True))
        self.assertEqual(len(before["acquisition-queries"]), 42)
        self.assertEqual(after["."], tuple(sorted((*before["."], "authority-close.json"))))
        self.assertEqual({key: value for key, value in before.items() if key != "."},
            {key: value for key, value in after.items() if key != "."})
        self.assertEqual(before["temporary"], ())

    def test_member_roster_rejects_escape_alias_or_missing_parent(self):
        files, directories = guarded(B.member_grammar, *ids())
        for bad in ("../stolen", "/absolute", "undeclared/file", files[1], None, {}, []):
            self.reject(B.directory_members, (bad, *files[1:]), directories, closed=False)
        self.reject(B.directory_members, files, (None, *directories[1:]), closed=False)
        self.reject(B.directory_members, files, directories, closed=1)

    def test_pure_helpers_do_not_consult_native_clocks_or_boot(self):
        with patch.object(B.clocks, "observe", side_effect=AssertionError("NO_NATIVE_CLOCK")), \
                patch.object(B.clocks, "checked_now", side_effect=AssertionError("NO_NATIVE_CLOCK")), \
                patch.object(C, "boot_digest", side_effect=AssertionError("NO_NATIVE_BOOT")):
            value = seed()
            self.assertEqual(guarded(B.first_caps, value, reading(value, 300 * NS), "b" * 64), (385 * NS, 385 * NS))
            self.assertEqual(len(guarded(B.step_rows, job(), DATE)), 4)
            self.assertEqual(len(guarded(B.member_grammar, *ids())[0]), 280)


class BeforeEntryLatchControls(unittest.TestCase):
    """Eleven actual in-memory latch controls; opaque results are NOT B records."""

    def opened(self):
        attempts = {}
        latch = guarded(B.EntryLatch, attempts)
        attempt = guarded(latch.begin, attempts)
        return latch, attempts, attempt

    def refused(self, function, *args):
        with self.assertRaises(B.BeforeError) as caught:
            guarded(function, *args)
        return caught.exception

    def test_one_original_attempt_and_exact_completed_result(self):
        latch, attempts, attempt = self.opened()
        result = object()
        self.assertIs(attempts["entry"], attempt)
        self.assertEqual(attempt, {"state": "STARTED", "failure": None, "return": None})
        guarded(latch.check, attempts, attempt)
        guarded(latch.complete, attempts, attempt, result)
        guarded(latch.returned, attempts, attempt, result)
        self.assertIs(attempt["return"], result)

    def test_postreturn_duplicate_invalidates_result_despite_visible_repair(self):
        latch, attempts, attempt = self.opened()
        result = object()
        guarded(latch.complete, attempts, attempt, result)
        first = self.refused(latch.begin, attempts)
        self.assertIs(self.refused(latch.returned, attempts, attempt, result), first)
        # Deliberately try restoring ONLY exposed DATA, never the private latch.
        attempt.update({"state": "RETURNED", "failure": None, "return": result})
        self.assertIs(self.refused(latch.check, attempts, attempt), first)
        self.assertIs(self.refused(latch.returned, attempts, attempt, result), first)

    def test_caught_callback_reentry_fails_the_immediate_postcallback_check(self):
        latch, attempts, attempt = self.opened()
        caught = []
        def callback():
            try:
                guarded(latch.begin, attempts)
            except B.BeforeError as error:
                caught.append(error)
        guarded(latch.check, attempts, attempt)
        callback()
        self.assertEqual(len(caught), 1)
        self.assertIs(self.refused(latch.check, attempts, attempt), caught[0])
        self.assertIs(self.refused(latch.complete, attempts, attempt, object()), caught[0])

    def test_late_outer_failure_invalidates_result_and_preserves_first_exception(self):
        latch, attempts, attempt = self.opened()
        result, first = object(), RuntimeError("SYNTHETIC_LATE_ENTRY_FAILURE")
        guarded(latch.complete, attempts, attempt, result)
        self.assertIs(guarded(latch.fail, first), first)
        self.assertIs(guarded(latch.fail, RuntimeError("SYNTHETIC_LATER_FAILURE")), first)
        self.assertIs(guarded(latch.fail, None), first)
        for method, args in ((latch.check, (attempts, attempt)), (latch.returned, (attempts, attempt, result)),
                (latch.begin, (attempts,))):
            with self.assertRaises(RuntimeError) as caught:
                guarded(method, *args)
            self.assertIs(caught.exception, first)

    def test_exposed_attempt_mutations_do_not_authorize_a_transition(self):
        changes = (lambda value: value.update(state="RETURNED"), lambda value: value.update(state=True),
            lambda value: value.update({"return": object()}), lambda value: value.update(failure=RuntimeError("DATA")),
            lambda value: value.update(extra=False), lambda value: value.pop("state"))
        for change in changes:
            latch, attempts, attempt = self.opened()
            change(attempt)
            self.refused(latch.check, attempts, attempt)

    def test_removed_or_replaced_visible_attempt_cannot_be_restored(self):
        for replacement in (False, True):
            latch, attempts, attempt = self.opened()
            if replacement:
                attempts["entry"] = dict(attempt)
            else:
                del attempts["entry"]
            first = self.refused(latch.check, attempts, attempt)
            attempts["entry"] = attempt
            attempt.update({"state": "STARTED", "failure": None, "return": None})
            self.assertIs(self.refused(latch.check, attempts, attempt), first)

    def test_registry_object_replacement_is_terminal_even_with_same_attempt(self):
        latch, attempts, attempt = self.opened()
        replacement = dict(attempts)
        first = self.refused(latch.check, replacement, attempt)
        self.assertIs(self.refused(latch.check, attempts, attempt), first)

    def test_wrong_equal_result_or_duplicate_completion_is_terminal(self):
        for repeat_complete in (False, True):
            latch, attempts, attempt = self.opened()
            result = {}
            guarded(latch.complete, attempts, attempt, result)
            first = self.refused(latch.complete if repeat_complete else latch.returned, attempts, attempt,
                result if repeat_complete else {})
            self.assertIs(self.refused(latch.returned, attempts, attempt, result), first)

    def test_pending_or_null_result_is_not_a_completed_entry(self):
        for complete in (False, True):
            latch, attempts, attempt = self.opened()
            self.refused(latch.complete if complete else latch.returned, attempts, attempt, None if complete else object())
        attempts = {}
        latch = guarded(B.EntryLatch, attempts)
        self.refused(latch.check, attempts, {})

    def test_foreign_attempt_and_unregistered_latch_cannot_mint_entry(self):
        first, first_table, first_attempt = self.opened()
        second, second_table, second_attempt = self.opened()
        self.refused(first.check, first_table, second_attempt)
        guarded(second.check, second_table, second_attempt)
        unregistered = object.__new__(B.EntryLatch)
        self.refused(unregistered.begin, {})
        self.assertEqual(first_attempt["state"], "FAILED")

    def test_reinitialization_cannot_reset_original_latch(self):
        latch, attempts, attempt = self.opened()
        first = self.refused(B.EntryLatch.__init__, latch, attempts)
        self.assertIs(self.refused(latch.begin, attempts), first)
        self.assertIs(self.refused(latch.check, attempts, attempt), first)


class BeforeWriteCloseDataControls(unittest.TestCase):
    """Seven supplied-metadata controls, not Windows/POSIX observations or IO."""

    def reject(self, *args):
        with self.assertRaises(ERRORS):
            guarded(B.write_close_metadata, *args)

    def test_unchanged_metadata_all_roles_is_nonmutating(self):
        for role in B.clocks.DOMAINS:
            before = file_metadata(role)
            after, old = copy.deepcopy(before), copy.deepcopy(before)
            expected = "WINDOWS_WRITE_CLOSE_MODIFIED_CHANGE_ONLY" if role == "windows-x64" else "POSIX_FULL_METADATA_EQUAL"
            self.assertEqual(guarded(B.write_close_metadata, role, before, after, 11), expected)
            self.assertEqual((before, after), (old, old))

    def test_windows_keeps_distinct_timestamps_without_invented_direction(self):
        before = file_metadata("windows-x64")
        for modified, changed in ((223, 334), (221, 332), (0, B.clocks.UINT64)):
            after = copy.deepcopy(before)
            after.update(modified_100ns=modified, change_100ns=changed)
            old = copy.deepcopy(after)
            self.assertEqual(guarded(B.write_close_metadata, "windows-x64", before, after, 11),
                "WINDOWS_WRITE_CLOSE_MODIFIED_CHANGE_ONLY")
            self.assertEqual(after, old)
            self.assertEqual((before["modified_100ns"], before["change_100ns"]), (222, 333))

    def test_every_windows_nonvolatile_field_remains_bound(self):
        before = file_metadata("windows-x64")
        for field, value in (("identity", [7, "d" * 32]), ("is_directory", True), ("size", 12), ("links", 2),
                ("attributes", 129), ("creation_100ns", 112), ("owner_sid", "S-1-5-21-123-456-789-1001"),
                ("protected_dacl", False)):
            after = copy.deepcopy(before)
            after[field] = value
            self.reject("windows-x64", before, after, 11)

    def test_both_windows_timestamp_observations_remain_strict_uint64(self):
        for field in ("modified_100ns", "change_100ns"):
            for invalid in (True, -1, 1.0, "1", None, B.clocks.UINT64 + 1):
                for side in (0, 1):
                    values = [file_metadata("windows-x64"), file_metadata("windows-x64")]
                    values[side][field] = invalid
                    self.reject("windows-x64", *values, 11)

    def test_posix_retains_full_cross_close_metadata_equality(self):
        for role in ("linux-x64", "macos-arm64", "macos-x64"):
            before = file_metadata(role)
            for field in before:
                after = dict(before)
                after[field] += 1
                self.reject(role, before, after, 11)

    def test_metadata_role_count_and_schema_are_closed(self):
        for role in ("windows-x64", "linux-x64"):
            before = file_metadata(role)
            for field in before:
                after = copy.deepcopy(before)
                del after[field]
                self.reject(role, before, after, 11)
            for after in (None, [], {**before, "new_field": 1}):
                self.reject(role, before, after, 11)
            for count in (True, -1, 12, 11.0, "11", B.wire.RECORD_LIMIT + 1):
                self.reject(role, before, before, count)
        for role in (None, [], "windows-arm64", "darwin"):
            self.reject(role, {}, {}, 0)

    def test_identity_privacy_and_scalar_aliases_are_not_weakened(self):
        before = file_metadata("windows-x64")
        for field, value in (("identity", (7, "c" * 32)), ("identity", [True, "c" * 32]),
                ("identity", [7, "C" * 32]), ("owner_sid", None), ("owner_sid", "public"),
                ("protected_dacl", 1), ("links", True), ("attributes", True), ("creation_100ns", -1),
                ("size", 11.0), ("is_directory", 0)):
            after = copy.deepcopy(before)
            after[field] = value
            self.reject("windows-x64", before, after, 11)


class BeforeSourceShapeControls(unittest.TestCase):
    """Fourteen AST assertions, NOT native/fence/lifecycle runtime tests."""

    def source(self, name, owner=None, tree=CUSTODY):
        return ast.unparse(function(tree, name, owner))

    def test_first_clock_is_capped_before_first_owned_read(self):
        parent = function(CUSTODY, "_before_pre_metadata")
        self.assertLess(calls(parent, "_BeforeClock")[0].lineno, calls(parent, "_read_before_input")[0].lineno)
        child = function(CUSTODY, "_before_authority_child")
        self.assertLess(calls(child, "_BeforeClock")[0].lineno, calls(child, "_PrimaryOwner")[0].lineno)
        self.assertIn("B.first_caps", self.source("__init__", "_BeforeClock"))
        self.assertNotIn("_TailClock", self.source("__init__", "_BeforeClock"))
        self.assertIn("inherited=caps", self.source("_before_authority_child"))

    def test_native_commands_bind_original_phase_tuple_twice(self):
        phase = function(NATIVE, "phase")
        bounded = [call for call in calls(phase, "phase_command") if any(key.arg == "before_caps" for key in call.keywords)]
        self.assertEqual(len(bounded), 2)
        for call in bounded:
            self.assertEqual(ast.unparse(next(key.value for key in call.keywords if key.arg == "before_caps")), "before_phase[:3]")
        self.assertIn("before_caps is None", self.source("phase_command", tree=NATIVE))
        self.assertIn("B.phase_caps", self.source("_before_start_fields"))
        self.assertIn("caps == anchor.binding[7]", self.source("bind_child", "_BeforeClock"))

    def test_eleven_inputs_and_metadata_readback_are_real_paths(self):
        node = function(CUSTODY, "_read_before_input")
        self.assertLess(calls(node, "_before_read")[0].lineno, calls(node, "clock.rebind_seal")[0].lineno)
        self.assertLess(calls(node, "clock.rebind_seal")[0].lineno, calls(node, "_tail_bundle")[0].lineno)
        self.assertIn("O.encoded(original.as_dict())", self.source("_before_read"))
        self.assertIn("_consume", self.source("_before_read"))
        self.assertIn("_before_same_read", self.source("_read_before_input"))
        self.assertIn("metadata.finish()", self.source("_read_before_input"))

    def test_all_279_reads_and_exact_directory_membership_are_required(self):
        self.assertIn("B.member_grammar(*identifiers)", self.source("_before_index"))
        self.assertIn("for relative, maximum, count, checksum in index", self.source("_before_capture"))
        self.assertIn("len(originals) == 279", self.source("_before_capture"))
        self.assertIn("count=count, checksum=checksum", self.source("_before_capture"))
        self.assertIn("_before_query_files", self.source("_before_capture"))
        self.assertIn("B.directory_members(required, directories, closed=False)", self.source("_before_capture"))
        self.assertIn("len(expected) <= 42", self.source("_before_directory_members"))

    def test_close_file_never_claims_its_own_hash_or_writer_close(self):
        node = function(CUSTODY, "_before_pending_close")
        rows = [value for value in ast.walk(node) if isinstance(value, ast.Dict) and
            any(isinstance(key, ast.Constant) and key.value == "self" for key in value.keys)]
        self.assertEqual(len(rows), 1)
        self_row = next(value for key, value in zip(rows[0].keys, rows[0].values) if isinstance(key, ast.Constant) and key.value == "self")
        self.assertEqual({key.value for key in self_row.keys}, {"relative", "maximum", "state"})
        self.assertIn("PENDING_SEPARATE_WRITER_READBACK_AND_CLOSE", ast.unparse(self_row))
        self.assertIn("PENDING_OWNER_CLOSE", ast.unparse(node))
        self.assertIn("NOT_OBSERVED", ast.unparse(node))

    def test_real_authority_close_precedes_separate_280th_writer(self):
        node = function(CUSTODY, "_close_before_authority")
        self.assertLess(calls(node, "owner.close")[0].lineno, calls(node, "_before_write_close")[0].lineno)
        protected = [value for value in node.body if isinstance(value, ast.Try) and calls(value, "owner.close")]
        self.assertEqual(len(protected), 1)
        self.assertEqual(len(calls(ast.Module(body=protected[0].body, type_ignores=[]), "_before_currency")), 2)
        self.assertEqual(len(calls(ast.Module(body=protected[0].finalbody, type_ignores=[]), "owner.close")), 1)
        self.assertIn("saved[8]", ast.unparse(node))
        for name, method in (("_read_before_input", "clock.attach_metadata"),
                ("_before_capture", "clock.attach_file_owner"), ("_before_write_close", "clock.attach_file_owner")):
            source = function(CUSTODY, name)
            self.assertTrue(any(isinstance(value, ast.Try) and value.finalbody and calls(value, method) for value in source.body))
        self.assertIn("owner.known()", ast.unparse(node))
        self.assertIn("len(complete) == 280", ast.unparse(node))
        checked = self.source("_checked_before_authority")
        self.assertIn("type(result) is _BeforeAuthority", checked)
        self.assertIn("result.__dict__ is dictionary", checked)
        self.assertEqual(checked.count("_before_file_owner_known("), 2)

    def test_token_frames_return_before_exhaustive_readback(self):
        node = function(CUSTODY, "before_authority")
        self.assertLess(calls(node, "_before_pre_metadata")[0].lineno, calls(node, "_close_before_authority")[0].lineno)
        self.assertNotIn("token", {value.id for value in ast.walk(node) if isinstance(value, ast.Name)})
        for name in ("_before_pre_metadata", "_before_acquire"):
            source = self.source(name)
            self.assertIn("token = None", source)
            self.assertNotIn("_before_capture(", source)
            self.assertNotIn("_before_write_close(", source)
        acquire = function(CUSTODY, "_before_acquire")
        self.assertTrue(any(isinstance(value, ast.Try) and "token = None" in ast.unparse(
            ast.Module(body=value.finalbody, type_ignores=[])) and calls(value, "_before_begin") for value in acquire.body))

    def test_all_native_phase_leave_and_expired_cleanup_seams(self):
        node = function(NATIVE, "phase")
        self.assertEqual(len(calls(node, "owner.enter_before_phase")), 1)
        self.assertEqual(len(calls(node, "owner.leave_before_phase")), 2)
        source = ast.unparse(node)
        self.assertIn("INITIAL_BEFORE_AUTHORITY_CONTEXT_SCOPE", source)
        self.assertIn("drain_end = min(capture_end, owner.local_end)", source)
        self.assertIn("BOOTSTRAP_CUSTODY_NO_ORIGINAL_CLEANUP_CEILING", source)
        self.assertIn("native.INITIAL_BEFORE_AUTHORITY_CONTEXT_SCOPE", self.source("_initial_service_phase", tree=PRIMARY))

    def test_legacy_caps_and_no_parent_before_output_route(self):
        old = self.source("__init__", "_TailClock")
        self.assertIn("30 if side == 'parent' else 45", old)
        self.assertIn("max_names=32", self.source("_tail_directory_names"))
        self.assertIn("max_names=32", self.source("_initializer_names", tree=NATIVE))
        main = self.source("main")
        self.assertIn("'_before-authority'", main)
        self.assertNotIn("'before-upload'", main)
        for name in ("before_authority", "_close_before_authority", "_before_write_close"):
            self.assertNotIn("C.append_outputs", self.source(name))
        self.assertIn("NOT_K_CAPTURE", self.source("_before_pending_close"))

    def test_single_original_entry_latch_is_bound_only_to_parent_clock(self):
        # A2 has a separate terminal productive-prefix retirement entry. It
        # must not share BEFORE's latch/registry or add another constructor at
        # any nested site. Count exact registrations, not unrelated callers.
        expected = {"_BEFORE_ENTRY": "_BEFORE_ATTEMPTS",
            "_PRODUCTIVE_PREFIX_ENTRY": "_PRODUCTIVE_PREFIX_ATTEMPTS"}
        constructors = calls(CUSTODY, "B.EntryLatch")
        registrations = [node for node in CUSTODY.body if isinstance(node, ast.Assign) and
            any(node.value is call for call in constructors)]
        self.assertEqual(len(registrations), len(expected))
        self.assertEqual({id(call) for call in constructors}, {id(node.value) for node in registrations})
        actual = {}
        for node in registrations:
            self.assertEqual(len(node.targets), 1)
            self.assertIsInstance(node.targets[0], ast.Name)
            self.assertNotIn(node.targets[0].id, actual)
            self.assertEqual(len(node.value.args), 1)
            self.assertIsInstance(node.value.args[0], ast.Name)
            self.assertEqual(node.value.keywords, [])
            actual[node.targets[0].id] = node.value.args[0].id
        self.assertEqual(actual, expected)
        self.assertIn("return _BEFORE_ENTRY.begin(_BEFORE_ATTEMPTS)", self.source("_before_begin"))
        parent = self.source("_before_pre_metadata")
        self.assertIn("entry=entry", parent)
        child = self.source("_before_authority_child")
        self.assertNotIn("entry=", child)
        constructor = self.source("__init__", "_BeforeClock")
        self.assertIn("entry is None", constructor)
        self.assertIn("_before_entry_current(entry)", constructor)
        self.assertIn("_before_entry_current(anchor.binding[9])", self.source("_current", "_BeforeClock"))

    def test_original_entry_links_acquired_currency_and_both_authority_checks(self):
        self.assertIn("owner, anchor, clock, entry", self.source("_before_acquire"))
        self.assertIn("clock_anchor.binding[9] is saved[11]", self.source("_checked_before_acquired"))
        self.assertIn("_before_entry_current(saved[11])", self.source("_before_currency"))
        self.assertIn("_checked_before_acquired(acquired)[11] is entry", self.source("_checked_before_authority"))
        self.assertIn("clock_anchor.binding[9] is entry", self.source("_checked_before_authority"))
        self.assertIn("entry = saved[18]", self.source("checked_before_authority"))
        for name in ("_checked_before_acquired", "_before_currency", "_checked_before_authority", "checked_before_authority"):
            self.assertIn(".fail(error)", self.source(name))

    def test_real_clock_callback_is_immediately_followed_by_entry_current_check(self):
        node = function(CUSTODY, "_observe", "_BeforeClock")
        blocks = [value for value in ast.walk(node) if isinstance(value, ast.If) and
            ast.unparse(value.test) == "number == 0"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(ast.unparse(blocks[0].body[0]), "anchor.binding[3]()")
        self.assertEqual(ast.unparse(blocks[0].body[1]), "self._current(anchor)")
        self.assertIn("_before_entry_current(anchor.binding[9])", self.source("_current", "_BeforeClock"))
        self.assertIn("anchor.binding[9][0].fail(error)", self.source("_error", "_BeforeClock"))

    def test_pending_internal_result_is_not_publicly_checker_accepted(self):
        private = function(CUSTODY, "_close_before_authority")
        self.assertEqual(len(calls(private, "_checked_before_authority")), 2)
        self.assertEqual(calls(private, "checked_before_authority"), [])
        outer = function(CUSTODY, "before_authority")
        self.assertLess(calls(outer, "original.complete")[0].lineno, calls(outer, "original.returned")[0].lineno)
        self.assertIn("raise original.fail(error)", ast.unparse(outer))
        public = function(CUSTODY, "checked_before_authority")
        returns = calls(public, "entry[0].returned")
        self.assertEqual(len(returns), 2)
        self.assertLess(returns[0].lineno, calls(public, "_checked_before_authority")[0].lineno)
        self.assertGreater(returns[1].lineno, calls(public, "_checked_before_authority")[0].lineno)

    def test_close_writer_retains_two_actual_stamps_without_reader_weakening(self):
        node = function(CUSTODY, "_before_write_close")
        self.assertLess(calls(node, "_consume")[0].lineno, calls(node, "_before_read")[0].lineno)
        self.assertLess(calls(node, "_before_read")[0].lineno, calls(node, "B.write_close_metadata")[0].lineno)
        source = ast.unparse(node)
        self.assertIn("'preCloseWrite': write_observation", source)
        self.assertIn("'readback': observation", source)
        self.assertIn("'metadataPolicy': metadata_policy", source)
        self.assertIn("metadata.rows[writer_ordinal][3:] == (True, True)", source)
        self.assertIn("N._history_graph(write_observation, observation", source)
        reader = self.source("_before_read")
        self.assertIn("reader.verify() == original", reader)
        self.assertIn("Q._file_info(path, reader, maximum) == original", reader)


if __name__ == "__main__":
    if "-v" not in sys.argv or "-f" not in sys.argv:
        raise SystemExit("BEFORE_CONTROLS_REQUIRE_VERBOSE_FAILFAST")
    unittest.main()
