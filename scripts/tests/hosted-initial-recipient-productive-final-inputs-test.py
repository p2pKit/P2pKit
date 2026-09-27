#!/usr/bin/env python3
"""NEW final-reader currency and historical DATA models, never native admission.

The handoff/authority/read/rederivation seams below are explicit tiny models.
The separate DATA model patches only the maintained ACK/frame/index helpers;
its tiny index is NOT the actual281 inventory or a historical-reader fixture.
No provider, process, key, payload archive or existing reader suite is selected.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import ctypes
import dataclasses
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED = False
EFFECTS = []


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen") or \
            GUARDED and event in ("open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        EFFECTS.append(event)
        raise AssertionError("PRODUCTIVE_FINAL_INPUT_MODEL_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive_custody as PC
import hosted_cache_provider_readback as R

A, D, O, CD, NS = PC.A, PC.D, PC.O, PC.CD, PC.NS
H = "a" * 64
REFUSALS = (ValueError, RuntimeError)
ADAPTER_SOURCE = (ROOT / "scripts/hosted_initial_recipient_productive_adapter.py").read_text(encoding="utf-8")
DATA_SOURCE = (ROOT / "scripts/hosted_initial_recipient_productive_data.py").read_text(encoding="utf-8")


def guarded(function, *args, **kwargs):
    global GUARDED
    prior, count = GUARDED, len(EFFECTS)
    GUARDED = True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = prior
        if len(EFFECTS) != count:
            raise AssertionError("PRODUCTIVE_FINAL_INPUT_MODEL_EFFECT")


class ModelCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

    def install(self, module, name, value):
        self.stack.enter_context(patch.object(module, name, value))
        return value

    def check(self, function, *args, **kwargs):
        return guarded(function, *args, **kwargs)

    def refuses(self, function, *args, **kwargs):
        with self.assertRaises(REFUSALS) as caught:
            self.check(function, *args, **kwargs)
        return caught.exception


class FinalInputModels(ModelCase):
    def setUp(self):
        super().setUp()
        for name in ("_FINAL_PEEKS", "_FINAL_INPUTS", "_FINAL_FAILURES", "_DERIVES", "_INPUTS"):
            self.install(A, name, {})
        self.parent, self.authority = object(), object()
        self.owner = SimpleNamespace(original=None, closed=False)
        self.clock = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
        self.first = O.clocks.Reading(self.clock, 1000 * NS)  # Explicit model observation only.
        self.identity = SimpleNamespace(record=b"model-worker")
        self.old_identity = SimpleNamespace(record=b"model-worker")
        self.claims = {name: "success" if name.endswith("OUTCOME") else H for name in CD.FINAL_CLAIMS}
        self.handoff = A.HandoffInputs(b"model-handoff", self.old_identity, b"model-history", b"model-proposal",
            (), ROOT / "model-initializer", (7, 8), b"model-producer-return",
            (("custody-request.json", b"model-actual-request"),), object())
        self.derived = A.ProviderInputs({"source": {"model": "not-admitted"}}, object(), self.handoff,
            {"model": H}, b"model-staging", b"model-original-compatibility")
        self.rows = tuple({"site": site, "model": True} for site in CD.USE_SITES)
        self.reader = SimpleNamespace(owner=self.owner, first=self.first, handoff=self.handoff,
            use_rows=self.rows, use_pins=(PC.N._history_graph(self.rows),))
        self.bind_action = self.authority_action = self.derive_action = self.recheck_action = lambda: None
        self.calls, self.errors = [], []
        self.install(PC, "_final_reader_binding", self.binding)
        self.install(PC, "_final_reader_authority", self.admission)
        self.install(A, "read_productive_handoff", self.read_handoff)
        self.install(A, "_checked_handoff", self.checked_handoff)
        self.install(A, "_rederive_inputs", self.rederive)
        self.install(A, "_read_file", self.read_file)
        self.install(A, "_final_probe_history", lambda *_args: b"model-probe-return")
        self.install(A, "recheck_provider_inputs", self.recheck)
        self.install(A, "_reader_failure", self.reader_error)
        self.install(D, "worker_values", lambda identity: (identity.record,))

    def binding(self, parent):
        self.assertIs(parent, self.parent)
        self.calls.append(("binding", parent))
        self.bind_action()
        return self.owner, self.first, self.claims

    def admission(self, parent):
        self.assertIs(parent, self.parent)
        self.calls.append(("authority", parent))
        self.authority_action()
        return self.identity, self.authority

    def read_handoff(self, owner, first, claims):
        self.assertIs(owner, self.owner)
        self.assertIs(first, self.first)
        self.assertIs(claims, self.claims)
        self.calls.append(("handoff", self.handoff))
        return self.handoff

    def checked_handoff(self, handoff):
        self.assertIs(handoff, self.handoff)
        return self.reader

    def rederive(self, reader, identity):
        self.assertIs(reader, self.reader)
        self.calls.append(("rederive", identity))
        self.derive_action()
        return self.derived

    def read_file(self, reader, path, name, *, expected):
        self.assertIs(reader, self.reader)
        self.calls.append(("read", path, name, expected))
        return expected

    def recheck(self, owner, inputs):
        self.assertIs(owner, self.owner)
        self.assertIs(inputs, self.derived)
        self.recheck_action()

    def reader_error(self, reader, stage, error):
        self.errors.append((reader, stage, error))
        return error

    def peek(self):
        return self.check(A._peek_final_productive_inputs, self.parent)

    def result(self):
        self.peek()
        return self.check(A.read_final_productive_inputs, self.parent)

    def caught(self, function):
        errors = []
        def invoke():
            try:
                function(self.parent)
            except REFUSALS as error:
                errors.append(error)
        return invoke, errors

    def test_exact_final_input_fields(self):
        self.assertEqual(tuple(item.name for item in dataclasses.fields(A.FinalInputs)),
            ("parent", "handoff", "derived", "authority", "claims_raw", "probe_raw", "use_rows"))

    def test_peek_is_historical_data_without_current_authority(self):
        self.assertIs(self.peek(), self.handoff)
        self.assertEqual([row[0] for row in self.calls], ["binding", "handoff"])
        self.assertEqual(A._FINAL_INPUTS, {})
        self.assertEqual(A._DERIVES, {})

    def test_peek_reserves_before_first_callback_and_caught_reentry_sticks(self):
        self.bind_action, errors = self.caught(A._peek_final_productive_inputs)
        first = self.refuses(A._peek_final_productive_inputs, self.parent)
        self.assertIs(first, errors[0])
        self.bind_action = lambda: None
        self.assertIs(self.refuses(A._peek_final_productive_inputs, self.parent), first)
        self.assertFalse(any(row[0] == "handoff" for row in self.calls))

    def test_duplicate_successful_peek_poisons_same_parent(self):
        self.peek()
        first = self.refuses(A._peek_final_productive_inputs, self.parent)
        self.assertIs(self.refuses(A.read_final_productive_inputs, self.parent), first)

    def test_missing_peek_cannot_be_repaired_after_read_attempt(self):
        first = self.refuses(A.read_final_productive_inputs, self.parent)
        self.assertIs(self.refuses(A._peek_final_productive_inputs, self.parent), first)

    def test_final_read_rederives_with_distinct_fresh_identity(self):
        result = self.result()
        self.assertIsNot(self.identity, self.old_identity)
        self.assertIn(("rederive", self.identity), self.calls)
        self.assertIs(result.authority, self.authority)
        self.assertIs(result.derived, self.derived)
        self.assertIs(result.handoff, self.handoff)
        self.assertIs(result.use_rows, self.rows)
        self.assertEqual(len(result.use_rows), 21)  # Model rows, not native authenticity.

    def test_actual_request_carrier_is_a_separate_fixed_read(self):
        self.result()
        self.assertIn(("read", self.handoff.initializer / "configuration-custody", "request.json",
            dict(self.handoff.blobs)["custody-request.json"]), self.calls)

    def test_missing_current_authority_cannot_be_replaced_by_old_identity(self):
        self.peek()
        error = O.OriginError("MODEL_CURRENT_AUTHORITY_MISSING")
        def missing():
            raise error
        self.authority_action = missing
        self.assertIs(self.refuses(A.read_final_productive_inputs, self.parent), error)
        self.authority_action = lambda: None
        self.assertIs(self.refuses(A.read_final_productive_inputs, self.parent), error)

    def test_read_attempt_is_reserved_before_binding_callback(self):
        self.peek()
        self.bind_action, errors = self.caught(A.read_final_productive_inputs)
        first = self.refuses(A.read_final_productive_inputs, self.parent)
        self.assertIs(first, errors[0])
        self.assertFalse(any(row[0] == "rederive" for row in self.calls))

    def test_caught_rederivation_reentry_is_not_success(self):
        self.peek()
        self.derive_action, errors = self.caught(A.read_final_productive_inputs)
        first = self.refuses(A.read_final_productive_inputs, self.parent)
        self.assertIs(first, errors[0])
        self.assertIs(self.errors[-1][2], first)

    def test_duplicate_read_revokes_checks_of_its_first_result(self):
        result = self.result()
        first = self.refuses(A.read_final_productive_inputs, self.parent)
        self.assertIs(self.refuses(A.checked_final_productive_inputs, result), first)

    def test_foreign_equal_result_is_not_registered(self):
        result = self.result()
        self.refuses(A.checked_final_productive_inputs, dataclasses.replace(result))
        self.assertIs(self.check(A.checked_final_productive_inputs, result), result)

    def test_equal_result_dictionary_replacement_is_sticky_after_repair(self):
        result = self.result()
        dictionary = result.__dict__
        object.__setattr__(result, "__dict__", dict(dictionary))
        first = self.refuses(A.checked_final_productive_inputs, result)
        object.__setattr__(result, "__dict__", dictionary)
        self.assertIs(self.refuses(A.checked_final_productive_inputs, result), first)

    def test_mutated_parent_is_latched_against_original_not_foreign_parent(self):
        result = self.result()
        foreign = object()
        object.__setattr__(result, "parent", foreign)
        first = self.refuses(A.checked_final_productive_inputs, result)
        self.assertIn(id(self.parent), A._FINAL_FAILURES)
        self.assertNotIn(id(foreign), A._FINAL_FAILURES)
        object.__setattr__(result, "parent", self.parent)
        self.assertIs(self.refuses(A.checked_final_productive_inputs, result), first)

    def test_changed_owner_is_not_equal_owner_authority(self):
        result = self.result()
        self.owner = SimpleNamespace(original=None, closed=False)
        self.refuses(A.checked_final_productive_inputs, result)

    def test_new_equal_reading_does_not_replace_original_first(self):
        result = self.result()
        self.first = O.clocks.Reading(self.clock, self.first.nanoseconds)
        self.refuses(A.checked_final_productive_inputs, result)

    def test_changed_claims_are_not_current_step_outputs(self):
        result = self.result()
        self.claims["PROBE_SHA256"] = "b" * 64
        self.refuses(A.checked_final_productive_inputs, result)

    def test_changed_authority_handle_refuses(self):
        result = self.result()
        self.authority = object()
        self.refuses(A.checked_final_productive_inputs, result)

    def test_changed_worker_identity_refuses(self):
        result = self.result()
        self.identity = SimpleNamespace(record=b"other-model-worker")
        self.refuses(A.checked_final_productive_inputs, result)

    def test_derived_dictionary_cannot_be_substituted(self):
        result = self.result()
        dictionary = self.derived.__dict__
        object.__setattr__(self.derived, "__dict__", dict(dictionary))
        first = self.refuses(A.checked_final_productive_inputs, result)
        object.__setattr__(self.derived, "__dict__", dictionary)
        self.assertIs(self.refuses(A.checked_final_productive_inputs, result), first)

    def test_original_compatibility_bytes_are_pinned_with_the_registered_derived_inputs(self):
        result = self.result()
        original = self.derived.compatibility_raw
        object.__setattr__(self.derived, "compatibility_raw", b"model-substituted-compatibility")
        first = self.refuses(A.checked_final_productive_inputs, result)
        object.__setattr__(self.derived, "compatibility_raw", original)
        self.assertIs(self.refuses(A.checked_final_productive_inputs, result), first)

    def test_nested_derived_mutation_during_callback_is_rechecked(self):
        result = self.result()
        self.recheck_action = lambda: self.derived.plan["source"].update(model="changed")
        first = self.refuses(A.checked_final_productive_inputs, result)
        self.derived.plan["source"]["model"] = "not-admitted"
        self.recheck_action = lambda: None
        self.assertIs(self.refuses(A.checked_final_productive_inputs, result), first)

    def test_original_use_graph_mutation_refuses(self):
        result = self.result()
        self.rows[-1]["site"] = "other/model-use"
        self.refuses(A.checked_final_productive_inputs, result)

    def test_final_field_changed_during_callback_refuses(self):
        result = self.result()
        self.recheck_action = lambda: object.__setattr__(result, "probe_raw", b"different-model-probe")
        self.refuses(A.checked_final_productive_inputs, result)

    def test_old_live_reader_route_is_not_replayed_by_new_source_path(self):
        block = ADAPTER_SOURCE.split("def _final_probe_history(", 1)[1].split("\ndef read_final_productive_inputs(", 1)[0]
        self.assertIn("D._HistoricalDataPoint(", block)
        self.assertIn("_final_action_originals(", block)
        self.assertNotIn("O.clocks.Reading(", block)
        final = ADAPTER_SOURCE.split("def read_final_productive_inputs(", 1)[1]
        self.assertIn("_rederive_inputs(reader, identity)", final)
        self.assertNotIn("_fresh_begin(", final)
        self.assertIn("tuple(sorted(CD.USE_SITES))", block)


class HistoricalActionDataModels(ModelCase):
    def setUp(self):
        super().setUp()
        self.clock = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
        self.point = D._HistoricalDataPoint(self.clock, 140 * NS)
        self.directory = Path("/model/prepare-probe")
        self.context = {"phase": "lookup", "role": self.clock.role, "frequency": NS,
            "directory": str(self.directory / "provider"), "home": str(self.directory / "provider-home"),
            "firstNs": str(100 * NS), "issuedNs": str(80 * NS), "hardEndNs": str(260 * NS),
            "plan": {"source": {}, "github": {}}}
        self.outputs = {"cache-primary-key": "model", "cache-matched-key": "model", "cache-hit": "true"}
        self.descriptor = {"scope": D.PROBE_PREPARATION_SCOPE, "directory": str(self.directory),
            "directoryIdentity": [7, 8], "clock": O.clock_value(self.clock), "plan": self.context["plan"],
            "planSha256": O.digest(O.encoded(self.context["plan"])),
            "providerWindow": {"issuedNs": 80 * NS, "hardEndNs": 260 * NS, "actualProviderStart": "NOT_OBSERVED"}}
        self.preparation_raw = O.encoded(self.descriptor)
        self.claims = {name: "success" if name.endswith("OUTCOME") else H
            for name in (*R.BASE_CLAIMS, *R.LOOKUP_CLAIMS, "PROBE_OUTCOME", "PROBE_READBACK_SHA256")}
        self.claims["PROBE_PREPARATION_SHA256"] = O.digest(self.preparation_raw)
        self.chain = {"schema": 1, "scope": "INITIAL_RECIPIENT_PROVIDER_ORIGINAL_USE_CHAIN_V1", "phase": "lookup",
            "clock": O.clock_value(self.clock), "originalBootDigest": H, "helperFirstNs": 100 * NS,
            "helperWorkEndNs": 145 * NS, "providerIssuedNs": 80 * NS, "providerHardEndNs": 260 * NS,
            "handoffSha256": H, "producerReturnSha256": H, "preparationSha256": O.digest(self.preparation_raw),
            "workerIdentitySha256": H, "directory": str(self.directory / "native-preparation"),
            "directoryIdentity": [7, 9], "source": {}, "github": {}, "materializedNs": 110 * NS, "uses": [],
            "checkedNs": 130 * NS, "helperOwnerClose": D.PENDING, "providerExecution": "NOT_PERFORMED",
            "exportSaveAuthority": False}
        self.native = {}
        root = self.directory.with_name("prepare")
        for offset, edge in ((0, "begin"), (10, "final")):
            site = "provider-probe/native-prepare/" + edge
            frame = {"site": site, "parentFirstNs": 100 * NS, "parentWorkEndNs": 145 * NS,
                "originalBootDigest": H, "firstNs": (101 + offset) * NS, "workEndNs": (109 + offset * 2) * NS}
            index_raw = O.encoded({"tiny-model-index": edge})
            returned = {"schema": 1, "scope": R.initial_use.RETURN_SCOPE, "site": site,
                "windowSha256": O.digest(O.encoded(frame)), "workerIdentitySha256": H,
                "inventorySha256": O.digest(index_raw), "pendingSha256": H,
                "originalChain": {"checkedNs": (102 + offset) * NS}, "preCloseNs": (103 + offset) * NS,
                "closedNs": (104 + offset) * NS, "resourceCount": 1, "retirement": "KNOWN_RESOURCE_CLOSE_ONLY",
                "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
            returned_raw = O.encoded(returned)
            self.native[edge + "-use.json"], self.native[edge + "-use-index.json"] = returned_raw, index_raw
            self.chain["uses"].append({"site": site, "root": str(root.with_name(root.name + "-" + R.initial_use.site_leaf(site))),
                "window": frame, "returnSha256": O.digest(returned_raw), "inventorySha256": O.digest(index_raw)})
        self.native["initial-use-chain.json"] = O.encoded(self.chain)
        old_claims = {name: self.claims[name] for name in (*R.BASE_CLAIMS, *R.LOOKUP_CLAIMS)}
        self.prepared = {"scope": "INITIAL_RECIPIENT_PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1",
            "phase": "lookup", "preparationSha256": O.digest(self.preparation_raw), "request": "model-request",
            "bindings": {name: H for name in R.launch.worker_source.outer_names(self.clock.role)},
            "clockBindings": {name: H for name in R.clock_source.roster(self.clock.role)},
            "firstNs": str(100 * NS), "originalClaims": old_claims, "providerExecution": "NOT_PERFORMED",
            "enclosingActionReturn": "NOT_OBSERVED", "initialUseChainSha256": O.digest(self.native["initial-use-chain.json"])}
        self.returned = {"scope": "INITIAL_RECIPIENT_PROVIDER_NATIVE_READBACK_PENDING_HELPER_RETURN_V1", "phase": "lookup",
            "preparedSha256": O.digest(O.encoded(self.prepared)), "preparationSha256": O.digest(self.preparation_raw),
            "acknowledgement": "model-ack", "acknowledgementSha256": O.digest(b"model-ack"), "python": "/model/python3",
            "workerRequestSha256": H, "outputs": self.outputs, "checkedNs": str(135 * NS), "originalClaims": old_claims,
            "enclosingActionReturn": "NOT_OBSERVED", "providerAcceptance": "NOT_ESTABLISHED",
            "initialUseChainSha256": self.prepared["initialUseChainSha256"]}
        self.helper_calls = []
        self.install(R.outer, "_context", self.request_context)
        self.install(R.outer, "read_ack", self.ack)
        self.install(R.initial_use, "checked_frame", self.frame)
        self.install(R, "_initial_use_index", self.index)
        self.install(O.clocks, "validate_reading", lambda *_args: self.fail("historical DATA invoked live Reading validator"))

    def request_context(self, raw):
        self.assertEqual(raw, b"model-request")
        self.helper_calls.append("context")
        return self.context, object()

    def ack(self, raw, request, code):
        self.assertEqual((raw, request, code), (b"model-ack", b"model-request", 0))
        self.helper_calls.append("ack")
        return SimpleNamespace(kind="success", provider_kind="success", worker_exit_code=0,
            worker_request_sha256=H, observed_ns=105 * NS)

    def frame(self, value):
        self.helper_calls.append("frame")
        return self.clock, value

    def index(self, value, root, site, frame, returned):
        # Explicit tiny-model seam: this is NOT testing the maintained281 parser.
        self.assertEqual(value, {"tiny-model-index": site.rsplit("/", 1)[1]})
        self.assertEqual(returned["windowSha256"], O.digest(O.encoded(frame)))
        self.assertTrue(root.is_absolute())
        self.helper_calls.append("index")

    def originals(self):
        prepared_raw = O.encoded(self.prepared)
        self.returned["preparedSha256"] = O.digest(prepared_raw)
        raw = O.encoded(self.returned)
        self.claims["PROBE_READBACK_SHA256"] = O.digest(raw)
        return dict(zip(R.ACTION_FILES, (prepared_raw, raw)))

    def parse(self, point=None):
        return self.check(D.final_action_records, self.originals(), self.preparation_raw, self.claims,
            self.point if point is None else point, self.outputs, self.native)

    def test_hash_joined_historical_data_without_fabricated_reading(self):
        self.assertEqual(self.parse(), self.chain)
        self.assertEqual(self.helper_calls, ["context", "ack", "frame", "index", "frame", "index"])

    def test_actual_reading_type_cannot_stand_in_for_historical_data(self):
        self.refuses(self.parse, O.clocks.Reading(self.clock, self.point.nanoseconds))
        self.assertEqual(self.helper_calls, [])

    def test_boolean_historical_ns_refuses_before_helpers(self):
        self.refuses(self.parse, D._HistoricalDataPoint(self.clock, True))
        self.assertEqual(self.helper_calls, [])

    def test_extra_claim_refuses_before_helpers(self):
        self.claims["UNDECLARED"] = H
        self.refuses(self.parse)
        self.assertEqual(self.helper_calls, [])

    def test_nonstring_outcome_or_digest_refuses_before_helpers(self):
        for name, value in (("PROBE_OUTCOME", True), ("HANDOFF_SHA256", "A" * 64)):
            old = self.claims[name]
            self.claims[name] = value
            self.refuses(self.parse)
            self.claims[name] = old
        self.assertEqual(self.helper_calls, [])

    def test_pending_action_does_not_become_native_or_provider_acceptance(self):
        self.returned["providerAcceptance"] = "ACCEPTED"
        self.refuses(self.parse)

    def test_original_provider_end_is_not_renewed_at_final_read(self):
        self.refuses(self.parse, D._HistoricalDataPoint(self.clock, 260 * NS))

    def test_duplicate_episode_and_original_chain_hash_changes_refuse(self):
        changed = copy.deepcopy(self.chain)
        changed["uses"][1] = changed["uses"][0]
        self.native["initial-use-chain.json"] = O.encoded(changed)
        self.prepared["initialUseChainSha256"] = self.returned["initialUseChainSha256"] = O.digest(
            self.native["initial-use-chain.json"])
        self.refuses(self.parse)

    def test_extra_native_original_is_not_ignored(self):
        self.native["unexpected.json"] = b"{}\n"
        self.refuses(self.parse)

    def test_final_data_source_never_calls_old_live_action_entry(self):
        block = DATA_SOURCE.split("def final_action_records(", 1)[1].split("\ndef preparation_record(", 1)[0]
        self.assertNotIn("validate_initial_action_return(", block)
        self.assertNotIn("validate_initial_use_chain(", block)
        self.assertNotIn("validate_reading(", block)
        self.assertNotIn("O.clocks.Reading(", block)


if __name__ == "__main__":
    unittest.main(failfast=True)
