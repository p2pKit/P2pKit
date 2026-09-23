#!/usr/bin/env python3
"""NEW collect-export/collect-close controls; AUTHORED, NOT execution evidence.

No earlier test modules are imported; the NEW sibling loads production source.
See the fixture's explicit supplier contract: no old successful registry insertion, old suite,
process/Git/HTTP/native library, GPG, private original or hosted environment.
The complete post-export composition is real production Python over supplied
low-level process/query/HTTP/clock boundaries and tiny real POSIX files. Those
models are not producer, retirement, provider, timing, custody or Step evidence.
No control result is claimed until independent source review and a separately
admitted frozen offline run. These methods are not an execution request.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


_spec = importlib.util.spec_from_file_location("new_collect_supplied_models",
    Path(__file__).with_name("hosted_initial_collect_models.py"))
M = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = M
_spec.loader.exec_module(M)
D, Rig, NS, BOOT, TOKEN, wire, sha = M.D, M.Rig, M.NS, M.BOOT, M.TOKEN, M.wire, M.sha


def frames():
    result, frame = [], sys._getframe(1)
    while frame is not None:
        result.append(frame)
        frame = frame.f_back
    return result


def rehash_bundle(raws, *, step=None, carrier=None, context=None, manifest=None):
    """Supplied-data mutation utility, not a production signer/Step fallback."""
    result = dict(raws)
    transfer = json.loads(result["step"])
    original = json.loads(result["carrier"])
    if context is not None:
        value = json.loads(result["context"])
        context(value)
        result["context"] = wire(value)
        transfer["originalContextSha256"] = sha(result["context"])
        original["parentClose"]["contextSha256"] = sha(result["context"])
    if manifest is not None:
        value = json.loads(result["manifest"])
        manifest(value)
        result["manifest"] = wire(value)
        original["exporter"].update(manifestBase64=M.base64.b64encode(result["manifest"]).decode("ascii"),
            manifestBytes=len(result["manifest"]), manifestSha256=sha(result["manifest"]))
        transfer["cryptoCarrier"]["exporterReturnSha256"] = sha(result["manifest"])
    if carrier is not None:
        carrier(original)
    result["carrier"] = wire(original)
    transfer["cryptoCarrier"].update(sha256=sha(result["carrier"]), bytes=len(result["carrier"]))
    if step is not None:
        step(transfer)
    result["step"] = wire(transfer)
    return result


class EntryControls(unittest.TestCase):
    def test_first_token_helper_returns_only_actual_inputs_before_token_free_crypto(self):
        with Rig() as rig, ExitStack() as stack:
            primary, authority, crypto, carrier, transfer = (object() for _ in range(5))
            calls = []
            rig.env[D.O.wire.TOKEN_ENV] = TOKEN
            def copy(kind, *, cancelled):
                self.assertEqual(kind, "gate")
                self.assertNotIn(D.O.wire.TOKEN_ENV, rig.env)
                calls.append("PRIMARY")
                return primary
            def acquire(value, token):
                self.assertIs(value, primary)
                self.assertEqual(token, TOKEN)
                calls.append("AUTHORITY1")
                return authority
            def encrypt(one, two):
                self.assertIs(one, primary)
                self.assertIs(two, authority)
                active = frames()
                self.assertFalse(any(frame.f_code.co_name == "_export_pre_crypto" for frame in active))
                caller = next(frame for frame in active if frame.f_code.co_name == "collect_export")
                self.assertNotIn("token", caller.f_locals)
                self.assertNotIn(D.O.wire.TOKEN_ENV, rig.env)
                calls.append("TOKEN_FREE_CRYPTO")
                return crypto
            stack.enter_context(patch.object(D, "copy_primary", copy))
            stack.enter_context(patch.object(D, "custody_authority", acquire))
            stack.enter_context(patch.object(D, "custody_crypto", encrypt))
            stack.enter_context(patch.object(D, "_custody_crypto_carrier", lambda value: carrier if value is crypto else None))
            stack.enter_context(patch.object(D, "_retain_crypto_step", lambda value: transfer if value is carrier else None))
            stack.enter_context(patch.object(D, "_CollectOutputFence", lambda value: SimpleNamespace(append=lambda: value)))
            self.assertIs(D.collect_export("gate", rig.clock.cancelled), transfer)
            self.assertEqual(calls, ["PRIMARY", "AUTHORITY1", "TOKEN_FREE_CRYPTO"])
            self.assertNotIn(D.O.wire.TOKEN_ENV, rig.env)

    def test_pre_crypto_falsey_failure_clears_token_without_returning_alias(self):
        with Rig() as rig:
            failure = M.FalseyFailure("SUPPLIED_PRE_CRYPTO_FAILURE")
            rig.env[D.O.wire.TOKEN_ENV] = TOKEN
            with patch.object(D, "copy_primary", side_effect=failure), patch.object(D, "custody_authority") as later:
                with self.assertRaises(M.FalseyFailure) as caught:
                    D._export_pre_crypto("gate", rig.clock.cancelled)
                self.assertIs(caught.exception, failure)
                later.assert_not_called()
            self.assertNotIn(D.O.wire.TOKEN_ENV, rig.env)

    def test_second_entry_needs_new_token_before_any_file_or_supplier(self):
        with Rig() as rig, patch.object(D, "_read_collect_input") as read:
            with self.assertRaisesRegex(Exception, "COLLECT_SECOND_TOKEN"):
                D._collect_pre_metadata("gate", rig.clock.cancelled)
            self.assertEqual(rig.clock.events[:2], ["LOCAL", "FIRST_RAW"])
            read.assert_not_called()
            self.assertEqual((rig.queries, rig.requests, rig.scopes), ([], [], []))

    def test_other_credential_and_non_success_predecessors_refuse(self):
        with Rig() as rig:
            for value in (None, "failure", "cancelled", "skipped", "SUCCESS", True):
                with self.subTest(outcome=value):
                    if value is None:
                        rig.env.pop(D._COLLECT_OUTCOME, None)
                    else:
                        rig.env[D._COLLECT_OUTCOME] = value
                    with self.assertRaises(Exception):
                        D._collect_actual()
            rig.env[D._COLLECT_OUTCOME] = "success"
            for name in D._CREDENTIAL_NAMES:
                with self.subTest(credential=name):
                    rig.env[name] = TOKEN
                    with self.assertRaises(Exception):
                        D._collect_actual()
                    rig.env.pop(name)
            self.assertEqual(D._collect_actual(), tuple(rig.env.get(name) for name in D._COLLECT_NAMES))

    def test_reentry_consumes_original_attempt_even_if_callback_catches_it(self):
        with Rig() as rig:
            first = D._collect_begin("collect-close-entry")
            with self.assertRaises(Exception) as caught:
                D._collect_begin("collect-close-entry")
            self.assertIs(first["failure"], caught.exception)
            self.assertEqual(first["state"], "FAILED")
            with self.assertRaises(Exception) as repeated:
                D._collect_begin("collect-close-entry")
            self.assertIs(repeated.exception, caught.exception)


class TransferAndInputControls(unittest.TestCase):
    def test_complete_gate_and_worker_prior_grammar_never_restores_old_returns(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), Rig(kind) as rig:
                old = {name: dict(getattr(D, name)) for name in ("_WINDOWS", "_PRIMARY_RETURNS", "_CRYPTO_RETURNS", "_CRYPTO_CARRIERS")}
                parsed = D._collect_bundle(rig.packets.raws)
                match = D._collect_host(rig.packets.raws, parsed, rig.clock.identity)
                self.assertEqual(match.record, rig.packets.match.record)
                for name, original in old.items():
                    self.assertEqual(getattr(D, name), original)
                fake = D.CustodyCryptoCarrier(object(), rig.packets.raws["carrier"], wire(M.close_record(("directory",))))
                with self.assertRaisesRegex(Exception, "NOT_ORIGINAL_CRYPTO_CARRIER"):
                    D._checked_crypto_carrier(fake)

    def test_real_export_currency_rechecks_supplied_prior_boundaries_after_last_clock_callback(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), Rig(kind) as rig:
                old = {name: dict(getattr(D, name)) for name in
                    ("_WINDOWS", "_PRIMARY_RETURNS", "_CRYPTO_RETURNS", "_CRYPTO_CARRIERS")}
                boundary = rig.export_currency_boundary()
                callbacks = []
                def observe():
                    callbacks.append(tuple(boundary.checks))
                rig.clock.callback = observe
                result = D._collect_export_currency(boundary.carrier)  # This helper is NOT patched.
                self.assertIs(result[0], boundary.window)
                self.assertIs(result[1], boundary.clock)
                self.assertEqual(result[3], rig.packets.raws["manifest"])
                self.assertEqual(result[5]["serviceJob"], rig.packets.transfer["originalServiceJob"])
                self.assertEqual(callbacks, [("carrier", "inputs", "primary", "authority")])
                self.assertEqual(boundary.checks,
                    ["carrier", "inputs", "primary", "authority", "carrier", "primary", "authority", "inputs"])
                self.assertEqual(len(rig.requests), 8)
                for name, original in old.items():
                    self.assertEqual(getattr(D, name), original)

    def test_real_export_currency_rejects_last_callback_carrier_match_window_and_input_changes(self):
        for changed in ("carrier", "match", "window", "inputs"):
            with self.subTest(changed=changed), Rig() as rig:
                boundary = rig.export_currency_boundary()
                callbacks = []
                def mutate():
                    callbacks.append(True)
                    if changed == "carrier":
                        object.__setattr__(boundary.carrier, "__dict__", dict(boundary.carrier.__dict__))
                    elif changed == "match":
                        object.__setattr__(boundary.original, "__dict__", dict(boundary.original.__dict__))
                    elif changed == "window":
                        boundary.primary_window = SimpleNamespace(clock=boundary.window.clock)
                    else:
                        boundary.inputs = (object(), boundary.authority)
                rig.clock.callback = mutate
                with self.assertRaisesRegex(Exception, "POST_CALLBACK_CHANGED|AUTHORITY_MATCH_CHANGED|INPUTS_CHANGED"):
                    D._collect_export_currency(boundary.carrier)
                self.assertEqual(callbacks, [True])
                if changed == "window":
                    self.assertEqual(boundary.checks[-2:], ["carrier", "primary"])
                if changed == "inputs":
                    self.assertEqual(boundary.checks[-4:], ["carrier", "primary", "authority", "inputs"])
                self.assertEqual(D._CRYPTO_CARRIERS, {})

    def test_transfer_is_new_real_file_close_with_postreturn_floor_and_exact_digests(self):
        with Rig() as rig:
            result, facade = rig.export_step()
            value = json.loads(result.raw)
            self.assertEqual(value["lowerNs"], 1180 * NS)
            self.assertGreater(value["lowerNs"], json.loads(rig.packets.raws["carrier"])["window"]["lastNs"])
            self.assertEqual(value["lowerLocal"], 100.0)
            self.assertEqual(value["writerReturn"], "PENDING_OWNER_CLOSE")
            self.assertEqual(value["originalStepOutcome"], "NOT_OBSERVED")
            saved = D._EXPORT_STEPS[id(result)]
            self.assertTrue(saved[7].finished)
            self.assertTrue(all(a and c for _r, _l, _o, a, c in saved[7].rows))
            self.assertEqual((rig.custody / "returned" / D._EXPORT_STEP_FILE).read_bytes(), result.raw)
            actual, limit, values = D._checked_export_step(result)
            self.assertIs(actual, facade)
            self.assertEqual(limit, rig.packets.transfer["originalWindow"]["readEndNs"])
            self.assertEqual(values, {"initialCryptoStepSha256": sha(result.raw),
                "initialExporterReturnSha256": sha(rig.packets.raws["manifest"])})
            with self.assertRaises(Exception):
                D._retain_crypto_step(result.carrier)

    def test_transfer_rejects_equal_return_dictionary_and_returned_roster_collisions(self):
        with Rig() as rig:
            result, _facade = rig.export_step()
            object.__setattr__(result, "__dict__", dict(result.__dict__))
            with self.assertRaisesRegex(Exception, "COLLECT_EXPORT_STEP_CHANGED"):
                D._checked_export_step(result)
        with Rig() as rig:
            M.put(rig.custody / "returned" / "unexpected.json", b"{}\n")
            with self.assertRaisesRegex(Exception, "RETURNED_ROSTER"):
                rig.export_step()

    def test_prior_crypto_child_member_is_mandatory_and_returned_roster_stays_exact(self):
        for stage in ("transfer", "input", "final"):
            for changed in ("missing", "extra"):
                with self.subTest(stage=stage, changed=changed), Rig() as rig:
                    authority = rig.authority() if stage == "final" else None
                    child = rig.custody / "returned/crypto-child-result.json"
                    self.assertEqual(sha(child.read_bytes()), json.loads(rig.packets.raws["carrier"])["exporter"]["childSha256"])
                    if changed == "missing":
                        child.unlink()
                    else:
                        M.put(child.with_name("unexpected-crypto-child.json"), b"SUPPLIED_EXTRA_PRIOR_CHILD")
                    with self.assertRaisesRegex(Exception, "RETURNED_ROSTER"):
                        if stage == "transfer":
                            rig.export_step()
                        elif stage == "input":
                            rig.input()
                        else:
                            D._collect_closed(authority)
                    self.assertEqual(D._EXPORT_STEPS, {})
                    self.assertEqual(D._COLLECT_RETURNS, {})
                    self.assertEqual(rig.output.read_bytes(), b"")

    def test_actual_new_input_owner_closes_before_binding_and_immutable_actual_hashes(self):
        with Rig() as rig:
            clock, inputs, expected = rig.input()
            raw, metadata = D._checked_collect_input(inputs)
            self.assertEqual(raw, rig.packets.raws)
            self.assertTrue(metadata.finished and metadata.owner.closed)
            self.assertTrue(all(a and c for _r, _l, _v, a, c in metadata.rows))
            self.assertEqual(expected.record, rig.packets.match.record)
            self.assertEqual(clock.frame, rig.packets.transfer["originalWindow"])
            rig.env[D._COLLECT_STEP_HASH] = "f" * 64
            with self.assertRaisesRegex(Exception, "ACTUAL_STEP_OR_CREDENTIAL_CHANGED"):
                D._checked_collect_input(inputs)

    def test_hash_mismatch_refuses_matching_files_without_actual_step_binding(self):
        for name in (D._COLLECT_STEP_HASH, D._COLLECT_EXPORT_HASH, D.PRIMARY_RESULT, D.PRIMARY_HANDOFF):
            with self.subTest(name=name), Rig() as rig:
                rig.env[name] = "f" * 64
                with self.assertRaises(Exception):
                    rig.input()
                self.assertEqual(D._COLLECT_INPUTS, {})
                self.assertEqual(rig.requests, [])

    def test_closed_nested_prior_grammar_rejects_rehashed_mutations(self):
        changes = (
            {"step": lambda value: value.update(writerReturn="KNOWN")},
            {"step": lambda value: value["originalWindow"].update(readEndNs=value["originalWindow"]["readEndNs"] + NS)},
            {"step": lambda value: value["cryptoCarrier"].update(unexpected=True)},
            {"context": lambda value: value.update(scope="INITIAL_CUSTODY_AUTHORITY_CONTEXT_V1")},
            {"context": lambda value: value["authority"].update(matchSha256="f" * 64)},
            {"carrier": lambda value: value["parentClose"].update(retirement="UNKNOWN")},
            {"carrier": lambda value: value["exporter"].update(manifestBytes=True)},
            {"manifest": lambda value: value.update(productiveAuthority=True)},
            {"manifest": lambda value: value["copy"]["origins"].update(LATE_AUTHORITY="f" * 64)},
            {"manifest": lambda value: value["artifact"].update(size=0)},
        )
        with Rig() as rig:
            for index, change in enumerate(changes):
                with self.subTest(index=index):
                    with self.assertRaises(Exception):
                        D._collect_bundle(rehash_bundle(rig.packets.raws, **change))

    def test_new_input_equal_tuple_and_metadata_dictionary_substitution_refuse(self):
        with Rig() as rig:
            _clock, inputs, _expected = rig.input()
            object.__setattr__(inputs, "originals", tuple(list(inputs.originals)))
            with self.assertRaisesRegex(Exception, "INPUT_RETURN_CHANGED"):
                D._checked_collect_input(inputs)
        with Rig() as rig:
            _clock, inputs, _expected = rig.input()
            metadata = D._COLLECT_INPUTS[id(inputs)][4]
            metadata.owner.__dict__ = dict(metadata.owner.__dict__)
            with self.assertRaises(Exception):
                D._checked_collect_input(inputs)


class ClockControls(unittest.TestCase):
    def test_gate_native_final_may_be_past_but_only_original_read_residue_remains(self):
        with Rig() as rig:
            clock, _inputs, _expected = rig.input()
            self.assertGreater(clock.first, clock.frame["nativeFinalEndNs"])
            self.assertEqual(clock.work, clock.final)
            self.assertEqual(clock.work, clock.frame["readEndNs"])
            self.assertLessEqual(clock.deadline(900), 125.0)
            self.assertEqual(clock.frame["startNs"], 1000 * NS)
            self.assertEqual(clock.frame["originalJobBasisNs"], 950 * NS)

    def test_worker_preserves_stricter_preliminary_raw30_and_local30_not_new_read_time(self):
        with Rig("worker") as rig:
            clock, _inputs, _expected = rig.input()
            self.assertGreater(clock.frame["readEndNs"], clock.first + 30 * NS)
            self.assertEqual(clock.work, clock.first + 30 * NS)
            self.assertEqual(clock.final, clock.work)
            self.assertLessEqual(clock.local_end, 130.0)
            rig.clock.advance(30)
            with self.assertRaises(Exception):
                clock.now(limit=clock.frame["readEndNs"])

    def test_wrong_boot_backward_local_and_expiry_stick_after_restoration(self):
        for name in ("boot", "local", "raw"):
            with self.subTest(name=name), Rig() as rig:
                clock, _inputs, _expected = rig.input()
                before = getattr(rig.clock, name)
                setattr(rig.clock, name, "8" * 64 if name == "boot" else 99.0 if name == "local" else clock.work)
                with self.assertRaises(Exception) as caught:
                    clock.now()
                setattr(rig.clock, name, before)
                with self.assertRaises(Exception) as repeated:
                    clock.now()
                self.assertIs(repeated.exception, caught.exception)

    def test_original_frame_and_first_dictionary_mutations_consume_clock(self):
        for change in ("frame", "first"):
            with self.subTest(change=change), Rig() as rig:
                clock, _inputs, _expected = rig.input()
                if change == "frame":
                    clock.frame["startNs"] += 1
                else:
                    object.__setattr__(clock.reading, "__dict__", dict(clock.reading.__dict__))
                with self.assertRaises(Exception):
                    clock.now()
                self.assertIsNotNone(clock._anchor().failure)

    def test_metadata_expenditure_and_missing_close_cannot_rebind_or_grant_time(self):
        with Rig() as rig:
            first = rig.clock.reading()
            clock = D._CollectClock(first, rig.clock.local, BOOT, rig.clock.cancelled, side="parent")
            inputs = D._read_collect_input(clock, "gate", D._collect_actual())
            rig.clock.advance(31)
            with self.assertRaises(Exception):
                clock.bind_parent(inputs)
            self.assertIsNotNone(clock._anchor().failure)
            rig.clock.advance(-31)
            with self.assertRaises(Exception):
                clock.bind_parent(inputs)
        with Rig() as rig:
            clock = D._CollectClock(rig.clock.reading(), rig.clock.local, BOOT, rig.clock.cancelled, side="parent")
            with self.assertRaisesRegex(Exception, "COLLECT_BIND_ONCE"):
                clock.bind_parent(object())

    def test_reentry_boolean_caps_and_wrong_transfer_floors_refuse(self):
        with Rig() as rig:
            clock, _inputs, _expected = rig.input()
            def reenter():
                try:
                    clock.now()
                except Exception:
                    pass
            rig.clock.callback = reenter
            with self.assertRaisesRegex(Exception, "COLLECT_CLOCK_REENTRY"):
                clock.now()
            rig.clock.callback = lambda: None
            with self.assertRaisesRegex(Exception, "COLLECT_CLOCK_REENTRY"):
                clock.now()
        with Rig() as rig:
            clock, _inputs, _expected = rig.input()
            with self.assertRaises(Exception):
                clock.deadline(True)
        with Rig() as rig:
            changed = rehash_bundle(rig.packets.raws, step=lambda value: value.update(lowerLocal=101.0))
            path = rig.custody / "returned" / D._EXPORT_STEP_FILE
            path.write_bytes(changed["step"])
            rig.env[D._COLLECT_STEP_HASH] = sha(changed["step"])
            with self.assertRaisesRegex(Exception, "COLLECT_BIND_ORIGINAL_FLOOR"):
                rig.input()

    def test_child_binding_catches_domain_callback_graph_substitution(self):
        with Rig() as rig:
            original = D.native.processes.ownership_domains
            changed = []
            def domains(chain, raw):
                result = original(chain, raw)
                active = next((frame for frame in frames() if frame.f_code.co_name == "bind_child"), None)
                if active is not None and "expected" in active.f_locals and not changed:
                    expected = active.f_locals["expected"]
                    object.__setattr__(expected, "__dict__", dict(expected.__dict__))
                    changed.append(True)
                return result
            with patch.object(D.native.processes, "ownership_domains", domains):
                with self.assertRaises(Exception):
                    rig.authority()
            self.assertEqual(changed, [True])
            self.assertEqual(rig.requests, [])


class SupplierAndLifetimeControls(unittest.TestCase):
    def test_real_new_bridge_preserves_source12_acquisition24_http8_and_finite_cut(self):
        with Rig() as rig:
            old_files = {path: sha(path.read_bytes()) for path in rig.custody.rglob("*") if path.is_file()}
            result = rig.closed()
            clock, inputs, _raw, originals, match, captured = D._checked_collect_authority(result.authority)
            self.assertEqual([len(query.queries) for query in rig.queries], [12, 24, 12])
            self.assertTrue(all(query.close_calls == 1 and query.finalizers == [None] for query in rig.queries))
            self.assertEqual([name for name, _raw in rig.requests], list(D.N.HTTP_KEYS))
            self.assertEqual(tuple(name for name, _raw in captured[1]), D.N.ORIGINAL_KEYS)
            self.assertEqual(list(D.N._service_job(captured, clock.clock)), rig.packets.transfer["originalServiceJob"])
            self.assertEqual(match.record, rig.packets.match.record)
            self.assertEqual(len(rig.scopes), 1)
            self.assertTrue(rig.scopes[0].closed)
            self.assertEqual(rig.scopes[0].close_calls, 1)
            saved = D._COLLECT_AUTHORITY_RETURNS[id(result.authority)]
            owner = saved[6]
            self.assertTrue(owner.known().closed)
            self.assertEqual(owner.phase_originals.context, dict(originals)["context.json"])
            self.assertFalse(owner._anchor().phase_active)
            self.assertEqual(owner._anchor().phase[1:3], (clock.work, clock.work))
            self.assertNotIn(D.O.wire.TOKEN_ENV, rig.env)
            self.assertNotIn(TOKEN.encode("ascii"), b"".join(raw for _name, raw in originals))
            self.assertEqual({path: sha(path.read_bytes()) for path in old_files}, old_files)
            final = json.loads(result.raw)
            self.assertEqual(final["predecessor"]["step"], "initial-custody-export")
            self.assertEqual(final["originalWindow"], rig.packets.transfer["originalWindow"])
            self.assertEqual(set(json.loads(rig.packets.raws["manifest"])["copy"]["origins"]), set(D.ORIGINS))
            self.assertEqual(final["writerReturn"], "PENDING_OWNER_CLOSE")
            self.assertEqual(final["originalStepOutcome"], "NOT_OBSERVED")
            self.assertFalse(final["exportSaveAuthority"])

    def test_worker_new_phase_uses_same_fixed_route_and_stricter_inner_end(self):
        with Rig("worker") as rig:
            result = rig.closed()
            clock, limit, values = D._checked_collect_closed(result)
            self.assertEqual(clock.work, clock.first + 30 * NS)
            self.assertGreater(limit, clock.work)
            self.assertEqual(rig.scopes[0].launches[0]["requestedArgv"][5], "_post-export-authority")
            self.assertEqual(set(values), {"initialCustodySha256", "initialExporterReturnSha256"})

    def test_dirty_source_refuses_before_child_and_changed_final_source_refuses_return(self):
        for phase, ordinal, replacement in (("source-before", 1, b"?? changed\n"), ("source-after", 8, b"3" * 40 + b"\n")):
            with self.subTest(phase=phase), Rig() as rig:
                rig.query_hook = lambda supplier, index, raw: replacement if supplier.path.name == phase and index == ordinal else raw
                with self.assertRaises(Exception):
                    rig.authority()
                self.assertEqual(D._COLLECT_AUTHORITY_RETURNS, {})
                if phase == "source-before":
                    self.assertEqual((rig.scopes, rig.requests), ([], []))
                else:
                    self.assertEqual(len(rig.requests), 8)

    def test_fresh_job_tuple_is_compared_not_used_to_replace_original_basis(self):
        with Rig() as rig:
            def body(name, raw):
                if name != "jobs":
                    return raw
                value = json.loads(raw)
                value["jobs"][0]["runner_id"] += 1  # Still valid new service data; differs from original tuple.
                return wire(value)
            rig.http_hook = body
            with self.assertRaisesRegex(Exception, "COLLECT_CURRENT_MATCH_OR_ORIGINAL_JOB"):
                rig.authority()
            self.assertEqual(len(rig.requests), 8)
            self.assertEqual(D._COLLECT_AUTHORITY_RETURNS, {})

    def test_actual_acquirer_refuses_changed_owner_and_environment_authority(self):
        for changed in ("comment", "environment"):
            with self.subTest(changed=changed), Rig() as rig:
                def body(name, raw):
                    if name != changed:
                        return raw
                    value = json.loads(raw)
                    if name == "comment":
                        value["user"]["id"] += 1
                    else:
                        value["can_admins_bypass"] = True
                    return wire(value)
                rig.http_hook = body
                with self.assertRaises(Exception):
                    rig.authority()
                self.assertEqual(D._COLLECT_AUTHORITY_RETURNS, {})
                self.assertTrue(any(name == changed for name, _raw in rig.requests))

    def test_query_roster_truncation_is_not_a_successful_parsed_match_shortcut(self):
        with Rig() as rig:
            def change(supplier, value):
                if supplier.path.name == "acquisition-queries":
                    value["queries"] = value["queries"][:-1]
            rig.session_hook = change
            with self.assertRaisesRegex(Exception, "GATE_QUERY_SESSION"):
                rig.authority()
            self.assertEqual(len(rig.queries[1].queries), 24)
            self.assertEqual(len(rig.requests), 8)
            self.assertEqual(D._COLLECT_AUTHORITY_RETURNS, {})

    def test_new_context_exact_scope_and_fixed_command_reject_arbitrary_route(self):
        with Rig() as rig:
            result = rig.authority()
            context_raw = dict(result.originals)["context.json"]
            context = json.loads(context_raw)
            command = D.native.phase_command(context_raw, 1180 * NS)
            self.assertEqual(command[4:6], [str(M.ROOT / "scripts/run-hosted-initial-recipient-custody.py"), "_post-export-authority"])
            self.assertEqual(context["edge"], "POST_EXPORT")
            for name, value in (("scope", D.native.INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE), ("edge", "PRE_EXPORT"),
                    ("session", str(rig.custody / "authority-1")), ("continuationEndNs", context["continuationEndNs"] + 1)):
                with self.subTest(name=name):
                    with self.assertRaises(Exception):
                        D._collect_context(wire({**context, name: value}), rig.clock.identity)

    def test_new_scope_keeps_selected_git_and_windows_no_cwd_search_grammar(self):
        # Windows-shaped search-policy inputs ONLY: no Windows/native backend.
        with Rig() as rig:
            context = {"scope": D.native.INITIAL_COLLECT_AUTHORITY_CONTEXT_SCOPE}
            selected = D.native._initial_service_environment(rig.custody, context, str(rig.git))
            self.assertEqual(selected["PATH"], str(rig.git.parent))
            with self.assertRaises(Exception):
                D.native._initial_service_environment(rig.custody, context, None)
            windows_git = rig.git.with_name("git.exe")
            M.put(windows_git, b"SUPPLIED_WINDOWS_GIT_PATH_NOT_AN_EXECUTABLE\n")
            with patch.object(D.native.os, "name", "nt"):
                selected = D.native._initial_service_environment(rig.custody, context, str(windows_git))
            self.assertEqual(selected["PATH"], str(windows_git.parent))
            self.assertEqual(selected["PATHEXT"], ".EXE")
            self.assertEqual(selected["NoDefaultCurrentDirectoryInExePath"], "1")
            supplier = SimpleNamespace(executable=str(windows_git))
            with rig.environment(selected), patch.object(D.N.os, "name", "nt"):
                D.N._initial_service_query_git(supplier)
                for name, value in (("PATH", str(windows_git.parent) + M.os.pathsep + "."),
                        ("PATHEXT", ".COM;.EXE"), ("NoDefaultCurrentDirectoryInExePath", "0")):
                    with self.subTest(name=name):
                        original = selected[name]
                        selected[name] = value
                        with self.assertRaises(Exception):
                            D.N._initial_service_query_git(supplier)
                        selected[name] = original

    def test_actual_native_return_record_tuple_replacement_is_not_original(self):
        with Rig() as rig:
            result = rig.authority()
            owner = D._COLLECT_AUTHORITY_RETURNS[id(result)][6]
            phase = owner.phase_originals
            object.__setattr__(phase, "records", tuple(list(phase.records)))
            with self.assertRaisesRegex(Exception, "COLLECT_PHASE_RETURN_CHANGED|HISTORY_CHANGED"):
                D._checked_collect_authority(result)

    def test_returned_scope_remains_owned_when_post_allocation_callback_fails(self):
        with Rig() as rig:
            failure = M.FalseyFailure("SUPPLIED_AFTER_SCOPE_RETURN")
            original = rig.scope
            def allocate(*args):
                scope = original(*args)
                rig.clock.callback = lambda: (_ for _ in ()).throw(failure)
                return scope
            with patch.object(D.native.processes, "make_scope", allocate):
                with self.assertRaises(M.FalseyFailure) as caught:
                    rig.authority()
            self.assertIs(caught.exception, failure)
            scope = rig.scopes[0]
            owners = [anchor for anchor in D._CUSTODY_OWNERS.values() if any(resource is scope for _r, _l, resource, _a, _c in anchor.rows)]
            self.assertEqual(len(owners), 1)
            self.assertIs(owners[0].failure, failure)
            self.assertEqual(D._COLLECT_AUTHORITY_RETURNS, {})
            self.assertTrue(scope.drains)
            self.assertLessEqual(scope.drains[0][2], rig.original_local_end)

    def test_query_and_scope_close_unknown_keep_falsey_first_failure_without_retry(self):
        for target in ("query", "scope"):
            with self.subTest(target=target), Rig() as rig:
                failure = M.FalseyFailure("SUPPLIED_" + target.upper() + "_CLOSE_UNKNOWN")
                if target == "query":
                    rig.query_close_error = failure
                else:
                    rig.scope_close_error = failure
                with self.assertRaises(M.FalseyFailure) as caught:
                    rig.authority()
                self.assertIs(caught.exception, failure)
                self.assertEqual(D._COLLECT_AUTHORITY_RETURNS, {})
                self.assertNotIn(D.O.wire.TOKEN_ENV, rig.env)
                self.assertTrue(D.native.QUARANTINE)
                if target == "scope":
                    self.assertEqual(rig.scopes[0].close_calls, 1)
                else:
                    self.assertEqual(rig.queries[0].close_calls, 1)


@dataclass(frozen=True)
class EqualFinalType:
    authority: object
    raw: bytes
    metadata_close: bytes


class OutputControls(unittest.TestCase):
    def test_real_final_file_append_exact_pair_and_two_original_late_checks(self):
        with Rig() as rig:
            result = rig.closed()
            value, fence, limit = D._CollectOutputFence(result).append()
            expected = {"initialCustodySha256": sha(result.raw), "initialExporterReturnSha256": sha(rig.packets.raws["manifest"])}
            self.assertEqual(rig.output.read_bytes(), "".join(name + "=" + expected[name] + "\n" for name in sorted(expected)).encode("ascii"))
            self.assertEqual(limit, rig.packets.transfer["originalWindow"]["readEndNs"])
            self.assertFalse(value["exportSaveAuthority"])
            fence.now(final=True, limit=limit)
            fence.now(final=True, limit=limit)
            with self.assertRaisesRegex(Exception, "EXACT_LATE_CHECK"):
                fence.now(final=True, limit=limit)
            with self.assertRaises(Exception):
                D._CollectOutputFence(result)

    def test_wrong_output_phase_final_limit_or_equal_binding_consumes_fence(self):
        for changed in ("before-append", "final", "limit", "binding"):
            with self.subTest(changed=changed), Rig() as rig:
                result, _clock = rig.export_step()
                fence = D._CollectOutputFence(result)
                if changed == "before-append":
                    limit = rig.packets.transfer["originalWindow"]["readEndNs"]
                else:
                    _value, _fence, limit = fence.append()
                original = fence._binding
                if changed == "binding":
                    fence._binding = tuple(list(original))
                with self.assertRaises(Exception) as caught:
                    fence.now(final=changed != "final", limit=limit + (1 if changed == "limit" else 0))
                fence._binding = original
                with self.assertRaises(Exception) as repeated:
                    fence.now(final=True, limit=limit)
                self.assertIs(caught.exception, repeated.exception)

    def test_append_short_write_fsync_readback_and_unknown_close_are_failures(self):
        for changed in ("write", "fsync", "read", "close"):
            with self.subTest(changed=changed), Rig() as rig:
                result, _clock = rig.export_step()
                failure = M.FalseyFailure("SUPPLIED_APPEND_" + changed)
                original = getattr(D.C.os, changed)
                if changed == "write":
                    replacement = lambda descriptor, raw: original(descriptor, raw[:-1])
                elif changed == "read":
                    replacement = lambda descriptor, count: original(descriptor, count) + b"X"
                elif changed == "close":
                    def replacement(descriptor):
                        original(descriptor)  # Actually retire the tiny fd; simulate an ambiguous return afterward.
                        raise failure
                else:
                    replacement = lambda _descriptor: (_ for _ in ()).throw(failure)
                fence = D._CollectOutputFence(result)
                with patch.object(D.C.os, changed, replacement):
                    with self.assertRaises(Exception):
                        fence.append()
                self.assertIsNotNone(D._COLLECT_OUTPUTS[id(fence)][2]["failure"])
                with self.assertRaises(Exception):
                    fence.append()
                if changed == "close":
                    self.assertTrue(D.C.QUARANTINE)

    def test_guarded_flush_restore_cancellation_and_second_check_fail_after_output(self):
        for changed in ("flush", "restore", "cancel", "second"):
            with self.subTest(changed=changed), Rig() as rig:
                result, _clock = rig.export_step()
                value, fence, limit = D._CollectOutputFence(result).append()
                failure = M.FalseyFailure("SUPPLIED_GUARDED_" + changed)
                output = io.BytesIO()
                class Buffer:
                    def write(self, raw):
                        return output.write(raw)
                    def flush(self):
                        if changed == "flush":
                            raise failure
                        if changed == "cancel":
                            rig.clock.callback = lambda: (_ for _ in ()).throw(failure)
                if changed == "restore":
                    rig.signal_hook = lambda _number, handler: (_ for _ in ()).throw(failure) if handler == "SUPPLIED_PREVIOUS_HANDLER" else None
                if changed == "second":
                    def cancel():
                        if D._COLLECT_OUTPUTS[id(fence)][2]["checks"] == 2:
                            raise failure
                    rig.clock.callback = cancel
                with patch.object(D.native, "sys", SimpleNamespace(**{**vars(sys), "stdout": SimpleNamespace(buffer=Buffer())})):
                    with self.assertRaises(M.FalseyFailure) as caught:
                        D.native.guarded(lambda _signals: (value, fence, limit))
                self.assertIs(caught.exception, failure)
                if changed != "restore":
                    self.assertTrue(output.getvalue())
                else:
                    self.assertEqual(output.getvalue(), b"")

    def test_last_currency_callback_of_second_final_output_cannot_change_own_return(self):
        for changed in ("raw", "metadata", "type"):
            with self.subTest(changed=changed), Rig() as rig:
                result = rig.closed()
                value, fence, limit = D._CollectOutputFence(result).append()
                metadata = D._COLLECT_RETURNS[id(result)][8]
                calls = []
                def mutate():
                    if D._COLLECT_OUTPUTS[id(fence)][2]["checks"] != 2 or not any(
                            frame.f_code.co_name == "_collect_authority_currency" for frame in frames()):
                        return
                    calls.append(True)
                    if len(calls) != 2:  # Last currency of the final guarded check, not an earlier redundant guard.
                        return
                    if changed == "raw":
                        result.__dict__["raw"] = b"SUPPLIED_LAST_CALLBACK_CHANGE\n"
                    elif changed == "metadata":
                        metadata.owner.resources[-1]["closed"] = False
                    else:
                        object.__setattr__(result, "__class__", EqualFinalType)
                rig.clock.callback = mutate
                output = io.BytesIO()
                with patch.object(D.native, "sys", SimpleNamespace(**{**vars(sys), "stdout": SimpleNamespace(buffer=output)})):
                    with self.assertRaises(Exception) as caught:
                        D.native.guarded(lambda _signals: (value, fence, limit))
                self.assertEqual(len(calls), 2)
                self.assertTrue(output.getvalue())
                rig.clock.callback = lambda: None
                with self.assertRaises(Exception) as repeated:
                    fence.now(final=True, limit=limit)
                self.assertIs(repeated.exception, caught.exception)

    def test_last_currency_callback_of_second_export_output_cannot_change_transfer(self):
        with Rig() as rig:
            result, _clock = rig.export_step()
            value, fence, limit = D._CollectOutputFence(result).append()
            calls = []
            def mutate():
                if D._COLLECT_OUTPUTS[id(fence)][2]["checks"] == 2 and any(
                        frame.f_code.co_name == "currency" for frame in frames()):
                    calls.append(True)
                    if len(calls) == 2:
                        result.__dict__["raw"] = b"SUPPLIED_LAST_TRANSFER_CHANGE\n"
            rig.clock.callback = mutate
            output = io.BytesIO()
            with patch.object(D.native, "sys", SimpleNamespace(**{**vars(sys), "stdout": SimpleNamespace(buffer=output)})):
                with self.assertRaises(Exception):
                    D.native.guarded(lambda _signals: (value, fence, limit))
            self.assertEqual(len(calls), 2)
            self.assertTrue(output.getvalue())
            self.assertIsNotNone(D._COLLECT_OUTPUTS[id(fence)][2]["failure"])

    def test_final_return_without_actual_parent_or_metadata_registry_is_refused(self):
        with Rig() as rig:
            result = rig.closed()
            replacement = D._CollectClosed(result.authority, result.raw, result.metadata_close)
            with self.assertRaisesRegex(Exception, "NOT_ORIGINAL_FINAL_RETURN"):
                D._checked_collect_closed(replacement)
            metadata = D._COLLECT_RETURNS[id(result)][8]
            failure = M.FalseyFailure("SUPPLIED_METADATA_CLOSE_ERROR")
            metadata.remember(failure, unknown=True)
            with self.assertRaises(Exception):
                D._checked_collect_closed(result)
            self.assertIs(metadata.failure, failure)

    def test_output_allowlist_rejects_paths_and_plaintext_or_partial_pairs(self):
        with Rig() as _rig:
            for values in ({"initialCustodySha256": "a" * 64}, {"path": "a" * 64},
                    {"initialCustodySha256": "a" * 64, "initialExporterReturnSha256": "b" * 64, "publicKey": "c" * 64},
                    {"initialCryptoStepSha256": "../private", "initialExporterReturnSha256": "b" * 64}):
                with self.subTest(keys=tuple(values)):
                    with self.assertRaises(Exception):
                        D.C.append_outputs(values, lambda: None)


if __name__ == "__main__":
    unittest.main()
