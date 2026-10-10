#!/usr/bin/env python3
"""NEW receiver N/B adapter models, not R/K/native/hosted qualification.

The actual shared N source12 proof, B native phase body and B guarded writer
run against explicitly declared in-memory suppliers. Only the small wrapper
ordering controls replace those shared bodies. The temporary R module is a
MODEL of the independently reviewed ABI, never the genuine R seed registry.
Actual R/K original-owner, argv, child, provider and timing proof is separate.

No credential, process, socket, native library, real clock or private evidence
file is used. Source reads below are static compatibility inputs, performed
before the per-call effect guard. No old test suite is imported or executed.
"""
from __future__ import annotations

from contextlib import ExitStack
import ctypes
import hashlib
import io
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED = False
EFFECTS = []


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen") or \
            GUARDED and event in ("open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        EFFECTS.append(event)
        raise AssertionError("PRODUCTIVE_NATIVE_ADAPTER_MODEL_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive_custody as PC

C, N, B, O, NS = PC.C, PC.N, PC.B, PC.O, PC.NS
REFUSALS = (ValueError, RuntimeError)  # Never swallow an effect-trap AssertionError.
H = "a" * 64
TOKEN = "MODEL_ONLY_NOT_A_CREDENTIAL_012345"
GIT = "/model/installed/git"
R_NAME = "hosted_initial_recipient_productive_receiver"
CONTEXTS = {
    "seal": "INITIAL_RECIPIENT_PRODUCTIVE_SEAL_AUTHORITY_CONTEXT_V1",
    "before": "INITIAL_RECIPIENT_PRODUCTIVE_BEFORE_AUTHORITY_CONTEXT_V1",
}
ACKS = {
    "seal": "INITIAL_RECIPIENT_PRODUCTIVE_SEAL_AUTHORITY_POST_CLOSE_ACK_V1",
    "before": "INITIAL_RECIPIENT_PRODUCTIVE_BEFORE_AUTHORITY_POST_CLOSE_ACK_V1",
    "tail": "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_POST_OWNER_CLOSE_ACK_V1",
}
SOURCE_BYTES = {name: (ROOT / "scripts" / name).read_bytes() for name in (
    "run-hosted-initial-recipient.py", "run-hosted-cache-bootstrap.py",
    "run-hosted-initial-recipient-custody.py", "hosted_initial_recipient_productive_custody.py",
    "hosted_initial_recipient_productive_custody_data.py")}
N_SOURCE = SOURCE_BYTES["run-hosted-initial-recipient.py"].decode("utf-8")
B_SOURCE = SOURCE_BYTES["run-hosted-cache-bootstrap.py"].decode("utf-8")
ACTUAL_PHASE_COMMAND = B.phase_command


def guarded(function, *args, **kwargs):
    global GUARDED
    prior, count = GUARDED, len(EFFECTS)
    GUARDED = True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = prior
        if len(EFFECTS) != count:
            raise AssertionError("PRODUCTIVE_NATIVE_ADAPTER_MODEL_EFFECT")


def source_definition(source, name):
    """Text slice only, including blank lines before the next top-level def."""
    begin = source.index("def " + name + "(")
    end = source.index("\ndef ", begin)
    return source[begin:end + 1].encode("utf-8")


class ModelCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.receiver = ModuleType(R_NAME, "Explicit adapter ABI model, NOT the actual R supplier")
        self.stack.enter_context(patch.dict(sys.modules, {R_NAME: self.receiver}))
        for name in ("_checked_authority_phase", "_checked_authority_phase_seed",
                     "_checked_native_authority_bridge", "_native_argv"):
            setattr(self.receiver, name, self.forbidden)
        self.install(O.clocks, "observe", self.forbidden)
        self.install(O.clocks, "checked_now", self.forbidden)
        self.install(B.time, "monotonic", self.forbidden)
        self.install(B.time, "sleep", self.forbidden)
        self.install(B.processes, "make_scope", self.forbidden)
        self.install(B, "child_environment", self.forbidden)
        self.install(B, "_installed_git_environment", self.forbidden)

    def forbidden(self, *_args, **_kwargs):
        raise AssertionError("UNMODELED_PRODUCTIVE_NATIVE_ADAPTER_EFFECT")

    def install(self, module, name, value):
        self.stack.enter_context(patch.object(module, name, value))
        return value

    def check(self, function, *args, **kwargs):
        return guarded(function, *args, **kwargs)

    def refuses(self, function, *args, **kwargs):
        with self.assertRaises(REFUSALS) as caught:
            self.check(function, *args, **kwargs)
        return caught.exception


class FixedWrapperModels(ModelCase):
    """Only these controls replace the shared body, to observe exact forwarding."""

    def setUp(self):
        super().setUp()
        self.seed, self.owner, self.private, self.fence, self.before = (object() for _index in range(5))
        self.raw, self.result, self.calls = b"model-context", object(), []

    def body(self, *args, **kwargs):
        self.calls.append(("body", args, kwargs))
        return self.result

    def n_gate(self, seed, owner, private, raw, fence, before, *, edge):
        self.calls.append(("gate", (seed, owner, private, raw, fence, before), edge))

    def b_gate(self, seed, owner, private, raw, fence, *, edge):
        self.calls.append(("gate", (seed, owner, private, raw, fence), edge))
        return seed

    def test_n_two_literal_edges_preserve_original_arguments_and_return(self):
        self.install(self.receiver, "_checked_authority_phase", self.n_gate)
        self.install(N, "_service_phase_owned", self.body)
        args = (self.seed, self.owner, self.private, self.raw, TOKEN, self.fence, self.before)
        for edge, call in (("seal", N._productive_seal_authority_phase),
                           ("before", N._productive_before_authority_phase)):
            self.calls.clear()
            self.assertIs(self.check(call, *args), self.result)
            self.assertEqual(self.calls, [
                ("gate", (self.seed, self.owner, self.private, self.raw, self.fence, self.before), edge),
                ("body", args[1:], {"receiver_seed": self.seed})])
            for actual, expected in zip(self.calls[0][1], (self.seed, self.owner, self.private,
                    self.raw, self.fence, self.before)):
                self.assertIs(actual, expected)
            for actual, expected in zip(self.calls[1][1], args[1:]):
                self.assertIs(actual, expected)

    def test_b_two_literal_edges_preserve_selected_git_and_return(self):
        self.install(self.receiver, "_checked_native_authority_bridge", self.b_gate)
        self.install(B, "_phase_owned", self.body)
        args = (self.seed, self.owner, self.private, self.raw, TOKEN, self.fence)
        for edge, call in (("seal", B.productive_seal_authority_phase),
                           ("before", B.productive_before_authority_phase)):
            self.calls.clear()
            self.assertIs(self.check(call, *args, initial_git=GIT), self.result)
            self.assertEqual(self.calls, [
                ("gate", (self.seed, self.owner, self.private, self.raw, self.fence), edge),
                ("body", args[1:], {"initial_git": GIT, "receiver_seed": self.seed})])
            for actual, expected in zip(self.calls[0][1], (self.seed, self.owner, self.private,
                    self.raw, self.fence)):
                self.assertIs(actual, expected)
            for actual, expected in zip(self.calls[1][1], args[1:]):
                self.assertIs(actual, expected)
            self.assertIs(self.calls[1][2]["initial_git"], GIT)

    def test_n_gate_failure_never_reaches_common_body(self):
        failure = O.OriginError("MODEL_N_GATE_REFUSED")
        def gate(*_args, **_kwargs):
            raise failure
        self.install(self.receiver, "_checked_authority_phase", gate)
        self.install(N, "_service_phase_owned", self.forbidden)
        for call in (N._productive_seal_authority_phase, N._productive_before_authority_phase):
            self.assertIs(self.refuses(call, self.seed, self.owner, self.private, self.raw,
                TOKEN, self.fence, self.before), failure)

    def test_b_gate_failure_never_reaches_common_body(self):
        failure = O.OriginError("MODEL_B_GATE_REFUSED")
        def gate(*_args, **_kwargs):
            raise failure
        self.install(self.receiver, "_checked_native_authority_bridge", gate)
        self.install(B, "_phase_owned", self.forbidden)
        for call in (B.productive_seal_authority_phase, B.productive_before_authority_phase):
            self.assertIs(self.refuses(call, self.seed, self.owner, self.private, self.raw,
                TOKEN, self.fence, initial_git=GIT), failure)

    def test_existing_n_final_selectors_still_forward_only_final_seed(self):
        def gate(*args, post):
            self.calls.append(("gate", args, post))
        self.install(PC, "_checked_authority_phase", gate)
        self.install(N, "_service_phase_owned", self.body)
        args = (self.seed, self.owner, self.private, self.raw, TOKEN, self.fence, self.before)
        for post, call in ((False, N._productive_authority_pre_phase),
                           (True, N._productive_authority_post_phase)):
            self.calls.clear()
            self.assertIs(self.check(call, *args), self.result)
            self.assertEqual(self.calls, [
                ("gate", (self.seed, self.owner, self.private, self.raw, self.fence, self.before), post),
                ("body", args[1:], {"final_seed": self.seed})])

    def test_existing_b_final_selectors_still_forward_only_final_seed(self):
        def gate(*args, post):
            self.calls.append(("gate", args, post))
        self.install(PC, "_checked_native_authority_bridge", gate)
        self.install(B, "_phase_owned", self.body)
        args = (self.seed, self.owner, self.private, self.raw, TOKEN, self.fence)
        for post, call in ((False, B.productive_pre_authority_phase),
                           (True, B.productive_post_authority_phase)):
            self.calls.clear()
            self.assertIs(self.check(call, *args, initial_git=GIT), self.result)
            self.assertEqual(self.calls, [
                ("gate", (self.seed, self.owner, self.private, self.raw, self.fence), post),
                ("body", args[1:], {"initial_git": GIT, "final_seed": self.seed})])

    def test_old_b_wrapper_cannot_synthesize_either_seed(self):
        self.install(B, "_phase_owned", self.body)
        args = (self.owner, self.private, self.raw, TOKEN, self.fence)
        self.assertIs(self.check(B.phase, *args, initial_git=GIT), self.result)
        self.assertEqual(self.calls, [("body", args, {"initial_git": GIT})])

    def test_existing_canonical_graph_is_not_the_legacy_before_module(self):
        self.assertIs(PC.P.C, C)
        self.assertIs(PC.P.N, N)
        self.assertIs(PC.P.B, B)
        self.assertIs(N.native, B)
        self.assertIs(C.native, B)
        self.assertIsNot(C.B, B)


class SourceTwelveModels(ModelCase):
    """Actual N shared body; genuine SourceReturn DTO in a MODEL owner registry.

    Four source records and twelve closed-query rows are distinct rosters. No
    query, readback, Git lookup or native B body is executed by this fixture.
    """

    def setUp(self):
        super().setUp()
        self.seed, self.fence, self.result = object(), object(), object()
        self.private = SimpleNamespace(path=Path("/model/native-adapter-session"))
        self.owner = SimpleNamespace(initial_sources={}, end=self.end)
        self.path = self.private.path / "source-before"
        self.events, self.ends, self.after_end = [], 0, None
        self.edge, self.reported_edge, self.revoked = "seal", None, False
        self.source, self.blob, self.job = "b" * 40, "c" * 40, "d" * 32
        self.clock = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
        self.records = (("base_policy_entry", b""), ("ancestry_raw", b"model-ancestry\n"),
            ("candidate_policy_entry", ("100644 blob " + self.blob + "\t" + N.I.POLICY_PATH + "\0").encode("ascii")),
            ("candidate_policy_raw", b"model-policy\n"))
        base = N.acquisition.stages.BASE["commit"]
        commands = (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
            ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", self.source + "^{tree}"),
            ("rev-parse", "--is-shallow-repository"), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
            ("rev-parse", "--verify", base + "^{tree}"), ("ls-tree", "-z", base, "--", N.I.POLICY_PATH),
            ("merge-base", base, self.source), ("ls-tree", "-z", self.source, "--", N.I.POLICY_PATH),
            ("cat-file", "-s", self.blob), ("cat-file", "blob", self.blob))
        self.session = {"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY", "job": self.job,
            "queries": [{"argv": [GIT, "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                "-C", str(N.ROOT), *command], "job": self.job, "state": str(self.path),
                "home": str(self.path / "query-home"), "cwd": str(N.ROOT), "launchAttempted": True,
                "scopeAttempted": True, "waitExitCode": 0, "retirement": "KNOWN",
                "result": "READY_FOR_CALLER_SEAL", "errors": [], "ownedSurvivors": []} for command in commands],
            "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN", "firstError": None,
            "errors": [], "readbacks": []}
        self.publish()
        self.install(self.receiver, "_checked_authority_phase_seed", self.gate)
        self.install(B, "productive_seal_authority_phase", self.seal)
        self.install(B, "productive_before_authority_phase", self.before_call)
        self.install(B, "phase", self.forbidden)
        self.install(B, "productive_pre_authority_phase", self.forbidden)
        self.install(B, "productive_post_authority_phase", self.forbidden)

    def publish(self):
        session_raw = N.Q.encoded(self.session)
        returned = {"schema": 1, "scope": N.SOURCE_SCOPE,
            "originalsSha256": {name: O.digest(raw) for name, raw in self.records},
            "sessionSha256": O.digest(session_raw), "clock": O.clock_value(self.clock), "returnedNs": 100 * NS}
        self.before = N.SourceReturn(self.records, session_raw, O.encoded(returned))
        self.owner.initial_sources[str(self.path)] = self.before
        self.context = {"scope": CONTEXTS[self.edge], "root": str(N.ROOT), "session": str(self.private.path),
            "sourceReturnSha256": O.digest(self.before.raw), "sourceReturnedNs": returned["returnedNs"],
            "observed": {"source": {"commit": self.source}}}
        self.raw = O.encoded(self.context)

    def context_changed(self, **changes):
        self.context.update(changes)
        self.raw = O.encoded(self.context)

    def end(self):
        self.ends += 1
        self.events.append(("end", self.ends))
        if self.after_end is not None:
            self.after_end(self.ends)

    def gate(self, seed, owner, private, raw, fence, before):
        self.events.append(("gate", self.ends))
        O.require(seed is self.seed and owner is self.owner and private is self.private and
            raw is self.raw and fence is self.fence and before is self.before and
            O.parse(raw)["scope"] == CONTEXTS[self.edge] and not self.revoked, "MODEL_R_ORIGINAL_GATE")
        return self.edge if self.reported_edge is None else self.reported_edge

    def dispatch(self, edge, *args, **kwargs):
        self.events.append(("dispatch", edge, args, kwargs))
        return self.result

    def seal(self, *args, **kwargs):
        return self.dispatch("seal", *args, **kwargs)

    def before_call(self, *args, **kwargs):
        return self.dispatch("before", *args, **kwargs)

    def run_body(self, **kwargs):
        return N._service_phase_owned(self.owner, self.private, self.raw, TOKEN, self.fence,
            self.before, **({"receiver_seed": self.seed} | kwargs))

    def no_dispatch(self):
        self.assertFalse(any(event[0] == "dispatch" for event in self.events))

    def test_both_edges_recheck_around_actual_source12_and_keep_selected_git(self):
        for edge in ("seal", "before"):
            self.edge, self.ends = edge, 0
            self.events.clear()
            self.publish()
            self.assertIs(self.check(self.run_body), self.result)
            self.assertEqual(self.events, [("gate", 0), ("end", 1), ("end", 2), ("gate", 2),
                ("dispatch", edge, (self.seed, self.owner, self.private, self.raw, TOKEN, self.fence),
                    {"initial_git": GIT})])
            self.assertIs(self.owner.initial_sources[str(self.path)], self.before)
            self.assertEqual(len(self.before.records), 4)
            self.assertEqual(len(self.session["queries"]), 12)

    def test_equal_source_return_is_not_the_registered_original(self):
        self.owner.initial_sources[str(self.path)] = N.SourceReturn(
            self.before.records, self.before.session, self.before.raw)
        self.assertIn("SERVICE_GIT_ORIGINAL", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_foreign_record_shaped_object_cannot_replace_source_return(self):
        self.before = SimpleNamespace(records=self.before.records, session=self.before.session, raw=self.before.raw)
        self.owner.initial_sources[str(self.path)] = self.before
        self.assertIn("SERVICE_GIT_ORIGINAL", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_exact_tuple_and_byte_record_types_are_required(self):
        for records in (list(self.records), tuple(reversed(self.records)),
                        ((*self.records[0][:1], bytearray()), *self.records[1:])):
            self.publish()
            object.__setattr__(self.before, "records", records)
            self.assertIn("SERVICE_GIT_ORIGINAL", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_all_twelve_rows_must_retain_one_original_executable(self):
        self.session["queries"][-1]["argv"][0] = "/model/other/git"
        self.publish()
        self.assertIn("SERVICE_GIT_QUERY", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_fixed_query_argv_cannot_be_changed_even_with_fresh_hash_joins(self):
        self.session["queries"][1]["argv"][-1] = "--untracked-files=no"
        self.publish()
        self.assertIn("SERVICE_GIT_QUERY", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_bool_exit_code_does_not_mean_actual_code_zero(self):
        self.session["queries"][4]["waitExitCode"] = False
        self.publish()
        self.assertIn("SERVICE_GIT_QUERY", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_unknown_query_retirement_or_survivor_is_not_repaired(self):
        row = self.session["queries"][7]
        row["retirement"] = "UNKNOWN"
        self.publish()
        self.assertIn("SERVICE_GIT_QUERY", str(self.refuses(self.run_body)))
        row["retirement"], row["ownedSurvivors"] = "KNOWN", [{"pid": 73}]
        self.publish()
        self.assertIn("SERVICE_GIT_QUERY", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_eleven_rows_cannot_stand_in_for_source12(self):
        self.session["queries"].pop()
        self.publish()
        self.assertIn("SERVICE_GIT_SESSION", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_noncanonical_original_session_is_rejected(self):
        session = self.before.session + b" "
        returned = O.parse(self.before.raw)
        returned["sessionSha256"] = O.digest(session)
        self.before = N.SourceReturn(self.records, session, O.encoded(returned))
        self.owner.initial_sources[str(self.path)] = self.before
        self.context_changed(sourceReturnSha256=O.digest(self.before.raw))
        self.refuses(self.run_body)
        self.no_dispatch()

    def test_return_record_original_hashes_cannot_be_replaced(self):
        returned = O.parse(self.before.raw)
        returned["originalsSha256"]["ancestry_raw"] = H
        self.before = N.SourceReturn(self.records, self.before.session, O.encoded(returned))
        self.owner.initial_sources[str(self.path)] = self.before
        self.context_changed(sourceReturnSha256=O.digest(self.before.raw))
        self.assertIn("SERVICE_GIT_RETURN", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_context_root_session_hash_and_strict_return_time_remain_required(self):
        for change in ({"root": "/model/foreign-root"}, {"session": "/model/foreign-session"},
                       {"sourceReturnSha256": H}, {"sourceReturnedNs": True}):
            self.publish()
            self.context_changed(**change)
            self.assertIn("SERVICE_GIT_CONTEXT", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_receiver_model_rejects_mismatched_literal_context_before_owner_end(self):
        self.context_changed(scope=CONTEXTS["before"])
        self.assertIn("MODEL_R_ORIGINAL_GATE", str(self.refuses(self.run_body)))
        self.assertEqual(self.events, [("gate", 0)])

    def test_changed_registry_at_first_end_is_not_an_original_source(self):
        def change(number):
            if number == 1:
                self.owner.initial_sources.clear()
        self.after_end = change
        self.assertIn("SERVICE_GIT_ORIGINAL", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_changed_original_bytes_at_second_end_fail_the_actual_pin(self):
        def change(number):
            if number == 2:
                object.__setattr__(self.before, "raw", self.before.raw + b" ")
        self.after_end = change
        self.assertIn("SERVICE_GIT_ORIGINAL_CHANGED", str(self.refuses(self.run_body)))
        self.assertEqual(self.events, [("gate", 0), ("end", 1), ("end", 2)])

    def test_changed_original_registry_at_second_end_fails_the_actual_pin(self):
        def change(number):
            if number == 2:
                self.owner.initial_sources[str(self.path)] = object()
        self.after_end = change
        self.assertIn("SERVICE_GIT_ORIGINAL_CHANGED", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_revoked_receiver_seed_is_rechecked_after_second_end(self):
        def change(number):
            if number == 2:
                self.revoked = True
        self.after_end = change
        self.assertIn("MODEL_R_ORIGINAL_GATE", str(self.refuses(self.run_body)))
        self.assertEqual(self.events, [("gate", 0), ("end", 1), ("end", 2), ("gate", 2)])

    def test_bad_receiver_edge_has_no_truthiness_or_fallback_dispatch(self):
        class StringSubclass(str):
            pass
        for edge in (False, "tail", StringSubclass("seal")):
            self.reported_edge = edge
            self.assertIn("SERVICE_GIT_RECEIVER_EDGE", str(self.refuses(self.run_body)))
        self.no_dispatch()

    def test_mixed_seeds_refuse_before_gate_or_owner_end(self):
        self.assertIn("SERVICE_GIT_EXCLUSIVE_SEED_ROUTE", str(self.refuses(self.run_body, final_seed=object())))
        self.assertEqual(self.events, [])

    def test_new_context_without_original_seed_is_not_shared_body_authority(self):
        self.assertIn("SERVICE_GIT_CONTEXT", str(self.refuses(self.run_body, receiver_seed=None)))
        self.assertEqual(self.events, [("end", 1)])

    def test_old_n_wrapper_does_not_admit_either_new_receiver_context(self):
        for edge in ("seal", "before"):
            self.edge = edge
            self.publish()
            self.assertIn("SERVICE_GIT_OLD_ROUTE", str(self.refuses(N._initial_service_phase, self.owner,
                self.private, self.raw, TOKEN, self.fence, self.before)))
        self.assertEqual(self.events, [])

    def test_old_n_route_keeps_the_actual_source12_proof_and_unseeded_dispatch(self):
        self.context_changed(scope=B.INITIAL_CONTEXT_SCOPE)
        self.install(B, "phase", lambda *args, **kwargs: self.dispatch("old", *args, **kwargs))
        self.assertIs(self.check(N._initial_service_phase, self.owner, self.private, self.raw,
            TOKEN, self.fence, self.before), self.result)
        self.assertEqual(self.events, [("end", 1), ("end", 2),
            ("dispatch", "old", (self.owner, self.private, self.raw, TOKEN, self.fence), {"initial_git": GIT})])

    def test_final_n_route_keeps_original_post_selector_and_selected_git(self):
        final_seed = object()
        self.context_changed(scope=PC.CD.AUTHORITY_POST_CONTEXT_SCOPE)
        def gate(seed, owner, private, raw, fence, before):
            self.assertEqual((seed, owner, private, raw, fence, before),
                (final_seed, self.owner, self.private, self.raw, self.fence, self.before))
            self.events.append(("final-gate", self.ends))
            return True
        self.install(PC, "_checked_authority_phase_seed", gate)
        self.install(B, "productive_post_authority_phase", lambda *args, **kwargs: self.dispatch("post", *args, **kwargs))
        self.assertIs(self.check(self.run_body, receiver_seed=None, final_seed=final_seed), self.result)
        self.assertEqual(self.events, [("end", 1), ("end", 2), ("final-gate", 2),
            ("dispatch", "post", (final_seed, self.owner, self.private, self.raw, TOKEN, self.fence),
                {"initial_git": GIT})])


class PhaseFenceModel:
    """Declared bounded readings/deadlines, not a real clock implementation."""

    def __init__(self, model):
        self.model = model
        self.clock = SimpleNamespace(role="linux-x64")
        self.work, self.final = 220 * NS, 280 * NS
        self.first, self.next = 110 * NS, 110 * NS
        self.now_calls, self.deadline_calls = [], []
        self.fail_now, self.failure, self.drain_failure = None, None, None
        self.capture_end, self.drain_end = 950.0, 925.0
        self.on_drain_deadline = None

    def now(self, *, final=False, minimum=0, limit=None):
        self.now_calls.append((final, minimum, limit, self.next))
        if self.failure is not None:
            raise self.failure
        if self.fail_now == len(self.now_calls):
            self.failure = O.OriginError("MODEL_ORIGINAL_FENCE_FAILED")
            raise self.failure
        bound = self.final if final else self.work
        if limit is not None:
            bound = min(bound, limit)
        if type(self.next) is not int or not minimum <= self.next < bound:
            self.failure = O.OriginError("MODEL_PHASE_FENCE_EXPIRED")
            raise self.failure
        value, self.next = self.next, self.next + 1
        return value

    def deadline(self, maximum, *, final=False, limit=None):
        self.deadline_calls.append((maximum, final, limit))
        if maximum == 45 and self.on_drain_deadline is not None:
            self.on_drain_deadline()
        if self.failure is not None:
            raise self.failure
        if maximum == 45 and self.drain_failure is not None:
            self.failure = self.drain_failure
            raise self.failure
        O.require(final is True and limit == self.model.phase[2], "MODEL_PHASE_DEADLINE_BINDING")
        O.require(maximum in (45, 90), "MODEL_PHASE_DEADLINE_MAXIMUM")
        return self.capture_end if maximum == 90 else self.drain_end


class CaptureModel:
    def __init__(self, model, name, maximum, deadline):
        self.model, self.name, self.maximum, self.deadline = model, name, maximum, deadline
        self.events, self.closed = [], False

    def sync(self):
        self.events.append("sync")
        if self.model.capture_failure is not None and self.name == "stdout":
            raise self.model.capture_failure

    def verify(self):
        O.require(not self.closed, "MODEL_CAPTURE_VERIFY_AFTER_CLOSE")
        self.events.append("verify")

    def observe_live_output(self):
        O.require(not self.closed, "MODEL_CAPTURE_OBSERVE_AFTER_CLOSE")
        self.events.append("observe")

    def close(self):
        O.require(not self.closed, "MODEL_CAPTURE_DOUBLE_CLOSE")
        self.events.append("close")
        self.closed = True


class DirectoryModel:
    def __init__(self, model, path):
        self.model, self.path, self.records = model, path, {}

    def create_file(self, name, *, max_bytes, deadline):
        O.require(name in ("stdout.log", "stderr.log"), "MODEL_UNEXPECTED_CAPTURE_FILE")
        stream = CaptureModel(self.model, name[:-4], max_bytes, deadline)
        self.model.captures[name[:-4]] = stream
        return stream


class ScopeModel:
    def __init__(self, model):
        self.model, self.baseline = model, {2, 1}
        self.spawn_calls, self.drain_calls = [], []
        self.closed, self.close_calls, self.poll_calls = False, 0, 0
        self.child = SimpleNamespace(pid=73, stdout=None, stderr=None, poll=self.poll)

    def spawn(self, argv, cwd, environment, *, stdout, stderr):
        self.spawn_calls.append((argv, cwd, dict(environment), stdout, stderr))
        self.model.environment_at_spawn = environment
        O.require(environment.get(O.wire.TOKEN_ENV) == TOKEN, "MODEL_EXPECTED_PRIVATE_TOKEN_AT_SPAWN")
        if self.model.spawn_failure is not None:
            raise self.model.spawn_failure
        return self.child

    def poll(self):
        self.poll_calls += 1
        return self.model.exit_code

    def description(self):
        return {"startedIdentities": [{"pid": 73, "startTicks": 7}],
            "discoveryErrors": self.model.discovery_errors}

    def discover(self):
        return self.model.descendants

    def drain(self, *, grace, kill_wait, deadline):
        self.drain_calls.append((grace, kill_wait, deadline))
        return self.model.survivors

    def close(self):
        self.close_calls += 1
        if self.model.scope_close_failure is not None:
            raise self.model.scope_close_failure
        O.require(not self.closed, "MODEL_SCOPE_DOUBLE_CLOSE")
        self.closed = True


class PhaseOwnerModel:
    """In-memory ledger and paired phase methods; NOT C/R's genuine owner."""

    def __init__(self, model):
        self.model = model
        self.work_limit, self.final_limit, self.local_end = model.fence.work, model.fence.final, 1000.0
        self.resources, self.errors, self.error_objects = [], [], []
        self.original, self.unknown, self.phase_originals = None, False, None
        self.entries, self.leaves, self.active = [], [], False

    def enter(self, route, seed, raw, started, work, final):
        self.entries.append((route, seed, raw, started, work, final))
        expected = self.model.seed if route == "receiver" else self.model.final_seed
        O.require(seed is expected and raw is self.model.raw and not self.active, "MODEL_ORIGINAL_PHASE_ENTRY")
        self.model.phase = (started, work, final)
        self.model.old_limits = (self.work_limit, self.final_limit)
        self.work_limit, self.final_limit, self.active = work, final, True

    def enter_receiver_phase(self, seed, raw, started, work, final):
        self.enter("receiver", seed, raw, started, work, final)

    def enter_final_productive_phase(self, seed, raw, started, work, final):
        self.enter("final", seed, raw, started, work, final)

    def leave(self, route, started, work, final, old_limits):
        self.leaves.append((route, started, work, final, old_limits))
        O.require(self.active and (started, work, final) == self.model.phase and
            old_limits == self.model.old_limits, "MODEL_ORIGINAL_PHASE_LEAVE")
        if self.model.restore_failure is not None:
            raise self.model.restore_failure
        self.work_limit, self.final_limit = old_limits
        self.active = False

    def leave_receiver_phase(self, started, work, final, old_limits):
        self.leave("receiver", started, work, final, old_limits)

    def leave_final_productive_phase(self, started, work, final, old_limits):
        self.leave("final", started, work, final, old_limits)

    def error(self, stage, error, *, unknown=False):
        self.errors.append({"stage": stage, "modelErrorType": type(error).__name__})
        self.error_objects.append((stage, error, unknown))
        if self.original is None:
            self.original = error
        self.unknown |= unknown

    def child(self, parent, name, *, create=False):
        O.require(parent is self.model.private and name == "service" and create is True,
            "MODEL_FIXED_SERVICE_DIRECTORY")
        self.resources.append({"label": "directory", "owner": self.model.directory,
            "attempted": False, "closed": False})
        return self.model.directory

    def write(self, directory, name, value, *, final=False):
        O.require(directory is self.model.directory, "MODEL_PHASE_RECORD_DIRECTORY")
        self.model.writes.append((name, final))
        if name == self.model.write_failure_name:
            raise self.model.write_failure
        raw = value if type(value) is bytes else O.encoded(value)
        directory.records[name] = raw
        if self.model.after_write is not None:
            self.model.after_write(name)
        return raw

    def read(self, directory, name, maximum, *, final=False):
        O.require(directory is self.model.directory and name in ("stdout.log", "stderr.log") and final is True,
            "MODEL_PHASE_CAPTURE_READBACK")
        self.model.reads.append((name, maximum, final))
        capture = self.model.captures[name[:-4]]
        O.require(capture.closed, "MODEL_CAPTURE_READBACK_BEFORE_CLOSE")
        if self.model.read_failure is not None:
            raise self.model.read_failure
        raw = b"model-child-stdout\n" if name == "stdout.log" else self.model.stderr
        O.require(len(raw) <= maximum, "MODEL_CAPTURE_READBACK_BOUND")
        directory.records[name] = raw
        return raw

    def acquire(self, label, factory):
        value = factory()
        O.require(not any(row["owner"] is value for row in self.resources), "MODEL_DUPLICATE_RESOURCE")
        self.resources.append({"label": label, "owner": value, "attempted": False, "closed": False})
        if label == self.model.acquire_failure_label:
            raise self.model.acquire_failure
        return value

    def close_one(self, value):
        row = next(row for row in self.resources if row["owner"] is value)
        if row["attempted"]:
            return
        row["attempted"] = True
        try:
            value.close()
            row["closed"] = True
        except BaseException as error:
            self.error(row["label"] + "-close", error, unknown=True)


class NativeFixture:
    """All live B suppliers are named models; B._phase_owned itself is untouched."""

    def __init__(self, case):
        self.case, self.seed, self.final_seed = case, object(), object()
        self.edge, self.route = "seal", "receiver"
        self.context = {"scope": CONTEXTS[self.edge], "job": "d" * 32}
        self.raw = O.encoded(self.context)
        self.phase, self.old_limits = None, None
        self.fence = PhaseFenceModel(self)
        self.owner = PhaseOwnerModel(self)
        self.private = SimpleNamespace(path=Path("/model/native-adapter-phase"))
        self.directory = DirectoryModel(self, self.private.path / "service")
        self.scope = ScopeModel(self)
        self.captures, self.argv_calls, self.argv_returns, self.gates = {}, [], [], []
        self.writes, self.reads, self.env_calls, self.scope_calls, self.local_checks = [], [], [], [], []
        self.environment, self.environment_at_spawn = None, None
        self.local_now = 100.0
        self.setup_failure, self.launch_argv_failure, self.environment_failure = None, None, None
        self.restore_failure, self.spawn_failure, self.scope_close_failure = None, None, None
        self.capture_failure, self.read_failure = None, None
        self.write_failure_name, self.write_failure = None, None
        self.after_write = None
        self.acquire_failure_label, self.acquire_failure = None, None
        self.exit_code, self.descendants, self.discovery_errors, self.survivors, self.stderr = 0, [], [], [], b""
        case.install(case.receiver, "_checked_native_authority_bridge", self.gate)
        case.install(case.receiver, "_native_argv", self.receiver_argv)
        case.install(PC, "_native_argv", case.forbidden)
        case.install(B, "phase_command", case.forbidden)
        case.install(B, "_initial_service_environment", case.forbidden)
        case.install(B, "child_environment", self.child_environment)
        case.install(B, "_installed_git_environment", self.installed_environment)
        case.install(B.processes, "ownership_environment", self.ownership_environment)
        case.install(B.processes, "make_scope", self.make_scope)
        case.install(B, "preparer_identity", self.preparer_identity)
        case.install(B.uuid, "uuid4", lambda: SimpleNamespace(hex="e" * 32))
        case.install(B.time, "monotonic", lambda: self.local_now)
        case.install(B.posix, "_deadline", self.local_deadline)

    def set_edge(self, edge):
        self.edge = edge
        self.context["scope"] = CONTEXTS[edge]
        self.raw = O.encoded(self.context)

    def gate(self, seed, owner, private, raw, fence, *, edge):
        self.gates.append((seed, owner, private, raw, fence, edge))
        O.require(seed is self.seed and owner is self.owner and private is self.private and raw is self.raw and
            fence is self.fence and edge == self.edge and O.parse(raw)["scope"] == CONTEXTS[edge],
            "MODEL_ORIGINAL_NATIVE_BRIDGE")
        return seed

    def argv(self, route, seed, raw, phase, minimum=None):
        self.argv_calls.append((route, seed, raw, phase, minimum))
        O.require(seed is (self.seed if route == "receiver" else self.final_seed) and raw is self.raw and
            phase == self.phase and self.owner.active, "MODEL_REGISTERED_NATIVE_ARGV")
        if minimum is None and self.setup_failure is not None:
            raise self.setup_failure
        if minimum is not None:
            O.require(type(minimum) is int and phase[0] <= minimum < phase[1], "MODEL_NATIVE_MINIMUM")
            if self.launch_argv_failure is not None:
                raise self.launch_argv_failure
        # Deliberately not a copy of R._command: only adapter forwarding is under test.
        argv = ["MODEL_NOT_EXECUTABLE", route, self.edge, "pending" if minimum is None else str(minimum)]
        self.argv_returns.append(argv)
        return argv

    def receiver_argv(self, seed, raw, phase, minimum=None):
        return self.argv("receiver", seed, raw, phase, minimum)

    def final_argv(self, seed, raw, phase, minimum=None):
        return self.argv("final", seed, raw, phase, minimum)

    def child_environment(self, path):
        self.env_calls.append(("child", path))
        O.require(path == self.private.path, "MODEL_CHILD_ENVIRONMENT_PATH")
        if self.environment_failure is not None:
            raise self.environment_failure
        return {name: "model-" + str(index) for index, name in enumerate(B.query._CONTEXT)}

    def installed_environment(self, environment, selected):
        self.env_calls.append(("installed", selected))
        O.require(selected == GIT and O.wire.TOKEN_ENV not in environment, "MODEL_ORIGINAL_GIT_ENVIRONMENT")
        environment["PATH"] = "/model/installed"
        return environment

    def ownership_environment(self, environment, job, invocation, state, home, *, allow_new_context):
        self.env_calls.append(("ownership", job, invocation, state, home, allow_new_context))
        O.require(job == self.context["job"] and invocation == "e" * 32 and state == str(self.private.path) and
            home == str(self.private.path / "control-home") and allow_new_context is True,
            "MODEL_ORIGINAL_OWNERSHIP_ENVIRONMENT")
        self.environment = dict(environment)
        return self.environment

    def make_scope(self, job, invocation, state, home):
        self.scope_calls.append((job, invocation, state, home))
        return self.scope

    def preparer_identity(self, scope, role):
        O.require(scope is self.scope and role == "linux-x64", "MODEL_ORIGINAL_PREPARER")
        return {"pid": 71, "startTicks": 5}

    def local_deadline(self, deadline):
        self.local_checks.append(deadline)
        O.require(self.local_now < deadline, "MODEL_LOCAL_CEILING_EXPIRED")

    def call(self):
        fixed = B.productive_seal_authority_phase if self.edge == "seal" else B.productive_before_authority_phase
        return fixed(self.seed, self.owner, self.private, self.raw, TOKEN, self.fence, initial_git=GIT)

    def body(self, **kwargs):
        return B._phase_owned(self.owner, self.private, self.raw, TOKEN, self.fence,
            initial_git=GIT, **({"receiver_seed": self.seed} | kwargs))


class NativeBodyModels(ModelCase):
    def setUp(self):
        super().setUp()
        self.model = NativeFixture(self)

    def no_original(self):
        self.assertIsNone(self.model.owner.phase_originals)
        if self.model.environment is not None:
            self.assertNotIn(O.wire.TOKEN_ENV, self.model.environment)

    def restored(self, route="receiver"):
        model = self.model
        self.assertEqual(model.owner.leaves, [(route, *model.phase, model.old_limits)])
        self.assertEqual((model.owner.work_limit, model.owner.final_limit), model.old_limits)
        self.assertFalse(model.owner.active)

    def successful_body(self):
        model = self.model
        directory, original = self.check(model.call)
        self.assertIs(directory, model.directory)
        self.assertIs(type(original), B.OriginalPhase)
        self.assertIs(model.owner.phase_originals, original)
        self.assertIs(original.context, model.raw)
        records = dict(original.records)
        self.assertEqual(set(records), B.PHASE_FILES)
        self.assertEqual(records, model.directory.records)
        start, result = O.parse(records["start.json"]), O.parse(records["result.json"])
        self.assertEqual(model.phase, (110 * NS, 155 * NS, 200 * NS))
        self.assertEqual(model.owner.entries, [("receiver", model.seed, model.raw, *model.phase)])
        self.assertEqual(model.argv_calls, [
            ("receiver", model.seed, model.raw, model.phase, None),
            ("receiver", model.seed, model.raw, model.phase, result["launchMinimumNs"])])
        self.assertEqual(result["launchMinimumNs"], model.fence.now_calls[2][3])
        self.assertEqual(start["argv"], model.argv_returns[0])
        self.assertEqual(result["launchArgv"], model.argv_returns[1])
        spawn = model.scope.spawn_calls[0]
        self.assertIs(spawn[0], model.argv_returns[1])
        self.assertEqual(spawn[1], str(B.ROOT))
        self.assertEqual(spawn[2][O.wire.TOKEN_ENV], TOKEN)
        self.assertIs(model.environment_at_spawn, model.environment)
        self.assertNotIn(O.wire.TOKEN_ENV, model.environment)
        self.assertEqual([event[0] for event in model.env_calls], ["child", "installed", "ownership"])
        self.assertEqual(model.env_calls[1], ("installed", GIT))
        self.assertEqual(model.fence.deadline_calls, [(90, True, model.phase[2]), (45, True, model.phase[2])])
        self.assertEqual(model.scope.drain_calls, [(5, 5, model.fence.drain_end)])
        self.assertEqual(model.reads, [("stdout.log", B.ACK_LIMIT, True), ("stderr.log", B.STDERR_LIMIT, True)])
        for name, maximum in (("stdout", B.ACK_LIMIT), ("stderr", B.STDERR_LIMIT)):
            capture = model.captures[name]
            self.assertEqual((capture.maximum, capture.deadline), (maximum, model.fence.capture_end))
            self.assertEqual(capture.events, ["verify", "sync", "verify", "close"])
            self.assertEqual(result["captureOutcomes"][name], {"synced": True, "verified": True,
                "closeAttempted": True, "closed": True, "readback": True})
        self.assertTrue(all(row["attempted"] and row["closed"] for row in model.owner.resources
            if row["label"] in ("stdout", "stderr", "native-scope")))
        self.assertTrue(model.scope.closed)
        self.assertEqual(result["retirement"], "KNOWN")
        self.assertEqual(result["exitCode"], 0)
        self.assertEqual(model.owner.errors, [])
        self.restored()

    def test_seal_uses_actual_shared_body_original_return_and_known_capture_close(self):
        self.successful_body()

    def test_before_uses_same_actual_body_with_separate_literal_gate(self):
        self.model.set_edge("before")
        self.successful_body()
        self.assertEqual(self.model.gates[-1][-1], "before")

    def test_original_work_final_caps_shorten_both_receiver_argv_observations(self):
        model = self.model
        model.fence.work, model.fence.final = 130 * NS, 160 * NS
        model.owner.work_limit, model.owner.final_limit = model.fence.work, model.fence.final
        self.check(model.call)
        self.assertEqual(model.phase, (110 * NS, 130 * NS, 160 * NS))
        self.assertEqual([call[3] for call in model.argv_calls], [model.phase, model.phase])
        self.assertTrue(all(call[2] in (None, model.phase[1], model.phase[2]) for call in model.fence.now_calls))
        self.restored()

    def test_original_local_ceiling_clips_capture_and_drain_without_extension(self):
        model = self.model
        model.fence.capture_end, model.fence.drain_end = 1200.0, 1100.0
        self.check(model.call)
        self.assertEqual({capture.deadline for capture in model.captures.values()}, {1000.0})
        self.assertEqual(model.scope.drain_calls, [(5, 5, 1000.0)])

    def test_mixed_native_seeds_refuse_before_clock_or_owner_entry(self):
        model = self.model
        self.assertIn("BOOTSTRAP_EXCLUSIVE_SEED_ROUTE", str(self.refuses(model.body, final_seed=model.final_seed)))
        self.assertEqual(model.fence.now_calls, [])
        self.assertEqual(model.owner.entries, [])
        self.assertEqual(model.argv_calls, [])
        self.assertEqual(model.owner.resources, [])
        self.no_original()

    def test_receiver_context_text_without_seed_hits_unchanged_old_selector_refusal(self):
        self.install(B, "phase_command", ACTUAL_PHASE_COMMAND)
        self.assertIn("BOOTSTRAP_SERVICE_CONTEXT_SCOPE", str(self.refuses(self.model.body, receiver_seed=None)))
        self.assertEqual(self.model.owner.entries, [])
        self.assertEqual(self.model.owner.resources, [])
        self.assertEqual(self.model.argv_calls, [])
        self.no_original()

    def test_foreign_seed_is_rejected_at_literal_gate_before_native_clock(self):
        model = self.model
        self.assertIn("MODEL_ORIGINAL_NATIVE_BRIDGE", str(self.refuses(B.productive_seal_authority_phase,
            object(), model.owner, model.private, model.raw, TOKEN, model.fence, initial_git=GIT)))
        self.assertEqual(model.fence.now_calls, [])
        self.no_original()

    def test_foreign_seed_direct_body_still_cannot_enter_model_original_owner(self):
        self.assertIn("MODEL_ORIGINAL_PHASE_ENTRY", str(self.refuses(self.model.body, receiver_seed=object())))
        self.assertEqual(self.model.owner.resources, [])
        self.assertEqual(self.model.argv_calls, [])
        self.no_original()

    def test_setup_argv_failure_leaves_entered_phase_and_keeps_first_error(self):
        model = self.model
        first = model.setup_failure = O.OriginError("MODEL_PENDING_ARGV_FAILED")
        self.assertIs(self.refuses(model.call), first)
        self.assertIs(model.owner.original, first)
        self.assertEqual(model.owner.error_objects, [("productive-receiver-phase-setup", first, False)])
        self.assertEqual(model.owner.resources, [])
        self.restored()
        self.no_original()

    def test_setup_environment_failure_has_same_paired_restore(self):
        first = self.model.environment_failure = O.OriginError("MODEL_ENVIRONMENT_FAILED")
        self.assertIs(self.refuses(self.model.call), first)
        self.assertEqual(self.model.scope_calls, [])
        self.restored()
        self.no_original()

    def test_setup_start_record_failure_does_not_launch_or_capture(self):
        model = self.model
        model.write_failure_name = "start.json"
        first = model.write_failure = O.OriginError("MODEL_START_WRITE_FAILED")
        self.assertIs(self.refuses(model.call), first)
        self.assertEqual(model.captures, {})
        self.assertEqual(model.scope_calls, [])
        self.restored()
        self.no_original()

    def test_setup_restore_failure_is_unknown_without_replacing_primary_error(self):
        model = self.model
        first = model.setup_failure = O.OriginError("MODEL_SETUP_FIRST")
        later = model.restore_failure = O.OriginError("MODEL_SETUP_RESTORE_FAILED")
        self.assertIs(self.refuses(model.call), first)
        self.assertIs(model.owner.original, first)
        self.assertTrue(model.owner.unknown)
        self.assertEqual(model.owner.error_objects, [("productive-receiver-phase-setup", first, False),
            ("productive-receiver-phase-setup-return", later, True)])
        self.assertEqual(len(model.owner.leaves), 1)
        self.no_original()

    def test_failed_original_launch_clock_clears_token_and_drains_owned_scope_only(self):
        model = self.model
        model.fence.fail_now = 3
        self.assertIs(self.refuses(model.call), model.fence.failure)
        self.assertIs(model.owner.original, model.fence.failure)
        self.assertEqual(len(model.argv_calls), 1)
        self.assertEqual(model.scope.spawn_calls, [])
        self.assertEqual(model.scope.drain_calls, [(5, 5, model.fence.capture_end)])
        self.assertTrue(model.scope.closed)
        self.assertTrue(model.owner.unknown)
        self.assertTrue(all(not capture.closed for capture in model.captures.values()))
        self.restored()
        self.no_original()

    def test_pre_scope_work_check_failure_never_attempts_native_allocation(self):
        model = self.model
        model.fence.fail_now = 2
        self.assertIs(self.refuses(model.call), model.fence.failure)
        self.assertEqual(model.scope_calls, [])
        self.assertEqual(model.scope.drain_calls, [])
        self.restored()
        self.no_original()

    def test_launch_at_exact_phase_work_end_refuses_without_borrowing_final45(self):
        model = self.model
        def late(name):
            if name == "baseline.json":
                model.fence.next = model.phase[1]
        model.after_write = late
        self.assertIn("MODEL_PHASE_FENCE_EXPIRED", str(self.refuses(model.call)))
        self.assertEqual(model.fence.now_calls[2][2:], (model.phase[1], model.phase[1]))
        self.assertLess(model.phase[1], model.phase[2])
        self.assertEqual(model.scope.spawn_calls, [])
        self.assertIs(model.owner.original, model.fence.failure)
        self.restored()
        self.no_original()

    def test_actual_launch_argv_failure_cannot_fall_back_to_old_or_pc_selectors(self):
        first = self.model.launch_argv_failure = O.OriginError("MODEL_LAUNCH_ARGV_FAILED")
        self.assertIs(self.refuses(self.model.call), first)
        self.assertEqual(len(self.model.argv_calls), 2)
        self.assertEqual(self.model.scope.spawn_calls, [])
        self.assertTrue(self.model.scope.closed)
        self.restored()
        self.no_original()

    def test_spawn_failure_removes_token_and_preserves_original_error(self):
        first = self.model.spawn_failure = O.OriginError("MODEL_SPAWN_FAILED")
        self.assertIs(self.refuses(self.model.call), first)
        self.assertEqual(len(self.model.scope.spawn_calls), 1)
        self.assertTrue(self.model.scope.closed)
        self.restored()
        self.no_original()

    def test_nonzero_child_is_retained_but_never_an_original_phase(self):
        model = self.model
        model.exit_code = 9
        self.assertIn("BOOTSTRAP_SERVICE_CHILD_FAILED", str(self.refuses(model.call)))
        self.assertEqual(O.parse(model.directory.records["result.json"])["exitCode"], 9)
        self.assertTrue(model.scope.closed)
        self.restored()
        self.no_original()

    def test_bool_child_code_is_not_integer_native_zero(self):
        self.model.exit_code = False
        self.assertIn("BOOTSTRAP_SERVICE_CHILD_FAILED", str(self.refuses(self.model.call)))
        self.assertIs(O.parse(self.model.directory.records["result.json"])["exitCode"], False)
        self.no_original()

    def test_left_descendant_is_not_erased_by_later_empty_drain(self):
        self.model.descendants = [{"pid": 74}]
        self.assertIn("BOOTSTRAP_SERVICE_LEFT_DESCENDANTS", str(self.refuses(self.model.call)))
        self.assertEqual(len(self.model.scope.drain_calls), 1)
        self.assertTrue(self.model.scope.closed)
        self.no_original()

    def test_discovery_unknown_prevents_capture_readback_and_success(self):
        self.model.discovery_errors = ["model-discovery-unknown"]
        self.assertIn("BOOTSTRAP_SERVICE_DISCOVERY_UNKNOWN", str(self.refuses(self.model.call)))
        self.assertTrue(self.model.owner.unknown)
        self.assertEqual(self.model.reads, [])
        self.assertTrue(self.model.scope.closed)
        self.no_original()

    def test_survivors_keep_native_retirement_unknown(self):
        self.model.survivors = [{"pid": 74}]
        self.assertIn("BOOTSTRAP_SERVICE_SURVIVORS", str(self.refuses(self.model.call)))
        self.assertTrue(self.model.owner.unknown)
        self.assertEqual(self.model.reads, [])
        self.no_original()

    def test_capture_sync_failure_still_attempts_both_known_closes(self):
        model = self.model
        first = model.capture_failure = O.OriginError("MODEL_CAPTURE_SYNC_FAILED")
        self.assertIs(self.refuses(model.call), first)
        result = O.parse(model.directory.records["result.json"])
        self.assertFalse(result["captureOutcomes"]["stdout"]["synced"])
        self.assertFalse(result["captureOutcomes"]["stdout"]["verified"])
        self.assertTrue(all(capture.closed for capture in model.captures.values()))
        self.restored()
        self.no_original()

    def test_capture_readback_failure_cannot_be_replaced_by_provisional_row(self):
        first = self.model.read_failure = O.OriginError("MODEL_CAPTURE_READBACK_FAILED")
        self.assertIs(self.refuses(self.model.call), first)
        self.assertTrue(all(capture.closed for capture in self.model.captures.values()))
        self.assertFalse(O.parse(self.model.directory.records["result.json"])["captureOutcomes"]["stdout"]["readback"])
        self.no_original()

    def test_nonempty_stderr_refuses_after_actual_modeled_readback(self):
        self.model.stderr = b"model-child-error\n"
        self.assertIn("BOOTSTRAP_SERVICE_NOT_ACCEPTED", str(self.refuses(self.model.call)))
        self.assertEqual(len(self.model.reads), 2)
        self.no_original()

    def test_scope_close_failure_is_unknown_and_does_not_certify_captures(self):
        first = self.model.scope_close_failure = O.OriginError("MODEL_SCOPE_CLOSE_FAILED")
        self.assertIs(self.refuses(self.model.call), first)
        self.assertTrue(self.model.owner.unknown)
        self.assertEqual(self.model.scope.close_calls, 1)
        self.assertEqual(self.model.reads, [])
        self.no_original()

    def test_receiver_restore_failure_blocks_success_after_provisional_result(self):
        first = self.model.restore_failure = O.OriginError("MODEL_RECEIVER_RESTORE_FAILED")
        self.assertIs(self.refuses(self.model.call), first)
        self.assertTrue(self.model.owner.unknown)
        self.assertIn("result.json", self.model.directory.records)
        self.assertEqual(self.model.owner.error_objects[-1], ("productive-receiver-phase-return", first, True))
        self.no_original()

    def test_later_restore_failure_does_not_replace_first_capture_failure(self):
        model = self.model
        first = model.capture_failure = O.OriginError("MODEL_CAPTURE_FIRST")
        later = model.restore_failure = O.OriginError("MODEL_RESTORE_LATER")
        self.assertIs(self.refuses(model.call), first)
        self.assertIs(model.owner.original, first)
        self.assertEqual(model.owner.error_objects[-1], ("productive-receiver-phase-return", later, True))
        self.assertTrue(model.owner.unknown)
        self.no_original()

    def test_failed_fence_drain_uses_only_retained_capture_and_shorter_local_ceiling(self):
        model = self.model
        first = model.fence.drain_failure = O.OriginError("MODEL_DRAIN_FENCE_FAILED")
        model.fence.capture_end, model.local_now = 501.0, 497.0
        model.fence.on_drain_deadline = lambda: setattr(model.owner, "local_end", 499.0)
        self.assertIs(self.refuses(model.call), first)
        self.assertEqual(model.scope.drain_calls, [(2.0, 0, 499.0)])
        self.assertEqual(model.fence.deadline_calls, [(90, True, model.phase[2]), (45, True, model.phase[2])])
        self.assertTrue(model.owner.unknown)
        self.assertTrue(model.scope.closed)
        self.restored()
        self.no_original()

    def test_invalid_retained_cleanup_ceiling_never_creates_a_fresh_deadline(self):
        model = self.model
        first = model.fence.drain_failure = O.OriginError("MODEL_DRAIN_CLOCK_FIRST")
        model.fence.on_drain_deadline = lambda: setattr(model.owner, "local_end", 0.0)
        self.assertIs(self.refuses(model.call), first)
        self.assertEqual(model.scope.drain_calls, [])
        self.assertEqual(len(model.fence.deadline_calls), 2)
        self.assertTrue(model.owner.unknown)
        self.assertTrue(model.scope.closed)
        self.no_original()

    def test_registered_scope_with_failed_allocation_return_is_still_closed_once(self):
        model = self.model
        model.acquire_failure_label = "native-scope"
        first = model.acquire_failure = O.OriginError("MODEL_AFTER_SCOPE_REGISTRATION_FAILED")
        self.assertIs(self.refuses(model.call), first)
        self.assertEqual(len(model.scope_calls), 1)
        self.assertEqual(model.scope.close_calls, 1)
        self.assertTrue(model.scope.closed)
        self.assertEqual(len(model.scope.drain_calls), 1)
        self.no_original()

    def test_duplicate_original_return_is_never_overwritten(self):
        previous = self.model.owner.phase_originals = object()
        self.assertIn("BOOTSTRAP_DUPLICATE_ORIGINAL_PHASE", str(self.refuses(self.model.call)))
        self.assertIs(self.model.owner.phase_originals, previous)
        self.assertNotIn(O.wire.TOKEN_ENV, self.model.environment)

    def test_final_seed_still_uses_pc_entry_argv_restore_not_receiver(self):
        model = self.model
        model.context["scope"] = PC.CD.AUTHORITY_PRE_CONTEXT_SCOPE
        model.raw = O.encoded(model.context)
        self.install(self.receiver, "_native_argv", self.forbidden)
        self.install(PC, "_native_argv", model.final_argv)
        directory, original = self.check(model.body, receiver_seed=None, final_seed=model.final_seed)
        self.assertIs(directory, model.directory)
        self.assertIs(model.owner.phase_originals, original)
        self.assertEqual(model.owner.entries, [("final", model.final_seed, model.raw, *model.phase)])
        self.assertEqual([call[0] for call in model.argv_calls], ["final", "final"])
        self.assertEqual(model.gates, [])
        self.restored("final")

    def test_old_route_still_uses_only_legacy_command_and_environment(self):
        model = self.model
        model.context["scope"] = B.INITIAL_CONTEXT_SCOPE
        model.raw = O.encoded(model.context)
        model.phase = (110 * NS, 155 * NS, 200 * NS)
        calls = []
        def old_command(raw, minimum=None):
            self.assertIs(raw, model.raw)
            calls.append(("argv", minimum))
            return ["MODEL_OLD_NOT_EXECUTABLE", "pending" if minimum is None else str(minimum)]
        def old_environment(path, context, installed):
            calls.append(("environment", path, context, installed))
            return model.child_environment(path)
        self.install(B, "phase_command", old_command)
        self.install(B, "_initial_service_environment", old_environment)
        directory, original = self.check(model.body, receiver_seed=None)
        self.assertIs(directory, model.directory)
        self.assertIs(model.owner.phase_originals, original)
        self.assertEqual(model.owner.entries, [])
        self.assertEqual(model.owner.leaves, [])
        self.assertEqual(model.argv_calls, [])
        self.assertEqual([call[0] for call in calls], ["argv", "environment", "argv"])
        self.assertEqual(calls[1], ("environment", model.private.path, model.context, GIT))
        self.assertEqual(calls[2], ("argv", model.fence.now_calls[2][3]))
        self.assertEqual((model.owner.work_limit, model.owner.final_limit), (model.fence.work, model.fence.final))


class AckFenceModel:
    """Same original strict work fence; deadline reconstruction is an effect trap."""

    def __init__(self):
        self.clock = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
        self.work, self.final = 170 * NS, 215 * NS
        self.values, self.calls = [150 * NS, 151 * NS], []

    def now(self, *, final=False, limit=None):
        index = len(self.calls)
        self.calls.append((final, limit))
        O.require(index < 2 and final is True and limit == self.work, "MODEL_ACK_ORIGINAL_WORK_ONLY")
        value = self.values[index]
        O.require(type(value) is int and value < self.work, "MODEL_ACK_WORK_EXPIRED")
        return value

    def deadline(self, *_args, **_kwargs):
        raise AssertionError("MODEL_ACK_MUST_NOT_RENEW_DEADLINE")


class AckBufferModel(io.BytesIO):
    def __init__(self, events):
        super().__init__()
        self.events = events
        self.short, self.write_failure, self.flush_failure, self.after_flush = False, None, None, None

    def write(self, raw):
        self.events.append("write")
        if self.write_failure is not None:
            raise self.write_failure
        count = super().write(raw)
        return count - 1 if self.short else count

    def flush(self):
        self.events.append("flush")
        if self.flush_failure is not None:
            raise self.flush_failure
        if self.after_flush is not None:
            self.after_flush()
        return super().flush()


class GuardedAckModels(ModelCase):
    """Actual B.guarded, with only signals/stdout and original work observations modeled."""

    def setUp(self):
        super().setUp()
        self.events, self.signals, self.cancelled = [], [], None
        self.fence = AckFenceModel()
        self.output = AckBufferModel(self.events)
        self.addCleanup(self.output.close)
        self.numbers = (B.signal.SIGINT, B.signal.SIGTERM,
            *([B.signal.SIGBREAK] if hasattr(B.signal, "SIGBREAK") else []))
        self.original_handlers = {number: object() for number in self.numbers}
        self.handlers = dict(self.original_handlers)
        self.install(B.signal, "getsignal", lambda number: self.handlers[number])
        self.install(B.signal, "signal", self.set_signal)
        self.install(B.sys, "stdout", SimpleNamespace(buffer=self.output))
        self.value = self.ack("seal")

    def ack(self, edge):
        value = {"schema": 1, "scope": ACKS[edge], "invocation": "f" * 32,
            "terminalSha256": H, "clock": O.clock_value(self.fence.clock), "closedNs": 140 * NS}
        if edge == "tail":
            value.update(ownerCloseSha256="b" * 64, metadataResourceCount=3, operativeResourceCount=7)
        return value

    def set_signal(self, number, handler):
        self.signals.append((number, handler))
        previous, self.handlers[number] = self.handlers[number], handler
        return previous

    def operation(self, cancelled):
        self.cancelled = cancelled
        self.events.append("operation")
        return self.value, self.fence, self.fence.work

    def call(self):
        return B.guarded(self.operation)

    def correct_ack(self, edge):
        self.value = self.ack(edge)
        original = dict(self.value)
        self.assertIsNone(self.check(self.call))
        written = O.parse(self.output.getvalue())
        self.assertEqual(set(written), set(original))
        self.assertEqual(len(written), 9 if edge == "tail" else 6)
        original["closedNs"] = self.fence.values[0]
        self.assertEqual(written, original)
        self.assertEqual(self.fence.calls, [(True, self.fence.work), (True, self.fence.work)])
        self.assertEqual(self.events, ["operation", "write", "flush"])
        self.assertEqual(self.handlers, self.original_handlers)
        self.assertEqual(len(self.signals), 2 * len(self.numbers))

    def test_plain_seal_ack6_updates_only_closed_ns_at_original_first_late_check(self):
        self.correct_ack("seal")

    def test_plain_before_ack6_updates_only_closed_ns_at_original_first_late_check(self):
        self.correct_ack("before")

    def test_plain_tail_ack9_keeps_owner_close_hash_and_both_resource_counts(self):
        self.correct_ack("tail")

    def test_near_receiver_scope_gets_no_new_timestamp_privilege(self):
        self.value["scope"] += "_NEAR"
        self.check(self.call)
        self.assertEqual(O.parse(self.output.getvalue())["closedNs"], 140 * NS)
        self.assertEqual(self.fence.calls, [(True, self.fence.work), (True, self.fence.work)])

    def test_unrelated_productive_scope_gets_no_prefix_wildcard_privilege(self):
        self.value["scope"] = "INITIAL_RECIPIENT_PRODUCTIVE_OTHER_POST_CLOSE_ACK_V1"
        self.check(self.call)
        self.assertEqual(O.parse(self.output.getvalue())["closedNs"], 140 * NS)

    def test_existing_exact_old_ack_scope_keeps_its_timestamp_update(self):
        self.value["scope"] = B.INITIAL_ACK_SCOPE
        self.check(self.call)
        self.assertEqual(O.parse(self.output.getvalue())["closedNs"], self.fence.values[0])

    def test_short_write_is_not_success_and_cannot_skip_exact_count(self):
        self.output.short = True
        self.assertIn("BOOTSTRAP_ACK_WRITE", str(self.refuses(self.call)))
        self.assertEqual(self.events, ["operation", "write"])
        self.assertEqual(len(self.fence.calls), 1)

    def test_write_failure_is_preserved_after_handlers_are_restored(self):
        first = self.output.write_failure = O.OriginError("MODEL_ACK_WRITE_FAILED")
        self.assertIs(self.refuses(self.call), first)
        self.assertEqual(self.handlers, self.original_handlers)
        self.assertEqual(self.events, ["operation", "write"])

    def test_flush_failure_keeps_escaped_bytes_provisional(self):
        first = self.output.flush_failure = O.OriginError("MODEL_ACK_FLUSH_FAILED")
        self.assertIs(self.refuses(self.call), first)
        self.assertNotEqual(self.output.getvalue(), b"")
        self.assertEqual(len(self.fence.calls), 1)

    def test_first_late_check_at_exact_work_end_refuses_before_stdout(self):
        self.fence.values[0] = self.fence.work
        self.assertIn("MODEL_ACK_WORK_EXPIRED", str(self.refuses(self.call)))
        self.assertEqual(self.output.getvalue(), b"")
        self.assertEqual(self.events, ["operation"])

    def test_second_late_check_cannot_borrow_final45_after_flush(self):
        self.fence.values[1] = self.fence.work
        self.assertLess(self.fence.work, self.fence.final)
        self.assertIn("MODEL_ACK_WORK_EXPIRED", str(self.refuses(self.call)))
        self.assertNotEqual(self.output.getvalue(), b"")
        self.assertEqual(self.events, ["operation", "write", "flush"])
        self.assertEqual(self.fence.calls, [(True, self.fence.work), (True, self.fence.work)])

    def test_ack_limit_is_unchanged_and_oversize_never_writes(self):
        self.value["modelOversize"] = "x" * B.ACK_LIMIT
        self.assertEqual(B.ACK_LIMIT, 16384)
        self.assertIn("BOOTSTRAP_ACK_WRITE", str(self.refuses(self.call)))
        self.assertEqual(self.output.getvalue(), b"")
        self.assertEqual(self.events, ["operation"])

    def test_cancellation_during_operation_restores_signals_and_prevents_output(self):
        operation = self.operation
        def cancelled_operation(cancelled):
            result = operation(cancelled)
            self.handlers[B.signal.SIGTERM](B.signal.SIGTERM, None)
            return result
        self.operation = cancelled_operation
        with self.assertRaises(KeyboardInterrupt):
            self.check(self.call)
        self.assertEqual(self.handlers, self.original_handlers)
        self.assertEqual(self.fence.calls, [])
        self.assertEqual(self.output.getvalue(), b"")

    def test_cancellation_during_flush_refuses_after_second_original_work_check(self):
        self.output.after_flush = lambda: self.cancelled.append(B.signal.SIGTERM)
        with self.assertRaises(KeyboardInterrupt):
            self.check(self.call)
        self.assertEqual(self.fence.calls, [(True, self.fence.work), (True, self.fence.work)])
        self.assertEqual(self.events, ["operation", "write", "flush"])

    def test_operation_failure_restores_original_handlers_without_output(self):
        first = O.OriginError("MODEL_ACK_OPERATION_FAILED")
        def failed(_cancelled):
            raise first
        self.operation = failed
        self.assertIs(self.refuses(self.call), first)
        self.assertEqual(self.handlers, self.original_handlers)
        self.assertEqual(self.fence.calls, [])
        self.assertEqual(self.output.getvalue(), b"")


class StaticBoundaryModels(ModelCase):
    """Text/hash preservation controls, explicitly not behavioral/native evidence."""

    def test_c_pc_and_cd_remain_exact_reviewed_integrated_suppliers(self):
        # Reviewed Foundation successors: a49fb2ac compatibility, 901dab68 raw originals,
        # a9ff0aa5 original-service job admission, fc8cce91 failure-only custody diagnostics.
        # Reviewed virtual-basis repair for run 37185605101 changes only C/CD basis minima.
        # Full supplier equality and all timing rules remain required; PC is unchanged.
        # Reviewed failure-only custody progress retains original Window/phase admission and close checks.
        # fb103521 adds independently reviewed first-failure traceback diagnostics only;
        # selected require/_snapshot_metadata bytes still equal 579d5817.
        # Reviewed immutable-handoff reuse and first-LOCAL observation preserve
        # those same selected functions byte-for-byte against 38035f8d.
        # Failure-only owner-ledger dispatch preserves every predicate/callback;
        # only successful error-wrapper calls are removed. No deadlines change.
        expected = {
            "run-hosted-initial-recipient-custody.py": "e40f507b256cb062d411f0cb3295a775b9605683594f54a3eb763ded168d9580",
            "hosted_initial_recipient_productive_custody.py": "8208dd3a4b114472690c1dc605de7d1f06116703aeeed533af232d99126c8a55",
            "hosted_initial_recipient_productive_custody_data.py": "31fd8be519a31d524e95b3e753b533983cb90067b6e64550e7e907a8a87205e7",
        }
        self.assertEqual({name: hashlib.sha256(SOURCE_BYTES[name]).hexdigest() for name in expected}, expected)

    def test_old_n_allowlist_still_contains_no_productive_receiver_scope(self):
        self.assertEqual(hashlib.sha256(source_definition(N_SOURCE, "_initial_service_phase")).hexdigest(),
            "48b9100ab7da594b4d093b21c22c4307781178d0d595155c6e1858ba409310bc")
        block = N_SOURCE.split("def _initial_service_phase(", 1)[1].split("\ndef _productive_authority_pre_phase(", 1)[0]
        self.assertNotIn("receiver_seed", block)
        self.assertNotIn("PRODUCTIVE_SEAL", block)
        self.assertNotIn("PRODUCTIVE_BEFORE", block)
        self.assertNotIn("productive_receiver", block)
        self.assertIn('"SERVICE_GIT_OLD_ROUTE"', block)

    def test_old_b_command_and_environment_have_no_receiver_admission(self):
        self.assertEqual(hashlib.sha256(source_definition(B_SOURCE, "phase_command")).hexdigest(),
            "031cbbb56fa54e40b71d483f2bcb7409b844b62ef041c412cafdc55a963f4d71")
        self.assertEqual(hashlib.sha256(source_definition(B_SOURCE, "_initial_service_environment")).hexdigest(),
            "23c1d9f2b15c3b9425ed2ff9ebd06f4e63c0ac0b04a8225eb91a6f94868d6d3e")
        command = B_SOURCE.split("def phase_command(", 1)[1].split("\ndef lifetime(", 1)[0]
        environment = B_SOURCE.split("def _initial_service_environment(", 1)[1].split("\ndef _installed_git_environment(", 1)[0]
        for block in (command, environment):
            self.assertNotIn("receiver_seed", block)
            self.assertNotIn("PRODUCTIVE_SEAL", block)
            self.assertNotIn("PRODUCTIVE_BEFORE", block)
            self.assertNotIn("productive_receiver", block)

    def test_receiver_has_exact_two_argv_sites_and_no_tail_bridge(self):
        phase = B_SOURCE.split("def _phase_owned(", 1)[1].split("\ndef revalidate(", 1)[0]
        self.assertEqual(phase.count("R._native_argv(receiver_seed, context_raw, receiver_phase[:3]"), 2)
        self.assertIn("final_seed is None or receiver_seed is None", phase)
        self.assertIn("final_productive_phase is None and receiver_phase is None", phase)
        self.assertNotIn("native_seed", phase)
        self.assertNotIn("enter_tail_productive_phase", phase)
        self.assertNotIn("productive_tail_crypto_native", N_SOURCE)

    def test_guarded_new_scopes_are_exact_literals_with_unchanged_two_checks(self):
        block = B_SOURCE.split("def guarded(", 1)[1].split("\ndef main(", 1)[0]
        for scope in ACKS.values():
            self.assertEqual(block.count('"' + scope + '"'), 1)
        self.assertEqual(block.count("fence.now(final=True, limit=limit)"), 2)
        self.assertNotIn("startswith", block)
        self.assertNotIn("deadline(", block)
        self.assertIn("len(raw) <= ACK_LIMIT", block)
        self.assertEqual(B.ACK_LIMIT, 16384)
        self.assertEqual(O.wire.ACQUIRE_SECONDS, 45)


if __name__ == "__main__":
    unittest.main(failfast=True)
