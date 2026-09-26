#!/usr/bin/env python3
"""Focused A2 DATA/window/registry models and separate source assertions.

No previous test methods are imported or rerun. No native file/process owner,
HTTP/Git acquisition, provider, key, download or hosted qualification executes.
The registry/output controls install explicitly SYNTHETIC in-memory parents and
empty Owner shells; their closed markers are model inputs, not native retirement.
Clock/boot observations are synthetic. All production resource APIs stay unused.
"""
from __future__ import annotations

import ast
import copy
import ctypes  # Initialize the standard library before denying native loads.
from contextlib import ExitStack
import hashlib
import math
import os
from pathlib import Path, PureWindowsPath
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("PRODUCTIVE_USE_MODEL_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive as P
import hosted_cache_provider_native as V

U, O, R = P.U, P.O, V.readback
NS, BOOT = O.NS, "b" * 64
ERRORS = (O.OriginError, O.wire.BudgetError, O.clocks.ClockError, P.I.AdmissionError,
          P.C.B.BeforeError, V.L.ProviderLaunchError)
SOURCE_NAMES = ("hosted_initial_recipient_productive.py", "hosted_cache_provider_native.py",
    "run-hosted-cache-bootstrap.py", "run-hosted-initial-recipient.py", "run-hosted-initial-recipient-custody.py",
    "hosted_cache_provider_prepare.py", "hosted_cache_provider_readback.py",
    "run-hosted-initial-recipient-productive.py")
TEXT = {name: (ROOT / "scripts" / name).read_text(encoding="utf-8") for name in SOURCE_NAMES}
TREES = {name: ast.parse(raw) for name, raw in TEXT.items()}
ACTION = (ROOT / "scripts/hosted-cache-provider-action.cjs").read_text(encoding="utf-8")
ENTRY = (ROOT / ".github/actions/initial-recipient-cache-provider/index.cjs").read_text(encoding="utf-8")
YAML = (ROOT / ".github/actions/initial-recipient-cache-provider/action.yml").read_text(encoding="utf-8")


def guarded(function, *args, **kwargs):
    global GUARDED
    previous, GUARDED = GUARDED, True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = previous


def clock(role="linux-x64"):
    return O.clocks.ClockIdentity(role, O.clocks.DOMAINS[role], 7_000_003 if role == "windows-x64" else NS)


def seed(site=None, *, first=100, end=300):
    return U.seed(U.PRIVATE_SITES[0] if site is None else site, 90 * NS, end * NS, first * NS, BOOT)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def function(filename, name, owner=None):
    body = TREES[filename].body
    if owner is not None:
        selected = [node for node in body if isinstance(node, ast.ClassDef) and node.name == owner]
        if len(selected) != 1:
            raise AssertionError("EXACT_CLASS")
        body = selected[0].body
    selected = [node for node in body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(selected) != 1:
        raise AssertionError("EXACT_FUNCTION")
    return selected[0]


def calls(node, name):
    return sorted((value for value in ast.walk(node) if isinstance(value, ast.Call) and
        ast.unparse(value.func) == name), key=lambda value: (value.lineno, value.col_offset))


class UseDataControls(unittest.TestCase):
    def test_exact_twenty_one_sites_have_distinct_fixed_roots_and_scopes(self):
        self.assertEqual((len(U.PRODUCTIVE_SITES), len(U.STEP_SITES), len(U.public.SITES)), (9, 8, 4))
        self.assertEqual(len(set(U.SITES)), 21)
        self.assertEqual(len({guarded(U.site_leaf, site) for site in U.SITES}), 21)
        for index, site in enumerate(U.SITES, 1):
            self.assertEqual(guarded(U.site_leaf, site), f"use-{index:02d}-" + site.replace("/", "-"))
            self.assertEqual(guarded(U.site_scope, site), U.PUBLIC_CONTEXT if site in U.public.SITES else U.PRIVATE_CONTEXT)
        for site in ("", "ordinary/full", "help", True, U.SITES, U.SITES[0] + "/again"):
            with self.assertRaises(ERRORS):
                guarded(U.site_scope, site)

    def test_seed_uses_original_parent_and_seventy_five_one_twenty_minima(self):
        for site in U.SITES:
            for end, expected in ((300, (175, 220)), (180, (175, 180)), (140, (140, 140))):
                value = guarded(seed, site, end=end)
                self.assertEqual((value["workEndNs"], value["nativeFinalEndNs"]), tuple(item * NS for item in expected))
                self.assertIs(guarded(U.checked_seed, value), value)

    def test_seed_bad_types_changed_arithmetic_or_extra_field_refuse(self):
        changes = (("firstNs", True), ("parentFirstNs", 101 * NS), ("parentWorkEndNs", 100 * NS),
            ("workEndNs", 176 * NS), ("nativeFinalEndNs", 221 * NS), ("originalBootDigest", "B" * 64),
            ("site", "unregistered"), ("extra", False))
        for name, value in changes:
            with self.subTest(name=name), self.assertRaises(ERRORS):
                guarded(U.checked_seed, {**seed(), name: value})

    def test_phase_caps_are_exact_inherited_tuple_not_fresh_child_allowance(self):
        value = seed()
        self.assertEqual(guarded(U.phase_caps, value, (110 * NS, 155 * NS, 200 * NS)),
                         (110 * NS, 155 * NS, 200 * NS))
        for caps in ([110 * NS, 155 * NS, 200 * NS], (True, 155 * NS, 200 * NS),
                (110 * NS, 156 * NS, 200 * NS), (110 * NS, 155 * NS, 201 * NS),
                (99 * NS, 144 * NS, 189 * NS), (175 * NS, 175 * NS, 220 * NS)):
            with self.subTest(caps=caps), self.assertRaises(ERRORS):
                guarded(U.phase_caps, value, caps)

    def test_all_roles_frame_is_supplied_data_without_authority_fields(self):
        for role in O.clocks.DOMAINS:
            c, value = clock(role), seed()
            result = guarded(U.frame, value, c)
            self.assertEqual(guarded(U.checked_frame, result), (c, value))
            self.assertEqual(set(result), {"schema", "scope", "clock", *U.SEED_NAMES})
            self.assertEqual(result["scope"], U.WINDOW_SCOPE)

    def test_frame_full_schema_scope_and_clock_validation_cannot_be_skipped(self):
        frame = U.frame(seed(), clock())
        for name, value in (("schema", True), ("scope", U.RETURN_SCOPE), ("extra", None),
                ("clock", {**frame["clock"], "ticksPerSecond": 1}), ("workEndNs", 300 * NS)):
            with self.subTest(name=name), self.assertRaises(ERRORS):
                guarded(U.checked_frame, {**frame, name: value})


class UseWindowModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.clock, self.raw, self.local, self.boot = clock(), 100 * NS, 1000.0, BOOT
        self.callbacks, self.observations, self.boots = 0, 0, 0
        self.action = lambda: None
        self.stack.enter_context(patch.object(time, "monotonic", lambda: self.local))
        self.stack.enter_context(patch.object(O.clocks, "observe", self.observe))
        self.stack.enter_context(patch.object(U.continuity, "boot_digest", self.observe_boot))

    def observe(self):
        self.observations += 1
        return O.clocks.Reading(self.clock, self.raw)

    def observe_boot(self, role):
        self.assertEqual(role, self.clock.role)
        self.boots += 1
        return self.boot

    def current(self):
        self.callbacks += 1
        self.action()

    def window(self, *, end=300, local_end=1200.0):
        return guarded(U.UseWindow, O.clocks.Reading(self.clock, self.raw), self.local, self.boot,
            seed(first=self.raw // NS, end=end), self.current, side="parent", parent_local_end=local_end)

    def test_actual_window_model_observes_two_raw_two_boot_three_parent_checks(self):
        for role in O.clocks.DOMAINS:
            self.clock = clock(role)
            window = self.window()
            before = self.callbacks, self.observations, self.boots
            self.assertEqual(guarded(window.now), self.raw)
            self.assertEqual((self.callbacks - before[0], self.observations - before[1], self.boots - before[2]), (3, 2, 2))
            self.assertEqual((window.first, window.work, window.final), (100 * NS, 175 * NS, 220 * NS))
            self.assertLessEqual(window.local_end, 1120.0)

    def test_delayed_child_does_not_renew_original_native_work_or_final(self):
        caps = 110 * NS, 155 * NS, 200 * NS
        self.raw = 150 * NS
        window = guarded(U.UseWindow, O.clocks.Reading(self.clock, self.raw), self.local, BOOT,
            seed(), self.current, side="child", caps=caps)
        self.assertEqual((window.work, window.final), (155 * NS, 155 * NS))
        self.assertLessEqual(window.local_end, 1005.0)
        self.assertEqual(guarded(window.now), self.raw)
        self.raw = 155 * NS
        with self.assertRaises(ERRORS):
            guarded(window.now, final=True)

    def test_parent_raw_and_local_original_caps_only_shorten(self):
        window = self.window(end=140, local_end=1010.0)
        self.assertEqual((window.work, window.final), (140 * NS, 140 * NS))
        self.assertEqual(window.local_end, 1010.0)
        self.local, self.raw = 1009.0, 139 * NS
        self.assertEqual(guarded(window.now), self.raw)
        self.local = 1010.0
        with self.assertRaises(ERRORS):
            guarded(window.now, final=True)

    def test_raw_work_expiry_is_sticky_even_when_clock_is_restored(self):
        window = self.window()
        self.raw = window.work
        with self.assertRaises(ERRORS) as first:
            guarded(window.now)
        self.raw = 100 * NS
        with self.assertRaises(ERRORS) as again:
            guarded(window.now, final=True)
        self.assertIs(first.exception, again.exception)

    def test_final_is_separate_cleanup_cap_not_success_work(self):
        window = self.window()
        self.raw = 180 * NS
        self.assertEqual(guarded(window.now, final=True), self.raw)
        self.raw = window.final
        with self.assertRaises(ERRORS):
            guarded(window.now, final=True)

    def test_local_expiry_rejects_before_new_raw_observation(self):
        window = self.window()
        self.local = 2000.0
        with self.assertRaises(ERRORS):
            guarded(window.now)
        self.assertEqual(self.observations, 0)

    def test_raw_backwards_observation_cannot_replace_the_original_frontier(self):
        window = self.window()
        self.raw = 101 * NS
        guarded(window.now)
        self.raw = 100 * NS
        with self.assertRaises(ERRORS):
            guarded(window.now)

    def test_local_backwards_observation_is_also_terminal(self):
        window = self.window()
        self.local = 1001.0
        guarded(window.now)
        self.local = 1000.5
        with self.assertRaises(ERRORS):
            guarded(window.now)

    def test_boot_replacement_fails_without_a_new_window(self):
        window = self.window()
        self.boot = "c" * 64
        with self.assertRaises(ERRORS) as first:
            guarded(window.now)
        self.boot = BOOT
        with self.assertRaises(ERRORS) as again:
            guarded(window.now)
        self.assertIs(first.exception, again.exception)

    def test_equal_bound_copy_and_restore_does_not_erase_failure(self):
        window = self.window()
        original = window._bound
        window._bound = tuple(list(original))
        with self.assertRaises(ERRORS) as first:
            guarded(window.now)
        window._bound = original
        with self.assertRaises(ERRORS) as again:
            guarded(window.now)
        self.assertIs(first.exception, again.exception)

    def test_original_first_dictionary_replacement_is_not_equal_value_authority(self):
        window = self.window()
        first = window._bound[0]
        old = first.__dict__
        object.__setattr__(first, "__dict__", dict(old))
        with self.assertRaises(ERRORS) as failure:
            guarded(window.now)
        object.__setattr__(first, "__dict__", old)
        with self.assertRaises(ERRORS) as again:
            guarded(window.now)
        self.assertIs(failure.exception, again.exception)

    def test_callback_cannot_mutate_then_return_a_changed_first(self):
        window = self.window()
        self.action = lambda: object.__setattr__(window._bound[0], "nanoseconds", 99 * NS)
        with self.assertRaises(ERRORS):
            guarded(window.now)

    def test_caught_recursive_callback_failure_still_poisoned_original(self):
        window = self.window()
        caught = []
        def reenter():
            try:
                window.now()
            except ERRORS as error:
                caught.append(error)
        self.action = reenter
        with self.assertRaises(ERRORS) as result:
            guarded(window.now)
        self.assertTrue(caught)
        self.assertIs(result.exception, caught[0])

    def test_deadline_captures_earlier_local_not_a_later_callback_allowance(self):
        window = self.window()
        def spend():
            self.local += 0.25
            self.raw += NS // 4
        self.action = spend
        deadline = guarded(window.deadline, 20)
        self.assertLessEqual(deadline, 1020.0)
        self.assertGreater(self.local, 1000.0)
        self.assertLess(deadline, self.local + 20)

    def test_invalid_operation_budget_and_constructor_binding_refuse(self):
        for maximum in (True, 0, -1, float("inf"), float("nan"), 901):
            with self.subTest(maximum=maximum), self.assertRaises(ERRORS):
                guarded(self.window().deadline, maximum)
        for side, end, caps in (("invalid", 1200.0, None), ("parent", 1000.0, None),
                ("parent", 1200.0, (110 * NS, 155 * NS, 200 * NS)), ("child", 1200.0, None)):
            with self.subTest(side=side, end=end), self.assertRaises(ERRORS):
                guarded(U.UseWindow, O.clocks.Reading(self.clock, self.raw), self.local, BOOT, seed(),
                    self.current, side=side, parent_local_end=end, caps=caps)


class ProviderRegistryModels(unittest.TestCase):
    """Synthetic registry/shell inputs only. No _new_initial_parent/native call."""
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.raw, self.local = 100 * NS, 1000.0
        self.clock = clock()
        self.events = []
        self.environment_action = lambda: None
        self.stack.enter_context(patch.object(time, "monotonic", lambda: self.local))
        self.stack.enter_context(patch.object(O.clocks, "observe", lambda: O.clocks.Reading(self.clock, self.raw)))
        self.stack.enter_context(patch.object(V, "P", P))
        self.stack.enter_context(patch.object(V, "B", P.B))
        self.stack.enter_context(patch.object(V, "_ORIGIN", "initial-recipient"))
        self.stack.enter_context(patch.object(V, "_INITIAL_PARENTS", {}))
        self.stack.enter_context(patch.object(V, "_INITIAL_ENTRY", None))
        self.first = O.clocks.Reading(self.clock, self.raw)
        self.fence = V._Fence(self.first, 90 * NS, 270 * NS, self.environment)
        self.owner = P.B.Owner(1045.0, self.fence, first=self.first)
        self.owner.work_limit, self.owner.final_limit = 225 * NS, 270 * NS
        self.parent = V._InitialProviderParent()
        self.attempts = {}
        self.entry = P.C.B.EntryLatch(self.attempts)
        self.attempt = self.entry.begin(self.attempts)
        self.registration = self.entry, self.attempts, self.attempt, self.parent
        V._INITIAL_ENTRY = self.registration
        owner_binding = (self.owner.__dict__, self.first, self.fence, self.owner.cancelled,
            self.owner.resources, self.owner.errors, self.owner.local_end, self.owner.work_limit, self.owner.final_limit)
        self.state = V._InitialParentState(self.parent, self.owner, self.fence, self.first, self.local,
            145 * NS, 1045.0, "save", {}, (), "EXPLICIT_SYNTHETIC_NOT_A_HOST", object(), object(),
            self.registration, owner_binding, P.N._history_graph(self.first), BOOT)
        V._INITIAL_PARENTS[id(self.parent)] = self.state, self.state.__dict__, tuple(self.state.__dict__.items())

    def environment(self):
        self.events.append("environment-model")
        self.environment_action()

    def output(self):
        # Explicit modeled consumed results / complete-close inputs. They never
        # enter the actual production use or original native owner registries.
        self.stack.enter_context(patch.object(P, "checked_consumed_use",
            lambda result, parent, site: self.events.append(("consumed-model", site))))
        inputs, materialized = SimpleNamespace(plan={"model": True}), SimpleNamespace(request=b"MODEL")
        V._initial_progress(self.parent, chain=b"MODEL_CHAIN", uses=(SimpleNamespace(site="begin"),
            SimpleNamespace(site="final")), inputs=inputs, inputs_pin=(inputs.__dict__, P.N._history_graph(inputs.__dict__)),
            materialized=materialized, materialized_pin=(materialized.__dict__, P.N._history_graph(materialized.__dict__)))
        self.entry.complete(self.attempts, self.attempt, self.state.chain)
        self.owner.closed = True  # MODEL INPUT, not an observed close or production registry write.
        return V._InitialOutputFence(self.parent, ())

    def test_constructor_or_equal_parent_copy_is_not_registered_authority(self):
        self.assertIs(guarded(V._initial_state, self.parent), self.state)
        with self.assertRaises(ERRORS):
            guarded(V._initial_state, V._InitialProviderParent())
        with self.assertRaises(ERRORS):
            guarded(V._initial_state, self.parent)

    def test_equal_state_dictionary_copy_and_restore_cannot_clear_entry_failure(self):
        original = self.state.__dict__
        self.state.__dict__ = dict(original)
        with self.assertRaises(ERRORS) as first:
            guarded(V._initial_state, self.parent)
        self.state.__dict__ = original
        with self.assertRaises(ERRORS) as again:
            guarded(V._initial_state, self.parent)
        self.assertIs(first.exception, again.exception)

    def test_direct_dynamic_field_change_must_not_replace_snapshot(self):
        self.state.site = U.public.SITES[0]
        with self.assertRaises(ERRORS) as first:
            guarded(V._initial_state, self.parent)
        self.state.site = None
        with self.assertRaises(ERRORS) as again:
            guarded(V._initial_state, self.parent)
        self.assertIs(first.exception, again.exception)

    def test_fixed_progress_checks_prior_snapshot_and_rejects_static_field_change(self):
        self.assertIs(guarded(V._initial_progress, self.parent, site=U.public.SITES[0]), self.state)
        self.assertEqual(self.state.site, U.public.SITES[0])
        self.assertIs(guarded(V._initial_state, self.parent), self.state)
        with self.assertRaises(ERRORS):
            guarded(V._initial_progress, self.parent, work_end=146 * NS)
        self.assertEqual(self.state.work_end, 145 * NS)

    def test_output_uses_same_helper45_and_keeps_consumed_uses_historical(self):
        output = self.output()
        self.raw, self.local = 140 * NS, 1040.0
        self.assertEqual(guarded(output.now, final=True), self.raw)
        self.assertEqual([item for item in self.events if type(item) is tuple],
                         [("consumed-model", "begin"), ("consumed-model", "final")])
        self.raw, self.local = 145 * NS, 1044.0  # ProviderW225 still has80 seconds; helper45 does not.
        with self.assertRaises(ERRORS):
            guarded(output.now, final=True)

    def test_output_refuses_missing_close_model_input_before_callbacks(self):
        output = self.output()
        self.owner.closed = False
        with self.assertRaises(ERRORS):
            guarded(output.now, final=True)
        self.assertEqual(self.events, [])

    def test_output_interface_never_accepts_ordinary_work_mode(self):
        output = self.output()
        with self.assertRaises(ERRORS):
            guarded(output.now)
        self.assertEqual(self.events, [])

    def test_post_clock_owner_mutation_is_not_a_successful_output(self):
        output = self.output()
        failure = RuntimeError("SYNTHETIC_OWNER_FAILURE")
        self.environment_action = lambda: setattr(self.owner, "original", failure)
        with self.assertRaises(ERRORS) as first:
            guarded(output.now, final=True)
        self.owner.original = None
        self.environment_action = lambda: None
        with self.assertRaises(ERRORS) as again:
            guarded(output.now, final=True)
        self.assertIs(first.exception, again.exception)

    def test_output_cannot_accept_mutated_materializer_graph(self):
        output = self.output()
        self.environment_action = lambda: setattr(self.state.materialized, "request", b"CHANGED_MODEL")
        with self.assertRaises(ERRORS):
            guarded(output.now, final=True)

    def test_output_local_expiry_is_independent_of_provider_raw_budget(self):
        output = self.output()
        self.local = 1045.0
        with self.assertRaises(ERRORS):
            guarded(output.now, final=True)

    def test_initial_loader_has_one_graph_and_never_falls_back_from_trusted_main(self):
        self.assertIs(guarded(V._initial_bootstrap), P.B)
        self.assertIs(P.C.N.native, P.B)
        self.assertIs(P.C.native, P.B)
        with self.assertRaises(ERRORS):
            guarded(V._bootstrap)
        self.assertIs(V.B, P.B)
        self.assertEqual(V._ORIGIN, "initial-recipient")


def index_fixture(root, site, frame):
    """Synthetic index declarations, NOT query originals or full281-file custody."""
    pinned = (".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")
    dirs = list(pinned)
    maxima = {name: 2 * 1024 * 1024 for name in ("use-window.json", "context.json", "use-pending.json",
        "service/child-result.json", *("service/" + name for name in R.initial_records.PHASE_FILES))}
    maxima["service/stdout.log"], maxima["service/stderr.log"] = 16384, 65536
    available = set(maxima)
    number = 1
    for section, count in (("source-before", 12), ("acquisition-queries", 24), ("source-after", 12)):
        dirs.append(section + "/query-home")
        maxima[section + "/owner.json"] = 1
        for slot in range(count):
            prefix = section + f"/query-{number:032x}"
            number += 1
            dirs.append(prefix)
            limit = P.I.EVENT_LIMIT if slot % 12 == 1 else P.I.POLICY_LIMIT if slot % 12 == 11 else 4096
            for leaf in R.initial_records.QUERY_FILES:
                maxima[prefix + "/" + leaf] = limit if leaf == "stdout.log" else 4096 if leaf == "stderr.log" else 1
        keys = R.initial_records.ORIGINAL_KEYS if section == "acquisition-queries" else R.initial_records.SOURCE_KEYS
        for name in keys:
            maxima[section + "/" + name + ".bin"] = 1
            available.add(section + "/" + name + ".bin")
        for name in (("session-result.json",) if section == "acquisition-queries" else
                ("session-result.json", "source-return.json")):
            maxima[section + "/" + name] = 2 * 1024 * 1024
            available.add(section + "/" + name)
    rows = [{"relative": name, "maximum": maximum, "bytes": 1, "sha256": digest(b"x"),
        "provenance": "ACTUAL_RETAINED_BYTES" if name in available else "ORIGINAL_QUERY_DECLARATION"}
        for name, maximum in sorted(maxima.items())]
    files = {row["relative"]: row for row in rows}
    raw = O.encoded(frame)
    files["use-window.json"].update(bytes=len(raw), sha256=digest(raw))
    identities = {name: [7, f"{index:032x}" if frame["clock"]["role"] == "windows-x64" else index]
        for index, name in enumerate(pinned, 1)}
    return {"schema": 1, "scope": "INITIAL_RECIPIENT_PER_USE_ORIGINAL_INDEX_V1", "site": site,
        "root": str(root), "clock": frame["clock"], "contextSha256": files["context.json"]["sha256"],
        "pendingSha256": files["use-pending.json"]["sha256"], "files": rows,
        "directories": [{"relative": name, "identity": identities.get(name),
            "provenance": "ORIGINAL_NATIVE_PIN" if name in pinned else "ORIGINAL_QUERY_DECLARATION"}
            for name in sorted(dirs)], "fileCount": len(rows), "directoryCount": len(dirs),
        "totalBytes": sum(row["bytes"] for row in rows), "copyState": "ORIGINAL_BYTES_NOT_COPIED",
        "exportSaveAuthority": False}


class ChainFixture:
    def __init__(self, *, role="linux-x64", phase="save"):
        self.phase, self.clock = phase, clock(role)
        self.first = O.clocks.Reading(self.clock, 120 * NS)
        root = PureWindowsPath("C:/synthetic/initial-worker") if role == "windows-x64" else Path("/synthetic/initial-worker")
        directory = root.with_name(root.name + ("-save" if phase == "save" else "-probe"))
        self.descriptor = {"scope": "INITIAL_RECIPIENT_BOOTSTRAP_" + ("SAVE" if phase == "save" else "PROBE") +
            "_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1", "directory": str(directory),
            "clock": O.clock_value(self.clock), "plan": {"source": {"model": "source"}, "github": {"model": "github"}},
            "providerWindow": {"issuedNs": 90 * NS, "hardEndNs": 270 * NS, "actualProviderStart": "NOT_OBSERVED"}}
        self.packet = {"scope": "INITIAL_RECIPIENT_PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1",
            "phase": phase, "firstNs": str(100 * NS), "originalClaims":
                {"HANDOFF_SHA256": "a" * 64, "PRODUCER_RETURN_SHA256": "c" * 64}}
        self.chain = {"schema": 1, "scope": "INITIAL_RECIPIENT_PROVIDER_ORIGINAL_USE_CHAIN_V1", "phase": phase,
            "clock": O.clock_value(self.clock), "originalBootDigest": BOOT, "helperFirstNs": 100 * NS,
            "helperWorkEndNs": 145 * NS, "providerIssuedNs": 90 * NS, "providerHardEndNs": 270 * NS,
            "handoffSha256": "a" * 64, "producerReturnSha256": "c" * 64, "workerIdentitySha256": "d" * 64,
            "directory": str(directory / "native-preparation"),
            "directoryIdentity": [7, "f" * 32 if role == "windows-x64" else 99],
            "source": copy.deepcopy(self.descriptor["plan"]["source"]),
            "github": copy.deepcopy(self.descriptor["plan"]["github"]), "materializedNs": 110 * NS, "uses": [],
            "checkedNs": 115 * NS, "helperOwnerClose": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE",
            "providerExecution": "NOT_PERFORMED", "exportSaveAuthority": False}
        self.returns, self.indices = {}, {}
        for number, edge in enumerate(("begin", "final")):
            site = ("provider-save" if phase == "save" else "provider-probe") + "/native-prepare/" + edge
            began = (101 + number * 10) * NS
            window = U.frame(U.seed(site, 100 * NS, 145 * NS, began, BOOT), self.clock)
            path = root.with_name(root.name + "-" + U.site_leaf(site))
            index = index_fixture(path, site, window)
            files = {row["relative"]: row for row in index["files"]}
            original_chain = {"phaseSha256": {name: files["service/" + name]["sha256"] for name in R.initial_records.PHASE_FILES},
                "childSha256": files["service/child-result.json"]["sha256"],
                "querySessionSha256": files["acquisition-queries/session-result.json"]["sha256"],
                "originalsSha256": {name: files["acquisition-queries/" + name + ".bin"]["sha256"]
                    for name in R.initial_records.ORIGINAL_KEYS}, "checkedNs": began + NS}
            self.returns[edge] = {"schema": 1, "scope": U.RETURN_SCOPE, "site": site,
                "windowSha256": digest(O.encoded(window)), "workerIdentitySha256": "d" * 64,
                "pendingSha256": index["pendingSha256"], "originalChain": original_chain,
                "preCloseNs": began + 2 * NS, "closedNs": began + 3 * NS, "resourceCount": 7,
                "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
            self.indices[edge] = index
            self.chain["uses"].append({"site": site, "root": str(path), "window": window})

    def encoded(self):
        # Rebind hashes after intentional DATA mutation so negative cases test
        # the semantic predicates rather than only a stale checksum.
        preparation = O.encoded(self.descriptor)
        self.chain["preparationSha256"] = self.packet["preparationSha256"] = digest(preparation)
        originals = {}
        for edge, use in zip(("begin", "final"), self.chain["uses"]):
            index = O.encoded(self.indices[edge])
            self.returns[edge]["inventorySha256"] = use["inventorySha256"] = digest(index)
            raw = O.encoded(self.returns[edge])
            use["returnSha256"] = digest(raw)
            originals[edge + "-use.json"], originals[edge + "-use-index.json"] = raw, index
        originals["initial-use-chain.json"] = O.encoded(self.chain)
        self.packet["initialUseChainSha256"] = digest(originals["initial-use-chain.json"])
        return originals, O.encoded(self.packet), preparation

    def check(self):
        return guarded(R.validate_initial_use_chain, *self.encoded(), self.first, phase=self.phase)


class ProviderChainDataControls(unittest.TestCase):
    def test_four_roles_both_provider_phases_exact_five_file_data_contract(self):
        for role in O.clocks.DOMAINS:
            for phase in ("save", "lookup"):
                fixture = ChainFixture(role=role, phase=phase)
                self.assertEqual(fixture.check(), fixture.chain)
                self.assertEqual(set(fixture.encoded()[0]), set(R.INITIAL_USE_FILES))
                self.assertEqual(fixture.chain["helperOwnerClose"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")

    def test_missing_extra_and_swapped_actual_files_refuse(self):
        fixture = ChainFixture()
        originals, packet, preparation = fixture.encoded()
        for raw in ({name: value for name, value in originals.items() if name != "final-use.json"},
                {**originals, "extra.json": b"{}"}, {**originals, "final-use.json": originals["begin-use.json"]}):
            with self.assertRaises(ERRORS):
                guarded(R.validate_initial_use_chain, raw, packet, preparation, fixture.first, phase=fixture.phase)

    def test_old_scopes_and_self_asserted_native_provider_success_refuse(self):
        for where, key, value in (("chain", "scope", "ORDINARY"), ("packet", "scope", "PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1"),
                ("descriptor", "scope", "BOOTSTRAP_SAVE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1"),
                ("chain", "helperOwnerClose", "KNOWN"), ("chain", "providerExecution", "PASSED"),
                ("chain", "exportSaveAuthority", True), ("chain", "schema", True)):
            fixture = ChainFixture()
            getattr(fixture, where)[key] = value
            with self.subTest(where=where, key=key), self.assertRaises(ERRORS):
                fixture.check()

    def test_helper45_provider180_and_parent_clipping_are_not_relaxed(self):
        for key, value in (("helperWorkEndNs", 146 * NS), ("providerHardEndNs", 271 * NS),
                ("helperFirstNs", 99 * NS), ("providerIssuedNs", 91 * NS), ("checkedNs", 145 * NS)):
            fixture = ChainFixture()
            fixture.chain[key] = value
            with self.subTest(key=key), self.assertRaises(ERRORS):
                fixture.check()

    def test_begin_materializer_final_and_close_order_is_mandatory(self):
        cases = (("begin", "closedNs", 111 * NS), ("final", "preCloseNs", 145 * NS),
            ("final", "closedNs", 145 * NS), ("final", "closedNs", 111 * NS))
        for edge, key, value in cases:
            fixture = ChainFixture()
            fixture.returns[edge][key] = value
            with self.subTest(edge=edge, key=key), self.assertRaises(ERRORS):
                fixture.check()
        fixture = ChainFixture()
        fixture.chain["materializedNs"] = 112 * NS  # Final use began111 before the materializer.
        with self.assertRaises(ERRORS):
            fixture.check()

    def test_original_site_window_boot_and_worker_binding_refuse_substitution(self):
        for where, key, value in (("use", "site", U.public.SITES[-1]), ("window", "parentWorkEndNs", 146 * NS),
                ("window", "originalBootDigest", "e" * 64), ("window", "extra", False),
                ("return", "workerIdentitySha256", "e" * 64), ("return", "resourceCount", True)):
            fixture = ChainFixture()
            target = fixture.chain["uses"][0] if where == "use" else fixture.chain["uses"][0]["window"] \
                if where == "window" else fixture.returns["begin"]
            target[key] = value
            with self.subTest(where=where, key=key), self.assertRaises(ERRORS):
                fixture.check()

    def test_predecessor_source_root_and_directory_identity_refuse(self):
        for key, value in (("handoffSha256", "e" * 64), ("producerReturnSha256", "e" * 64),
                ("source", {"other": True}), ("directory", "/synthetic/other"), ("directoryIdentity", [7, True])):
            fixture = ChainFixture()
            fixture.chain[key] = value
            with self.subTest(key=key), self.assertRaises(ERRORS):
                fixture.check()

    def test_index_is_full281_not_the_thirty_eight_available_blobs(self):
        fixture = ChainFixture()
        index = fixture.indices["begin"]
        self.assertEqual((len(index["files"]), len(index["directories"])), (281, 58))
        index["files"] = [row for row in index["files"] if row["provenance"] == "ACTUAL_RETAINED_BYTES"]
        self.assertEqual(len(index["files"]), 38)
        index["fileCount"] = 38
        index["totalBytes"] = sum(row["bytes"] for row in index["files"])
        with self.assertRaises(ERRORS):
            fixture.check()

    def test_index_fixed_maxima_are_not_just_any_two_mib_value(self):
        for name in ("service/stdout.log", "service/stderr.log", "source-before/owner.json",
                "source-before/query-00000000000000000000000000000001/stderr.log",
                "source-before/query-00000000000000000000000000000001/start.json",
                "source-before/base_policy_entry.bin", "source-before/session-result.json"):
            fixture = ChainFixture()
            row = next(row for row in fixture.indices["begin"]["files"] if row["relative"] == name)
            row["maximum"] = row["maximum"] - 1 if row["maximum"] == 2 * 1024 * 1024 else row["maximum"] + 1
            with self.subTest(name=name), self.assertRaises(ERRORS):
                fixture.check()

    def test_index_original_pin_alias_path_and_provenance_changes_refuse(self):
        for mutation in ("alias", "unexpected-directory", "file-provenance", "file-alias", "missing-query"):
            fixture = ChainFixture()
            index = fixture.indices["begin"]
            if mutation == "alias":
                rows = [row for row in index["directories"] if row["identity"] is not None]
                rows[1]["identity"] = rows[0]["identity"]
            elif mutation == "unexpected-directory":
                index["directories"][-1]["relative"] = "../alias"
            elif mutation == "file-provenance":
                index["files"][0]["provenance"] = "NEW_CURRENT_AUTHORITY"
            elif mutation == "file-alias":
                index["files"][1]["relative"] = index["files"][0]["relative"]
            else:
                index["directories"] = index["directories"][:-1]
            with self.subTest(mutation=mutation), self.assertRaises(ERRORS):
                fixture.check()

    def test_index_bad_hash_empty_digest_integer_types_and_total_refuse(self):
        for field, value in (("sha256", "A" * 64), ("bytes", 0), ("bytes", True), ("maximum", True)):
            fixture = ChainFixture()
            fixture.indices["begin"]["files"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ERRORS):
                fixture.check()
        fixture = ChainFixture()
        fixture.indices["begin"]["totalBytes"] += 1
        with self.assertRaises(ERRORS):
            fixture.check()


class IntegrationSourceAssertions(unittest.TestCase):
    """Source-shape assertions only; NOT original child/native/control execution."""
    def test_single_c_n_b_graph_and_fixed_loader_boundaries(self):
        tree = TREES["hosted_initial_recipient_productive.py"]
        self.assertEqual(len(calls(tree, "importlib.util.spec_from_file_location")), 1)
        self.assertEqual(len(calls(tree, "_spec.loader.exec_module")), 1)
        self.assertIn("N, B, A, O, I, Q = (C.N, C.N.native, C.N.acquisition, C.O, C.I, C.Q)", ast.unparse(tree))
        native = function("hosted_cache_provider_native.py", "_initial_bootstrap")
        self.assertEqual(calls(native, "_bootstrap"), [])
        self.assertIn("P.C.N is P.N", ast.unparse(native))

    def test_current_use_is_source_before_child_source_after_then_real_closed_return(self):
        node = function("hosted_initial_recipient_productive.py", "_acquire")
        source, child, close = calls(node, "N.source_queries"), calls(node, "N._initial_service_phase"), calls(node, "owner.close")
        self.assertEqual((len(source), len(child), len(close)), (2, 1, 1))
        self.assertLess(source[0].lineno, child[0].lineno)
        self.assertLess(child[0].lineno, source[1].lineno)
        self.assertLess(source[1].lineno, calls(node, "owner.freeze")[0].lineno)
        self.assertLess(close[0].lineno, calls(node, "owner.known")[0].lineno)
        self.assertLess(calls(node, "owner.known")[0].lineno, calls(node, "InitialUse")[0].lineno)

    def test_consumed_result_never_reenters_old_parent_clock_or_current_time(self):
        node = function("hosted_initial_recipient_productive.py", "_checked_use")
        branches = [part for part in ast.walk(node) if isinstance(part, ast.If) and ast.unparse(part.test) == "not consumed"]
        self.assertEqual(len(branches), 1)
        self.assertEqual(len(calls(branches[0], "time.time")), 1)
        chosen = [part for part in ast.walk(node) if isinstance(part, ast.If) and ast.unparse(part.test) == "consumed"]
        self.assertEqual(len(chosen), 1)
        branch = ast.Module(body=chosen[0].body, type_ignores=[])
        for name in ("_parent", "time.time", "window.now", "window.deadline", "acquire_public", "acquire_private"):
            self.assertEqual(calls(branch, name), [])
        self.assertEqual(calls(node, "window.now"), [])

    def test_prefix_retirement_is_twelve_existing_inputs_not_initializer_reexecution(self):
        node = function("run-hosted-initial-recipient-custody.py", "retire_primary_for_productive")
        self.assertEqual(len(P.C._PRODUCTIVE_INITIALIZER_NAMES), 12)
        self.assertEqual(len(set(P.C._PRODUCTIVE_INITIALIZER_NAMES)), 12)
        for name in ("N.initialize", "native.phase", "native.produce_originals", "_export_pre_crypto"):
            self.assertEqual(calls(node, name), [])
        self.assertLess(calls(node, "wrapper.finish")[0].lineno, calls(node, "RetiredProductivePrefix")[0].lineno)
        passive = function("run-hosted-initial-recipient-custody.py", "checked_retired_primary")
        for name in ("window.now", "window.deadline", "checked_primary", "checked_custody_authority", "callback"):
            self.assertEqual(calls(passive, name), [])

    def test_provider_begin_and_final_surround_same_materializer_not_help(self):
        graph = function("hosted_cache_provider_native.py", "_initial_graph")
        uses = calls(graph, "_initial_use")
        self.assertEqual([ast.literal_eval(call.args[1]) for call in uses], ["begin", "final"])
        self.assertLess(uses[0].lineno, calls(graph, "adapter.rederive_provider_inputs")[0].lineno)
        self.assertLess(uses[1].lineno, calls(graph, "adapter.recheck_provider_inputs")[0].lineno)
        operation = function("hosted_cache_provider_native.py", "_operate")
        self.assertEqual(len(calls(operation, "materialize")), 1)
        self.assertLess(calls(operation, "materialize")[0].lineno, calls(operation, "final_readback")[0].lineno)
        self.assertNotIn("help", {item.value for item in ast.walk(operation) if isinstance(item, ast.Constant) and type(item.value) is str})

    def test_output_fence_rechecks_owner_after_last_original_clock(self):
        node = function("hosted_cache_provider_native.py", "now", "_InitialOutputFence")
        self.assertEqual(len(calls(node, "self._closed")), 2)
        self.assertLess(calls(node, "state.fence.now")[-1].lineno, calls(node, "self._closed")[-1].lineno)
        self.assertIn("state.work_end", ast.unparse(node))
        self.assertIn("state.local_work_end", ast.unparse(node))

    def test_source_owned_wrappers_keep_ordinary_and_initial_origins_distinct(self):
        pairs = (("hosted_cache_provider_prepare.py", "materialize", "materialize_initial_recipient", "_materialize"),
            ("hosted_cache_provider_native.py", "operate", "operate_initial", "_operate"),
            ("hosted_cache_provider_readback.py", "validate_action_return", "validate_initial_action_return", "_validate_action_return"))
        for name, old, new, core in pairs:
            for wrapper, literal in ((old, "trusted-main"), (new, "initial-recipient")):
                selected = calls(function(name, wrapper), core)
                self.assertEqual(len(selected), 1)
                self.assertEqual(ast.literal_eval(selected[0].args[0]), literal)

    def test_public_child_has_fixed_no_token_branch_and_private_steps_remain_private(self):
        phase = function("run-hosted-cache-bootstrap.py", "phase")
        branches = [node for node in ast.walk(phase) if isinstance(node, ast.If) and
            ast.unparse(node.test) == "context.get('scope') == INITIAL_PROVIDER_PUBLIC_CONTEXT_SCOPE"]
        self.assertEqual(len(branches), 2)  # Setup/inheritance and actual launch credential boundary.
        launch = next(node for node in branches if "BOOTSTRAP_PUBLIC_USE_LAUNCH_CREDENTIAL" in ast.unparse(node))
        self.assertIn("token is None", ast.unparse(launch))
        self.assertIn("env[origin.wire.TOKEN_ENV]", ast.unparse(ast.Module(body=launch.orelse, type_ignores=[])))
        step = function("hosted_initial_recipient_productive.py", "step")
        self.assertEqual(len(calls(step, "os.environ.pop")), 1)
        mappings = [node for node in ast.walk(step) if isinstance(node, ast.Dict)]
        self.assertEqual(len(mappings), 1)
        self.assertEqual({ast.literal_eval(key) for key in mappings[0].keys},
                         {"prepare-save", "after-save", "prepare-probe", "after-probe"})
        self.assertIn("finally:\n        token = None", ast.unparse(step))

    def test_initial_action_fixed_node24_route_has_no_token_or_workflow_activation_input(self):
        self.assertIn("using: node24", YAML)
        self.assertIn("mainInitialRecipient();", ENTRY)
        self.assertNotIn("process.env", ENTRY)
        self.assertIn("['initial-window', 'initial-prepare', 'initial-readback']", ACTION)
        self.assertIn("['GH_TOKEN', 'GITHUB_TOKEN', 'P2PKIT_ACTIONS_READ_TOKEN']", ACTION)
        self.assertNotIn("token:", YAML.lower())


if __name__ == "__main__":
    unittest.main(failfast=True)
