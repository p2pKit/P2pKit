#!/usr/bin/env python3
"""New flat-tail E models only; no native/GPG/custody/hosted qualification.

Reuse fixture constructors, NOT earlier test methods. K admission/native
suppliers are explicit in-memory models; the maintained TD/CD parsers and E
implementation are real. No installed key, file owner, process, network or
private evidence is acquired. The inherited audit hook forbids actual effects.
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))


def fixture(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


F = fixture("productive_tail_e_fixture", "hosted-initial-recipient-productive-evidence-test.py")
CF = fixture("productive_tail_e_data_fixture", "hosted-initial-recipient-productive-custody-data-test.py")
import hosted_initial_recipient_productive_tail as K
import hosted_initial_recipient_productive_tail_data as TD

E, P, PC, CD, NS = F.E, F.P, F.PC, F.CD, F.NS
REFUSALS = (E.posix.EvidenceError, P.O.OriginError)
canonical = F.canonical


class TailFacadeModels(unittest.TestCase):
    # Explicit helper reuse without inheriting/discovering any earlier tests.
    install = F.ProductiveFacadeModels.install
    local_now = F.ProductiveFacadeModels.local_now
    observe = F.ProductiveFacadeModels.observe
    unguard = staticmethod(F.ProductiveFacadeModels.unguard)
    admit_validation = F.ProductiveFacadeModels.admit_validation
    live_validation = F.ProductiveFacadeModels.live_validation
    retired_validation = F.ProductiveFacadeModels.retired_validation
    admit_archive = F.ProductiveFacadeModels.admit_archive
    live_archive = F.ProductiveFacadeModels.live_archive
    archive_liveness = F.ProductiveFacadeModels.archive_liveness
    retired_archive = F.ProductiveFacadeModels.retired_archive

    def setUp(self):
        self.mutations = []
        self.snapshot_action = self.node_action = lambda _value: None
        self.backend_known = True
        self.utc_calls = 0
        F.ProductiveFacadeModels.setUp(self)
        self.install(E, "time", SimpleNamespace(time=self.utc_now, monotonic=self.local_now))
        for name, callback in (("checked_child_validation", self.admit_validation),
                ("check_child_validation", self.live_validation), ("checked_retired_child_validation", self.retired_validation),
                ("checked_child_archive", self.admit_archive), ("check_child_archive", self.live_archive),
                ("archive_liveness", self.archive_liveness), ("check_retired_child_archive", self.retired_archive)):
            self.install(K, name, callback)

    def utc_now(self):
        if self.forbid_observation:
            raise AssertionError("PASSIVE_TAIL_CHECK_MUST_NOT_OBSERVE_UTC")
        self.utc_calls += 1
        return self.utc

    def fresh(self):
        F.ProductiveFacadeModels.fresh(self)
        self.child, self.archive = K.TailChild(), K.TailArchiveBinding()
        self.work = Path("/synthetic/productive-tail/tail-public-crypto")
        source = K.TailChildSourceBinding(*[getattr(self.validation.source, name) for name in E._SOURCE_FIELDS])
        caps = K.TailValidationCaps(*[getattr(self.validation.caps, name) for name in E._CAP_FIELDS])
        self.validation = K.TailValidationView(self.child, "linux-x64", self.work, self.key, F.F.POLICY,
            self.match_raw, source, caps)
        self.recipient = dataclasses.replace(self.recipient, work_dir=self.work, home=self.work / "gnupg")

    def checked_backend(self, result, binding):
        if not self.backend_known:
            raise E.posix.EvidenceError("MODEL_BACKEND_CLOSE_NOT_CONFIRMED")
        return F.ProductiveFacadeModels.checked_backend(self, result, binding)

    def backend_validation(self, binding):
        self.assertIs(E._checked_productive_validation_binding(binding), self.validation)
        return F.ProductiveFacadeModels.backend_validation(self, binding)

    def backend_export(self, binding):
        if type(self.view) is PC.ArchiveView:
            return F.ProductiveFacadeModels.backend_export(self, binding)
        self.backend_calls.append("export")
        self.backend_action()
        self.assertIs(E._checked_productive_export_binding(binding), self.view)
        nodes = (self.view.payload_root, *self.view.members, self.view.map)
        snapshot = {node.relative: node.native[1:] for node in nodes}
        self.snapshot_action(snapshot)
        self.assertIs(E._productive_check_snapshot(binding, snapshot), snapshot)
        selected = E._productive_expected_node(binding, self.view.members[0].relative)
        self.node_action(selected)
        self.assertIs(E._productive_node_guard(binding, selected), selected)
        cap = E._productive_keyring_begin(binding)
        self.assertIs(E._productive_keyring_guard(binding, cap), cap)
        self.assertIs(E._productive_keyring_complete(binding, cap), cap)
        raw = E._productive_manifest(binding, "f" * 64, 100)
        artifact = E.posix._ProductiveArtifact(E.posix.ARTIFACT, "f" * 64, 100,
            ("posix", 1, 99999, stat.S_IFREG | 0o600, 1, 1, 100, 1, 1))
        result = E.posix._ProductiveExportReturn(binding, object(), raw, artifact, (object(),), object())
        self.backend_results.append(result)
        return result

    def archive_view(self):
        # Only final public DATA construction is borrowed. It is not a final
        # custody run or a hash-restored original K parent. TD parses it for real.
        final_view = F.ProductiveFacadeModels.archive_view(self)
        final = json.loads(final_view.public_inputs)
        rows = CF.groups()
        count = sum(row["dataFiles"] for row in rows)
        copied = final["copy"]
        copied.update(groups=rows, dataFiles=count, archiveFiles=count + 31, archiveNativeNodes=count + 62,
            plaintextBytes=sum(row["dataBytes"] + row["map"]["bytes"] for row in rows) + copied["index"]["bytes"])
        final.update(scope="ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_PRODUCTIVE_EVIDENCE_V1",
            recipient={"fingerprint": self.recipient.fingerprint, "encryptionFingerprint": self.recipient.encryption_fingerprint,
                "keySha256": self.recipient.key_sha256, "expiresAt": self.recipient.expires_at},
            artifact={"name": "evidence.tar.gz.gpg", "sha256": "d" * 64, "size": 100},
            testAcceptance="NOT_PERFORMED", productiveAuthority=False, cacheAuthority=False,
            exportSaveAuthority=False, budgetAcceptance="NOT_ADMITTED")
        self.final_raw = canonical(final)
        CD.public_manifest(self.final_raw)
        serial = 1

        def node(name, raw=None):
            nonlocal serial
            directory = raw is None
            value = K.ExpectedNode(name, "directory" if directory else "file", None if directory else len(raw),
                None if directory else hashlib.sha256(raw).hexdigest(), ("posix", 1, serial,
                    (stat.S_IFDIR | 0o700) if directory else (stat.S_IFREG | 0o600), 1,
                    2 if directory else 1, 4096 if directory else len(raw), 1, 1), object())
            serial += 1
            return value

        root, members, groups = node(""), [], {}
        counts = (11, 279, 2, 7, 0, 280, 1, 280, 5, 13)
        for index, (name, count) in enumerate(zip(TD.GROUPS, counts)):
            raw = b"s" * (index + 1)
            for _ in range(count):
                members.append(node("member-" + str(len(members)).zfill(5) + ".bin", raw))
            groups[name] = {"memberCount": count, "totalBytes": count * len(raw)}
        mapped = node("custody-tail-map.json", b'{"synthetic":true}\n')
        cut = {"mapName": mapped.relative, "mapSha256": mapped.sha256, "mapBytes": mapped.bytes,
            "memberCount": len(members) + 1, "totalBytes": sum(item.bytes for item in members) + mapped.bytes,
            "groups": groups}
        inputs = TD.manifest_inputs(self.final_raw, {name: "b" * 64 for name in TD.PREDECESSOR_FIELDS}, cut)
        caps = K.TailArchiveCaps(*[getattr(final_view.caps, name) for name in E._CAP_FIELDS])
        self.view = K.TailArchiveView(self.child, self.archive, self.recipient, "linux-x64",
            Path("/synthetic/productive-tail/tail-copied-evidence"), Path("/synthetic/productive-tail/tail-export-output"),
            root, tuple(members), mapped, object(), caps, inputs)
        return self.view

    def validate(self):
        return E.validate_initial_productive_tail_recipient(self.child)

    def export(self):
        return E.export_initial_productive_tail_encrypted(self.child, self.archive, self.recipient)

    def prepared(self):
        validation = self.validate()
        self.archive_view()
        return validation

    def public_change(self, change):
        value = json.loads(self.view.public_inputs)
        change(value)
        object.__setattr__(self.view, "public_inputs", canonical(value))

    def refuses(self, function, *args):
        with self.assertRaises(REFUSALS) as caught:
            function(*args)
        return caught.exception

    def test_00_real_facade_and_data_join_register_flat_tail_only(self):
        validation = self.prepared()
        result = self.export()
        self.assertIs(E.checked_productive_tail_validation_return(validation, self.child), validation)
        self.assertIs(E.checked_productive_tail_backend_return(result, self.view), result)
        final, tail = TD.join_manifests(self.final_raw, result.manifest_raw)
        self.assertEqual(tail["final"]["manifestSha256"], hashlib.sha256(self.final_raw).hexdigest())
        self.assertEqual(tail["recipient"], final["recipient"])
        self.assertEqual(tail["cut"]["memberCount"], len(self.view.members) + 1)
        self.assertEqual(tail["finalPrivateOriginals"]["requiredEvidence"], "NOT_USED_AS_QUALIFICATION_ORIGINALS")
        self.assertNotIn("copy", tail)
        self.assertFalse(hasattr(self.view, "partitions"))
        state = E._PRODUCTIVE_ATTEMPTS[("export", id(self.child))]
        self.assertEqual(len(state["nodes"]), len(self.view.members) + 2)
        self.assertNotIn("partition_pins", state)
        self.assertEqual(self.backend_calls, ["validation", "export"])

    def test_tail_returns_never_pass_final_result_checkers(self):
        validation = self.prepared()
        result = self.export()
        for function, value, target in ((E.checked_productive_validation_return, validation, self.child),
                (E.checked_retired_productive_validation_return, validation, self.child),
                (E.checked_productive_backend_return, result, self.view),
                (E.checked_retired_productive_backend_return, result, self.view)):
            with self.subTest(function=function.__name__):
                self.refuses(function, value, target)
        self.assertIs(E.checked_productive_tail_backend_return(result, self.view), result)

    def test_final_returns_never_pass_tail_result_checkers(self):
        F.ProductiveFacadeModels.fresh(self)
        validation = E.validate_initial_productive_recipient(self.child)
        F.ProductiveFacadeModels.archive_view(self)
        result = E.export_initial_productive_encrypted(self.child, self.archive, self.recipient)
        for function, value, target in ((E.checked_productive_tail_validation_return, validation, self.child),
                (E.checked_retired_productive_tail_validation_return, validation, self.child),
                (E.checked_productive_tail_backend_return, result, self.view),
                (E.checked_retired_productive_tail_backend_return, result, self.view)):
            with self.subTest(function=function.__name__):
                self.refuses(function, value, target)
        self.assertIs(E.checked_productive_backend_return(result, self.view), result)

    def test_final_entry_cannot_admit_tail_view_or_be_retried_under_tail_name(self):
        first = self.refuses(E.validate_initial_productive_recipient, self.child)
        self.assertIs(self.refuses(self.validate), first)
        self.assertEqual(self.backend_calls, [])

    def test_tail_entry_cannot_admit_final_child_or_restart_final_entry(self):
        F.ProductiveFacadeModels.fresh(self)
        first = self.refuses(self.validate)
        self.assertIs(self.refuses(E.validate_initial_productive_recipient, self.child), first)
        self.assertEqual(self.backend_calls, [])

    def test_unregistered_tail_binding_has_no_backend_authority(self):
        self.refuses(E._checked_productive_validation_binding, E._ProductiveTailValidationBinding(self.validation))
        self.assertEqual(E._PRODUCTIVE_BINDINGS, {})

    def test_equal_result_and_equal_child_are_not_originals(self):
        result = self.validate()
        self.refuses(E.checked_productive_tail_validation_return, dataclasses.replace(result), self.child)
        self.refuses(E.checked_productive_tail_validation_return, result, K.TailChild())

    def test_caught_cross_route_reentry_preserves_original_failure(self):
        errors = []
        def reenter():
            self.mutations.append("cross-route")
            errors.append(self.refuses(E.validate_initial_productive_recipient, self.child))
        self.admission_action = reenter
        self.assertIs(self.refuses(self.validate), errors[0])
        self.assertEqual(self.mutations, ["cross-route"])
        self.assertEqual(self.backend_calls, [])

    def test_family_mutation_during_backend_callback_is_sticky(self):
        def mutate():
            self.mutations.append("family")
            E._PRODUCTIVE_ATTEMPTS[("validation", id(self.child))]["family"] = "final"
        self.backend_action = mutate
        error = self.refuses(self.validate)
        self.assertEqual(self.mutations, ["family"])
        self.assertIs(self.refuses(self.validate), error)

    def test_controller_graph_change_during_admission_is_not_adopted(self):
        self.install(K.R, "P", P)
        def mutate():
            self.mutations.append("graph")
            K.R.P = SimpleNamespace()
        self.admission_action = mutate
        self.refuses(self.validate)
        self.assertEqual(self.mutations, ["graph"])
        self.assertEqual(self.backend_calls, [])

    def test_data_constant_mutation_keeps_its_original_content_pin(self):
        self.install(TD, "FIXED_COUNTS", dict(TD.FIXED_COUNTS))
        def mutate():
            self.mutations.append("constant")
            TD.FIXED_COUNTS[TD.GROUPS[0]] = 1
        self.admission_action = mutate
        self.refuses(self.validate)
        self.assertEqual(self.mutations, ["constant"])
        self.assertEqual(self.backend_calls, [])

    def test_replaced_tail_parser_during_admission_never_runs(self):
        self.install(TD, "public_inputs", TD.public_inputs)
        invoked = []
        def mutate():
            self.mutations.append("parser")
            TD.public_inputs = lambda _raw: invoked.append("replacement")
        self.admission_action = mutate
        self.refuses(self.validate)
        self.assertEqual(self.mutations, ["parser"])
        self.assertEqual(invoked, [])

    def test_equal_recipient_cannot_enter_tail_export(self):
        self.prepared()
        self.recipient = dataclasses.replace(self.recipient)
        self.refuses(self.export)
        self.assertEqual(self.backend_calls, ["validation"])

    def test_equal_members_tuple_replacement_in_callback_refuses(self):
        self.prepared()
        def mutate():
            self.mutations.append("members")
            object.__setattr__(self.view, "members", tuple(list(self.view.members)))
        self.backend_action = mutate
        self.refuses(self.export)
        self.assertEqual(self.mutations, ["members"])

    def test_map_cannot_alias_a_member_native_identity(self):
        self.prepared()
        native = self.view.map.native
        object.__setattr__(self.view.map, "native", (*self.view.members[0].native[:3], *native[3:]))
        self.refuses(self.export)
        self.assertEqual(self.backend_calls, ["validation"])

    def test_noncontiguous_or_partitioned_member_name_refuses(self):
        self.prepared()
        object.__setattr__(self.view.members[0], "relative", "partition/member-00000.bin")
        self.refuses(self.export)

    def test_incomplete_native_vector_refuses(self):
        self.prepared()
        object.__setattr__(self.view.members[0], "native", self.view.members[0].native[:-1])
        self.refuses(self.export)

    def test_group_byte_redistribution_cannot_preserve_false_total(self):
        self.prepared()
        def change(value):
            value["cut"]["groups"][TD.GROUPS[0]]["totalBytes"] += 1
            value["cut"]["groups"][TD.GROUPS[1]]["totalBytes"] -= 1
        self.public_change(change)
        TD.public_inputs(self.view.public_inputs)  # Deliberately valid DATA totals; actual node slices disagree.
        self.refuses(self.export)

    def test_declared_map_hash_cannot_replace_original_map_node(self):
        self.prepared()
        self.public_change(lambda value: value["cut"].update(mapSha256="a" * 64))
        self.refuses(self.export)

    def test_public_event_hash_must_match_original_tail_source_binding(self):
        self.prepared()
        self.public_change(lambda value: value["github"].update(eventSha256="a" * 64))
        self.refuses(self.export)

    def test_windows_flat_node_and_group_grammar_uses_its_actual_counts(self):
        self.prepared()
        # Direct helper DATA test ONLY: no Windows admission/native owner claim.
        original = self.view
        def node(source, number, *, directory=False):
            return dataclasses.replace(source, native=("windows", 1, f"{number:032x}", directory,
                0 if directory else source.bytes, 1, 16 if directory else 0, 1, 1, 1, "S-1-5-21", True))
        groups, members, offset = {}, [], 0
        prior = json.loads(original.public_inputs)
        for name, count in zip(TD.GROUPS, (11, 279, 2, 4, 0, 280, 1, 280, 5, 12)):
            source_count = prior["cut"]["groups"][name]["memberCount"]
            selected = original.members[offset:offset + count]
            offset += source_count
            groups[name] = {"memberCount": count, "totalBytes": sum(item.bytes for item in selected)}
            for source in selected:
                members.append(node(dataclasses.replace(source,
                    relative="member-" + str(len(members)).zfill(5) + ".bin"), len(members) + 2))
        view = dataclasses.replace(original, role="windows-x64", payload_root=node(original.payload_root, 1, directory=True),
            members=tuple(members), map=node(original.map, len(members) + 2))
        state = {"family": "tail", "PC": K, "binding": E._ProductiveTailExportBinding(view)}
        E._productive_nodes(state)
        prior["cut"].update(groups=groups, memberCount=len(members) + 1,
            totalBytes=sum(item.bytes for item in members) + view.map.bytes)
        E._productive_tail_public_counts(state, prior)
        self.assertEqual(len(state["node_rows"]), len(members) + 2)
        prior["cut"]["groups"][TD.GROUPS[9]]["memberCount"] = 13
        self.refuses(E._productive_tail_public_counts, state, prior)

    def test_combined_final_and_tail_bound_is_not_two_separate_allowances(self):
        self.prepared()
        self.public_change(lambda value: value["final"].update(plaintextBytes=E.posix.MAX_BYTES))
        self.refuses(self.export)

    def test_optional_empty_group_must_also_have_zero_bytes(self):
        self.prepared()
        def change(value):
            value["cut"]["groups"][TD.GROUPS[4]]["totalBytes"] = 1
            value["cut"]["totalBytes"] += 1
        self.public_change(change)
        self.refuses(self.export)

    def test_native_snapshot_missing_original_member_refuses(self):
        self.prepared()
        def mutate(snapshot):
            self.mutations.append("snapshot")
            snapshot.pop(self.view.members[-1].relative)
        self.snapshot_action = mutate
        self.refuses(self.export)
        self.assertEqual(self.mutations, ["snapshot"])

    def test_selected_original_node_mutation_refuses_per_block(self):
        self.prepared()
        def mutate(node):
            self.mutations.append("selected-node")
            object.__setattr__(node, "sha256", "a" * 64)
        self.node_action = mutate
        self.refuses(self.export)
        self.assertEqual(self.mutations, ["selected-node"])

    def test_raw_validation_end_cannot_be_renewed_by_tail_route(self):
        def expire():
            self.mutations.append("raw")
            self.raw = self.validation.caps.workEndNs
        self.backend_action = expire
        self.refuses(self.validate)
        self.assertEqual(self.mutations, ["raw"])

    def test_local_export_end_cannot_borrow_outer_time(self):
        self.prepared()
        def expire():
            self.mutations.append("local")
            self.local = self.view.caps.workEndLocal
        self.backend_action = expire
        self.refuses(self.export)
        self.assertEqual(self.mutations, ["local"])

    def test_expired_current_policy_refuses_even_with_unspent_raw_cap(self):
        def expire():
            self.mutations.append("policy")
            self.utc = self.policy["expiresAt"]
        self.backend_action = expire
        self.refuses(self.validate)
        self.assertEqual(self.mutations, ["policy"])

    def test_tail_validation_cannot_claim_more_than_original_sixty(self):
        object.__setattr__(self.validation, "caps", dataclasses.replace(self.validation.caps,
            workEndNs=161 * NS, operationFinishEndNs=161 * NS))
        self.refuses(self.validate)
        self.assertEqual(self.backend_calls, [])

    def test_tail_keyring_keeps_original_thirty_and_duplicate_failure(self):
        self.prepared()
        state = E._productive_start(self.child, "export", family="tail")
        binding = E._productive_admit(state, self.archive, self.recipient)
        cap = E._productive_keyring_begin(binding)
        self.assertLessEqual(cap.workEndNs, self.raw + 30 * NS)
        self.assertLess(cap.workEndLocal, self.local + 30)
        error = self.refuses(E._productive_keyring_begin, binding)
        self.assertIs(self.refuses(E._productive_keyring_guard, binding, cap), error)

    def test_actual_backend_close_check_is_still_required(self):
        self.prepared()
        def refuse_close():
            self.mutations.append("close")
            self.backend_known = False
        self.backend_action = refuse_close
        self.refuses(self.export)
        self.assertEqual(self.mutations, ["close"])

    def test_retired_tail_returns_are_passive_not_renewed_caps(self):
        validation = self.prepared()
        result = self.export()
        self.retired, self.forbid_observation = True, True
        before = self.clock_calls, self.local_calls, self.utc_calls
        self.raw, self.local = 10 ** 15, 10 ** 12
        self.assertIs(E.checked_retired_productive_tail_validation_return(validation, self.child), validation)
        self.assertIs(E.checked_retired_productive_tail_backend_return(result, self.view), result)
        self.assertEqual((self.clock_calls, self.local_calls, self.utc_calls), before)

    def test_active_tail_cannot_be_claimed_retired(self):
        result = self.validate()
        with self.assertRaisesRegex(RuntimeError, "MODEL_CHILD_NOT_RETIRED"):
            E.checked_retired_productive_tail_validation_return(result, self.child)

    def test_original_return_completion_mutation_refuses_passively(self):
        result = self.validate()
        self.retired = True
        reading = result.observations[1][0]
        object.__setattr__(reading, "nanoseconds", reading.nanoseconds + 1)
        self.refuses(E.checked_retired_productive_tail_validation_return, result, self.child)


if __name__ == "__main__":
    unittest.main(failfast=True)
