#!/usr/bin/env python3
"""Authored Stage1 adapter models; no actual crypto, native owners or HTTP.

The existing staged fixture supplies only public policy and synthetic builders;
no old test method is invoked. Exporters, public event reads and guards are
explicit models. Windows roots below are supplied fake objects, NOT native
Windows qualification. Copy membership and genuine call/Step provenance remain
the fixed driver's separate controls, not evidence fabricated by these hashes.
"""
from __future__ import annotations

import ctypes  # Stdlib initialization before the no-native audit boundary.
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_evidence as E

_spec = importlib.util.spec_from_file_location("initial_evidence_stage_fixture",
    Path(__file__).with_name("hosted-initial-recipient-stages-test.py"))
F = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F)
I, S, G = E.I, E.S, E.G


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    # The actual maintained POSIX and Windows manifest-file encoding.
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")


class SuppliedDirectory:
    """No native calls or handles; exact shaped caller input to a mocked backend."""

    def __init__(self, name, number):
        self.path = Path("/synthetic") / name
        self.identity = (number, str(number) * 32)
        self._closed = False


class Stage1EvidenceModels(unittest.TestCase):
    def setUp(self):
        self.now = F.DONE1
        self.guard_calls = self.read_calls = 0
        self.guard_action = self.read_action = None
        self.returned = self.manifest_file = None
        self.factory_results = []
        self.native_roots = (SuppliedDirectory("crypto", 1), SuppliedDirectory("evidence", 2),
                             SuppliedDirectory("output", 3))
        self.select()
        self.env_view = SimpleNamespace(name="posix", environ=self.env)
        self.install(E, "os", self.env_view)
        self.install(E, "time", SimpleNamespace(time=lambda: self.now))
        self.install(E.windows.files, "PrivateDirectory", SuppliedDirectory)
        self.event_reader = self.install(I, "read_regular", side_effect=self.event_read)
        self.posix_exporter = self.install(E.posix, "_export_bound_manifest", side_effect=self.posix_export)
        self.windows_exporter = self.install(E.windows, "_export", side_effect=self.windows_export)
        for module, name in ((E.acquisition, "acquire_bootstrap"), (I, "admit"),
                             (E.posix, "_manifest_identity"), (E.posix, "validate_recipient"),
                             (E.windows, "validate_recipient")):
            self.install(module, name, side_effect=AssertionError("ADAPTER_MUST_NOT_ACQUIRE_OR_VALIDATE"))

    def install(self, target, name, value=None, **kwargs):
        manager = patch.object(target, name, **kwargs) if kwargs else patch.object(target, name, value)
        result = manager.start()
        self.addCleanup(manager.stop)
        return result

    def select(self, name="desktop-linux-x64", kind="worker"):
        self.kind, self.selection = kind, name
        declaration = F.stage1()
        observed = F.observation1(declaration, name)
        if kind == "worker":
            original = F.check1(declaration, observed)
        else:
            github = observed["github"]
            github.pop("profile")
            github.pop("selection")
            github.update(job=G.JOB, runnerOS="Linux", runnerArch="X64")
            observed["inputs"] = {"selection": name, "expected_sha": F.H1, "expected_tree": F.T1}
            comment = F.comment(declaration, 8001, F.START - 60)
            history = [{"state": "approved", "user": dict(F.OWNER),
                "comment": "AUTHORIZE_INITIAL_RECIPIENT stage1 " + github["runId"] + "/" +
                    github["runAttempt"] + " 8001 " + F.body_hash(comment),
                "environments": [{"id": 101, "name": S.ENVIRONMENT}]}]
            environment = {"id": 101, "name": S.ENVIRONMENT, "can_admins_bypass": False,
                "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
                "protection_rules": [{"type": "required_reviewers", "prevent_self_review": False,
                    "reviewers": [{"type": "User", "reviewer": dict(F.OWNER)}]}, {"type": "branch_policy"}]}
            original = G.eligible(stage="stage1", approvals_raw=wire(history), comment_raw=wire(comment),
                environment_raw=wire(environment), branches_raw=wire({"total_count": 2,
                    "branch_policies": F.ENVIRONMENT["branchPolicies"]}), observation_raw=wire(observed),
                now=F.DONE1, **F.policy_inputs())
        self.original, self.fresh = original, type(original)(original.record)
        self.event_raw = wire({"repository": {"full_name": I.REPOSITORY, "default_branch": "main"},
            "ref": S.SOURCE_REF, "inputs": {"selection": name, "expected_sha": F.H1, "expected_tree": F.T1}})
        github = I.parse(original.record, S.LIMIT)["github"]
        self.env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": I.REPOSITORY,
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": S.SOURCE_REF, "GITHUB_SHA": F.H1, "GITHUB_WORKFLOW_SHA": F.H1,
            "GITHUB_WORKFLOW_REF": I.REPOSITORY + "/" + S.bootstrap.WORKFLOW + "@" + S.SOURCE_REF,
            "GITHUB_JOB": github["job"], "GITHUB_RUN_ID": github["runId"], "GITHUB_RUN_ATTEMPT": "1",
            "RUNNER_OS": github["runnerOS"], "RUNNER_ARCH": github["runnerArch"], "RUNNER_NAME": "supplied-runner",
            "GITHUB_WORKSPACE": str(ROOT), "GITHUB_EVENT_PATH": "/synthetic/event.json"}
        policy, _key = I._policy(F.POLICY, F.DONE1)
        if github["runnerOS"] == "Windows":
            self.recipient = E.windows.Recipient(self.native_roots[0], Path("/synthetic/gpg.exe"), "7" * 64,
                self.native_roots[0].identity, policy["recipient"]["fingerprint"], "B" * 40,
                policy["expiresAt"] + 1000, policy["recipient"]["sha256"], "8" * 32)
            self.evidence, self.output = self.native_roots[1:]
        else:
            self.recipient = E.posix.Recipient(Path("/synthetic/crypto"), Path("/synthetic/crypto/gnupg"),
                Path("/synthetic/gpg"), policy["recipient"]["fingerprint"], "B" * 40,
                policy["expiresAt"] + 1000, policy["recipient"]["sha256"], (1, 2))
            self.evidence, self.output = Path("/synthetic/evidence"), Path("/synthetic/output")
        self.primary = {"step": "initial-originals" if kind == "gate" else "canonical-initialization",
            "outcome": "success", "resultSha256": "1" * 64, "handoffSha256": "2" * 64, "inventorySha256": "3" * 64}
        self.copied = {"mapSha256": "4" * 64, "memberCount": 40, "totalBytes": 4000,
            "origins": dict(zip(E.ORIGINS, ("a" * 64, "b" * 64, "c" * 64)))}
        self.authority = {"returnSha256": "5" * 64, "matchSha256": digest(original.record)}
        if hasattr(self, "env_view"):
            self.env_view.environ = self.env
            self.env_view.name = "nt" if github["runnerOS"] == "Windows" else "posix"

    def event_read(self, path, limit):
        self.assertEqual((path, limit), (Path(self.env["GITHUB_EVENT_PATH"]), I.EVENT_LIMIT))
        return self.event_raw

    def guard(self):
        self.guard_calls += 1
        if self.guard_action is not None:
            self.guard_action()

    def read_manifest(self):
        self.read_calls += 1
        if self.read_action is not None:
            return self.read_action()
        return self.manifest_file

    def finish_export(self, manifest):
        self.assertNotIn("artifact", manifest)
        manifest["artifact"] = {"name": "evidence.tar.gz.gpg", "sha256": "f" * 64, "size": 17}
        self.returned, self.manifest_file = manifest, wire(manifest)
        return manifest

    def posix_export(self, evidence, output, recipient, *, manifest, max_bytes, max_members, timeout_seconds):
        self.assertIs(evidence, self.evidence)
        self.assertIs(output, self.output)
        self.assertIs(recipient, self.recipient)
        self.assertEqual((max_bytes, max_members, timeout_seconds), (8000, 80, 30))
        return self.finish_export(manifest)

    def windows_export(self, evidence, output, recipient, factory, *, max_bytes, max_members, timeout_seconds):
        self.assertIs(evidence, self.evidence)
        self.assertIs(output, self.output)
        self.assertIs(recipient, self.recipient)
        self.assertEqual((max_bytes, max_members, timeout_seconds), (8000, 80, 30))
        first, second = factory(), factory()
        self.assertIsNot(first, second)
        self.assertEqual(first, second)
        self.factory_results = [first, second]
        return self.finish_export(first)

    def export(self, **changes):
        arguments = dict(kind=self.kind, selection=self.selection, source_commit=F.H1, source_tree=F.T1,
            original_match=self.original, fresh_match=self.fresh, event_raw=self.event_raw, policy_raw=F.POLICY,
            primary=self.primary, copied=self.copied, authority=self.authority, check=self.guard,
            read_manifest=self.read_manifest, timeout_seconds=30, max_bytes=8000, max_members=80)
        arguments.update(changes)
        return E.export_encrypted(self.evidence, self.output, self.recipient, **arguments)

    def altered_match(self, change):
        value = I.parse(self.original.record, S.LIMIT)
        change(value)
        self.original = type(self.original)(I.encoded(value))
        self.fresh = type(self.original)(self.original.record)
        self.authority["matchSha256"] = digest(self.original.record)

    def refuse(self, pattern=".+", **changes):
        with self.assertRaisesRegex((E.posix.EvidenceError, I.AdmissionError), pattern):
            self.export(**changes)

    def test_worker_six_selections_use_closed_schema_and_actual_backend_shape(self):
        for selection, _profile, _role, system, arch in S.bootstrap.SELECTIONS:
            with self.subTest(selection=selection):
                self.select(selection)
                raw = self.export()
                value = I.parse(raw, E.MANIFEST_LIMIT)
                self.assertEqual((value["schema"], value["scope"], value["kind"], value["selection"]),
                    (4, E.SCOPE, "worker", selection))
                self.assertEqual((value["github"]["job"], value["github"]["runnerOS"], value["github"]["runnerArch"]),
                    ("populate", system, arch))
                self.assertEqual(raw, self.manifest_file)
                self.assertEqual(value["initialRecipient"]["freshReturnSha256"], self.authority["returnSha256"])

    def test_gate_mac_selection_remains_linux_gate_not_a_worker_cast(self):
        self.select("full-macos-arm64", "gate")
        value = I.parse(self.export(), E.MANIFEST_LIMIT)
        self.assertEqual((value["kind"], value["selection"], value["github"]["job"], value["github"]["runnerOS"]),
                         ("gate", "full-macos-arm64", G.JOB, "Linux"))
        self.assertNotIn("profile", value["github"])
        self.windows_exporter.assert_not_called()

    def test_manifest_is_public_only_nonproductive_and_binds_three_origins(self):
        value = I.parse(self.export(), E.MANIFEST_LIMIT)
        self.assertEqual(value["copy"], self.copied)
        self.assertEqual(value["primary"], self.primary)
        self.assertEqual(value["policy"]["origin"], "reviewed-head")
        self.assertEqual(value["policy"]["retentionDays"], 14)
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        for name in ("productiveAuthority", "cacheAuthority", "exportSaveAuthority"):
            self.assertIs(value[name], False)
        for text in ("BEGIN PGP", "/synthetic", "privateKey", "suites", "producerCommand", "liveRecipient"):
            self.assertNotIn(text, self.manifest_file.decode("ascii"))

    def test_exact_backend_encoding_and_one_original_return_encoding(self):
        with patch.object(E, "_canonical", wraps=E._canonical) as encode:
            raw = self.export()
        encode.assert_called_once_with(self.returned)
        self.assertIs(encode.call_args.args[0], self.returned)
        self.assertEqual(raw, wire(self.returned))
        self.assertTrue(raw.endswith(b"}\n"))
        self.assertNotIn(b'": ', raw)
        self.assertEqual(self.read_calls, 1)

    def test_windows_factory_is_fresh_and_does_not_reuse_artifact_mutation(self):
        self.select("desktop-windows-x64")
        self.export()
        self.assertIn("artifact", self.factory_results[0])
        self.assertNotIn("artifact", self.factory_results[1])
        self.posix_exporter.assert_not_called()

    def test_gate_worker_ordinary_and_untyped_match_objects_cannot_be_substituted(self):
        for value in (None, self.original.record, {}, S.OrdinaryMatch(self.original.record),
                      G.GateEligibility(self.original.record)):
            with self.subTest(kind=type(value).__name__):
                self.refuse("MATCH_TYPE", original_match=value)
                self.refuse("MATCH_TYPE", fresh_match=value)
        self.posix_exporter.assert_not_called()

    def test_changed_fresh_record_or_hash_cannot_replace_original_first_use(self):
        value = I.parse(self.fresh.record, S.LIMIT)
        value["firstUseAt"] += 1
        self.refuse("FRESH_MATCH_DIFFERS", fresh_match=S.BootstrapMatch(I.encoded(value)))
        self.refuse("FRESH_MATCH_HASH", authority={**self.authority, "matchSha256": "0" * 64})
        self.posix_exporter.assert_not_called()

    def test_uncanonical_or_mutable_record_bytes_do_not_get_normalized(self):
        for raw in (bytearray(self.original.record), self.original.record + b"\n"):
            altered = S.BootstrapMatch(raw)
            with self.subTest(kind=type(raw).__name__):
                self.refuse(original_match=altered, fresh_match=S.BootstrapMatch(raw),
                    authority={**self.authority, "matchSha256": digest(raw)})
        self.posix_exporter.assert_not_called()

    def test_empty_or_overlimit_match_is_refused_before_guard_or_backend(self):
        for raw in (b"", b"x" * (S.LIMIT + 1)):
            altered = S.BootstrapMatch(raw)
            with self.subTest(size=len(raw)):
                self.refuse("MATCH_TYPE", original_match=altered, fresh_match=altered)
        self.assertEqual(self.guard_calls, 0)
        self.posix_exporter.assert_not_called()

    def test_wrong_scope_schema_or_candidate_policy_origin_refuses(self):
        for change in (lambda v: v.update(scope=S.STAGE2 + "_MATCH_ONLY_NOT_ADMISSION"),
                       lambda v: v.update(schema=True), lambda v: v["policy"].update(origin="main")):
            self.select()
            self.altered_match(change)
            self.refuse()
        self.posix_exporter.assert_not_called()

    def test_gate_selector_type_mismatch_does_not_use_bool_int_equality(self):
        self.select("desktop-linux-x64", "gate")
        self.altered_match(lambda v: v["selector"].update(schema=True))
        self.refuse("GATE_SELECTOR")
        self.posix_exporter.assert_not_called()

    def test_actual_event_and_explicit_source_selection_must_agree(self):
        self.refuse(source_commit=F.H2)
        self.refuse(source_tree=F.T2)
        self.refuse(selection="desktop-macos-arm64")
        self.event_reader.return_value = b"{}"
        self.event_reader.side_effect = None
        self.refuse("EVENT_CHANGED")
        self.posix_exporter.assert_not_called()

    def test_event_reader_equality_subclass_is_not_original_bytes(self):
        class EqualBytes(bytes):
            def __eq__(self, other):
                return True
        self.event_reader.side_effect = None
        self.event_reader.return_value = EqualBytes(b"not the event")
        self.refuse("EVENT_CHANGED")
        self.posix_exporter.assert_not_called()

    def test_wrong_actual_job_workspace_or_token_refuses_before_backend(self):
        for name, value in (("GITHUB_JOB", G.JOB), ("GITHUB_WORKSPACE", "/synthetic/not-source"),
                            (E.acquisition.origin.wire.TOKEN_ENV, "synthetic-not-a-real-token")):
            self.select()
            self.env[name] = value
            with self.subTest(name=name):
                self.refuse()
        self.posix_exporter.assert_not_called()

    def test_primary_requires_exact_successful_predecessor_not_pending_file(self):
        for change in ({"outcome": "failure"}, {"outcome": "NOT_OBSERVED"}, {"step": "recipient"},
                       {"resultSha256": "A" * 64}):
            self.refuse(primary={**self.primary, **change})
        self.posix_exporter.assert_not_called()

    def test_missing_extra_or_duplicate_origin_binding_refuses(self):
        for origins in ({key: value for key, value in self.copied["origins"].items() if key != E.ORIGINS[2]},
                        {**self.copied["origins"], "TERMINAL_TRANSPORT": "d" * 64},
                        dict.fromkeys(E.ORIGINS, "d" * 64)):
            self.refuse(copied={**self.copied, "origins": origins})
        self.posix_exporter.assert_not_called()

    def test_unknown_public_manifest_fields_are_not_caller_extensibility(self):
        for key, value in (("primary", self.primary), ("copied", self.copied), ("authority", self.authority)):
            self.refuse(**{key: {**value, "approved": True}})
        self.posix_exporter.assert_not_called()

    def test_supplied_graphs_refuse_subclasses_floats_cycles_and_container_aliases(self):
        class EqualInt(int):
            def __eq__(self, other):
                return True
        cycle = {}
        cycle["self"] = cycle
        shared = {}
        for malformed in ({"memberCount": EqualInt(40)}, {"totalBytes": 4000.0},
                          {"extra": cycle}, {"extra": [shared, shared]}):
            with self.subTest(fields=tuple(malformed)):
                self.refuse("GRAPH_", copied={**self.copied, **malformed})
        self.assertEqual(self.guard_calls, 0)
        self.posix_exporter.assert_not_called()

    def test_boolean_expanded_or_insufficient_bounds_refuse(self):
        for changes in ({"max_bytes": True}, {"max_bytes": E.posix.MAX_BYTES + 1}, {"max_bytes": 3999},
                        {"max_members": 0}, {"max_members": 39}, {"max_members": E.posix.MAX_MEMBERS + 1},
                        {"timeout_seconds": 241}, {"timeout_seconds": False},
                        {"copied": {**self.copied, "memberCount": True}},
                        {"copied": {**self.copied, "totalBytes": 0}}):
            with self.subTest(changes=tuple(changes)):
                self.refuse(**changes)
        self.posix_exporter.assert_not_called()

    def test_policy_bytes_grant_window_and_public_key_lifetime_refuse(self):
        self.refuse(policy_raw=F.POLICY + b"\n")
        for now in (F.FIRST1 - 1, F.START + 150, F.END):
            self.now = now
            self.refuse()
        self.now = F.DONE1
        self.recipient = dataclasses.replace(self.recipient, expires_at=F.END - 1)
        self.refuse("RECIPIENT_POLICY")
        self.posix_exporter.assert_not_called()

    def test_recipient_dict_wrong_fingerprint_or_key_hash_is_not_live_validation(self):
        original = self.recipient
        for recipient in (dataclasses.asdict(original), SimpleNamespace(**original.__dict__),
                          dataclasses.replace(original, fingerprint="C" * 40),
                          dataclasses.replace(original, key_sha256="0" * 64)):
            self.recipient = recipient
            self.refuse()
        self.posix_exporter.assert_not_called()

    def test_whole_recipient_dictionary_replacement_during_guard_refuses(self):
        def replace():
            object.__setattr__(self.recipient, "__dict__", dict(self.recipient.__dict__))
        self.guard_action = replace
        self.refuse("RECIPIENT_CHANGED")
        self.posix_exporter.assert_not_called()

    def test_whole_match_dictionary_replacement_during_event_read_refuses(self):
        def reader(path, limit):
            object.__setattr__(self.fresh, "__dict__", {"record": self.fresh.record})
            return self.event_read(path, limit)
        self.event_reader.side_effect = reader
        self.refuse("MATCH_CHANGED")
        self.posix_exporter.assert_not_called()

    def test_equal_but_distinct_recipient_path_and_changed_match_scalar_refuse(self):
        def replace_path():
            old = self.recipient.home
            replacement = Path(str(old))
            self.assertIsNot(replacement, old)
            object.__setattr__(self.recipient, "home", replacement)
        self.guard_action = replace_path
        self.refuse("RECIPIENT_CHANGED")
        self.select()
        self.guard_action = lambda: object.__setattr__(self.fresh, "record", self.fresh.record + b"\n")
        self.refuse("MATCH_CHANGED")
        self.posix_exporter.assert_not_called()

    def test_equal_nested_copy_map_replacement_during_guard_refuses(self):
        def replace():
            self.copied["origins"] = dict(self.copied["origins"])
        self.guard_action = replace
        self.refuse("GRAPH_CHANGED")
        self.posix_exporter.assert_not_called()

    def test_windows_requires_live_pinned_inputs_without_posix_fallback(self):
        self.select("desktop-windows-x64")
        self.output = Path("/synthetic/output")
        self.refuse("WINDOWS_PINNED_DIRECTORY")
        self.windows_exporter.assert_not_called()
        self.posix_exporter.assert_not_called()

    def test_windows_borrowed_root_closed_by_guard_is_not_recreated(self):
        self.select("desktop-windows-x64")
        self.guard_action = lambda: setattr(self.output, "_closed", True)
        self.refuse("WINDOWS_DIRECTORY_CHANGED")
        self.windows_exporter.assert_not_called()

    def test_backend_cleanup_failure_never_reads_a_plausible_output_file(self):
        error = E.posix.EvidenceError("SUPPLIED_CLEANUP_FAILURE")
        def failure(*args, **kwargs):
            self.posix_export(*args, **kwargs)
            raise error
        self.posix_exporter.side_effect = failure
        with self.assertRaises(E.posix.EvidenceError) as caught:
            self.export()
        self.assertIs(caught.exception, error)
        self.assertIsNotNone(self.manifest_file)
        self.assertEqual(self.read_calls, 0)

    def test_missing_actual_dict_return_cannot_be_reconstructed_from_files(self):
        def missing(*args, **kwargs):
            self.posix_export(*args, **kwargs)
            return None
        self.posix_exporter.side_effect = missing
        self.refuse("RETURN_FIELDS")
        self.assertEqual(self.read_calls, 0)

    def test_backend_identity_mutation_is_not_the_expected_manifest(self):
        def changed(*args, **kwargs):
            result = self.posix_export(*args, **kwargs)
            result["productiveAuthority"] = True
            self.manifest_file = wire(result)
            return result
        self.posix_exporter.side_effect = changed
        self.refuse("RETURN_IDENTITY")
        self.assertEqual(self.read_calls, 0)

    def test_nonpositive_or_boolean_ciphertext_size_refuses_before_file_read(self):
        for size in (0, True, E.posix.MAX_CIPHERTEXT_BYTES + 1):
            def changed(*args, **kwargs):
                result = self.posix_export(*args, **kwargs)
                result["artifact"]["size"] = size
                return result
            self.posix_exporter.side_effect = changed
            self.refuse("RETURN_ARTIFACT")
        self.assertEqual(self.read_calls, 0)

    def test_returned_graph_is_pinned_before_canonical_encoder_callback(self):
        encode = E._canonical
        def mutate(value):
            raw = encode(value)
            value["source"] = dict(value["source"])
            return raw
        with patch.object(E, "_canonical", side_effect=mutate):
            self.refuse("GRAPH_CHANGED")
        self.assertEqual(self.read_calls, 0)

    def test_returned_graph_rejects_late_scalar_type_equivalence(self):
        encode = E._canonical
        def mutate(value):
            raw = encode(value)
            value["productiveAuthority"] = 0  # Python equality is not exact type identity.
            return raw
        with patch.object(E, "_canonical", side_effect=mutate):
            self.refuse("GRAPH_CHANGED")
        self.assertEqual(self.read_calls, 0)

    def test_returned_graph_is_pinned_before_post_backend_guard(self):
        def mutate():
            if self.returned is not None:
                self.returned["artifact"] = dict(self.returned["artifact"])
        self.guard_action = mutate
        self.refuse("GRAPH_CHANGED")
        self.assertEqual(self.read_calls, 0)

    def test_readback_must_be_exact_bytes_not_equality_or_reencoding(self):
        class EqualBytes(bytes):
            def __eq__(self, other):
                return True
        for changed in (lambda: EqualBytes(self.manifest_file), lambda: self.manifest_file + b"\n",
                        lambda: wire({**self.returned, "artifact": {**self.returned["artifact"], "size": 18}})):
            self.read_action = changed
            self.refuse("MANIFEST_READBACK")

    def test_return_dict_mutation_at_readback_or_late_guard_keeps_failure(self):
        def reader():
            self.returned["copy"]["origins"] = dict(self.returned["copy"]["origins"])
            return self.manifest_file
        self.read_action = reader
        self.refuse("GRAPH_CHANGED")
        self.read_action = None
        self.read_calls = 0
        self.guard_action = lambda: self.returned.update(schema=True) if self.read_calls else None
        self.refuse("GRAPH_CHANGED")

    def test_expiry_exposed_by_last_guard_cannot_return_original_manifest(self):
        final_guards = []
        def expire():
            if self.read_calls:
                final_guards.append(True)
                if len(final_guards) == 2:
                    self.now = F.START + 150
        self.guard_action = expire
        self.refuse("FINAL_WINDOW")
        self.assertEqual(len(final_guards), 2)

    def test_context_change_after_export_is_not_a_new_authority_observation(self):
        def changed():
            if self.returned is not None:
                self.env["GITHUB_RUN_ATTEMPT"] = "2"
        self.guard_action = changed
        self.refuse("CONTEXT_CHANGED")
        self.assertEqual(self.read_calls, 0)

    def test_encoder_reader_and_guard_failures_preserve_the_original_exception(self):
        for which in ("encoder", "reader", "guard"):
            error = RuntimeError("SUPPLIED_" + which.upper() + "_FAILURE")
            def fail():
                raise error
            if which == "encoder":
                with patch.object(E, "_canonical", side_effect=error), self.assertRaises(RuntimeError) as caught:
                    self.export()
            else:
                self.read_action = fail if which == "reader" else None
                self.guard_action = fail if which == "guard" else None
                with self.assertRaises(RuntimeError) as caught:
                    self.export()
            self.assertIs(caught.exception, error)


if __name__ == "__main__":
    unittest.main()
