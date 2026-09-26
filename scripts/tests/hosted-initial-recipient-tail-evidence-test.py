#!/usr/bin/env python3
"""Small tail-adapter DATA controls, authored separately from all old suites.

No B/K capability, native owner, Recipient, validation, file copy, exporter,
HTTP, clock, provider or real hosted identity is created/executed. The few
_current_p0 tests replace the old identity supplier with explicit DATA: they
test this adapter's complete-graph comparison, not that supplier's acceptance.
No previous fixture/test module is imported or previous suite invoked.
"""
from __future__ import annotations

import ctypes  # Complete stdlib loading before the no-native audit boundary.
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("TAIL_DATA_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.dont_write_bytecode = True
sys.addaudithook(offline)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hosted_initial_recipient_tail_evidence as T


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def copy(value):
    return json.loads(wire(value))


def prior(selection="desktop-linux-x64", kind="worker"):
    # Explicitly synthetic labels and counters, never hosted/source evidence.
    source = {"commit": "1" * 40, "tree": "2" * 40}
    _, _role, system, arch = T.S.bootstrap.selection(selection)
    github = {"repository": T.I.REPOSITORY, "event": "workflow_dispatch", "ref": T.S.SOURCE_REF,
        "workflow": T.S.bootstrap.WORKFLOW, "workflowSha": source["commit"],
        "job": T.original.G.JOB if kind == "gate" else T.S.bootstrap.JOB,
        "runId": "9001", "runAttempt": "2", "runnerOS": "Linux" if kind == "gate" else system,
        "runnerArch": "X64" if kind == "gate" else arch, "eventSha256": "e" * 64}
    if kind == "worker":
        github.update(profile=T.S.bootstrap.PROFILE, selection=selection)
    return {"schema": 4, "scope": T.original.SCOPE, "kind": kind, "selection": selection,
        "source": source, "github": github,
        "policy": {"origin": "reviewed-head", "commit": source["commit"], "blob": "3" * 40,
            "path": T.I.POLICY_PATH, "sha256": "4" * 64, "fingerprint": "A" * 40,
            "keySha256": "5" * 64, "expiresAt": 3, "retentionDays": 14},
        "initialRecipient": {"authority": {}, "environment": {}, "originalBase": dict(T.S.BASE),
            "reviewed": dict(source), "firstUseAt": 1, "notBefore": 1, "expiresAt": 2,
            "matchSha256": hashlib.sha256(b"supplied-match-data\n").hexdigest(), "freshReturnSha256": "6" * 64},
        "primary": {"step": "initial-originals" if kind == "gate" else "canonical-initialization",
            "outcome": "success", "resultSha256": "7" * 64, "handoffSha256": "8" * 64, "inventorySha256": "9" * 64},
        "copy": {"mapSha256": "a" * 64, "memberCount": 20, "totalBytes": 200,
            "origins": {name: digit * 64 for name, digit in zip(T.original.ORIGINS, ("b", "c", "d"))}},
        "recipient": {"fingerprint": "A" * 40, "encryptionFingerprint": "B" * 40,
            "keySha256": "5" * 64, "expiresAt": 3},
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED",
        "artifact": {"name": "evidence.tar.gz.gpg", "sha256": "f" * 64, "size": 500}}


def cut(windows=False):
    counts = {**T.FIXED_COUNTS, "P0_EXPORT_DIAGNOSTICS": 4 if windows else 7,
        "NEW_RECIPIENT_VALIDATION": 10 if windows else 11}
    groups = {name: {"memberCount": counts[name], "totalBytes": counts[name] * 2} for name in T.GROUPS}
    return {"mapSha256": "0" * 64, "mapBytes": 100, "memberCount": sum(counts.values()) + 1,
        "totalBytes": sum(row["totalBytes"] for row in groups.values()) + 100, "groups": groups}


def recalculate(value):
    value["memberCount"] = sum(row["memberCount"] for row in value["groups"].values()) + 1
    value["totalBytes"] = sum(row["totalBytes"] for row in value["groups"].values()) + value["mapBytes"]


def predecessors():
    return {name: digit * 64 for name, digit in zip(sorted(T.PREDECESSOR_FIELDS), "01234")}


class TailEvidenceData(unittest.TestCase):
    def setUp(self):
        self.p0, self.cut = prior(), cut()
        for module, name in ((T.posix, "_export_bound_manifest"), (T.windows, "_export"),
                (T.posix, "validate_recipient"), (T.windows, "validate_recipient"),
                (T.I, "read_regular"), (T.time, "time"), (T.original, "_manifest")):
            manager = patch.object(module, name, side_effect=AssertionError("DATA_CONTROL_FORBIDS_EFFECT"))
            manager.start()
            self.addCleanup(manager.stop)

    def reject(self, call):
        with self.assertRaises((T.posix.EvidenceError, ValueError)):
            call()

    def manifest(self, p0=None, copied=None):
        p0 = self.p0 if p0 is None else p0
        copied = self.cut if copied is None else copied
        current = copy({name: value for name, value in p0.items() if name != "artifact"})
        return T._manifest(p0, wire(p0), current, 7001, predecessors(), copied)

    def test_prior_schema4_stays_byte_identical(self):
        raw = wire(self.p0)
        self.assertEqual(T._p0(raw), self.p0)
        self.assertEqual(wire(self.p0), raw)

    def test_prior_refuses_tail_schema_and_noncanonical_bytes(self):
        tail = self.manifest()
        self.reject(lambda: T._p0(wire(tail)))
        self.reject(lambda: T._p0(wire(self.p0) + b"\n"))

    def test_prior_refuses_extra_and_boolean_scalar_fields(self):
        for location, name, replacement in ((self.p0, "schema", True), (self.p0, "productiveAuthority", 0),
                (self.p0["copy"], "memberCount", True), (self.p0["artifact"], "size", True)):
            old = location[name]
            location[name] = replacement
            self.reject(lambda: T._p0(wire(self.p0)))
            location[name] = old
        self.p0["privatePath"] = "/not-a-public-field"
        self.reject(lambda: T._p0(wire(self.p0)))

    def test_prior_cannot_rename_internal_artifact_or_relabel_origins(self):
        self.p0["artifact"]["name"] = T.ARTIFACT_MEMBER
        self.reject(lambda: T._p0(wire(self.p0)))
        self.p0 = prior()
        self.p0["copy"]["origins"]["BEFORE_AUTHORITY"] = self.p0["copy"]["origins"].pop("PRIMARY")
        self.reject(lambda: T._p0(wire(self.p0)))

    def test_both_platform_group_counts_include_map_exactly_once(self):
        for is_windows in (False, True):
            copied = cut(is_windows)
            self.assertIs(T._cut(copied, self.p0, is_windows), copied)
            self.assertEqual(copied["memberCount"], sum(row["memberCount"] for row in copied["groups"].values()) + 1)
            self.assertEqual(copied["totalBytes"], sum(row["totalBytes"] for row in copied["groups"].values()) + copied["mapBytes"])

    def test_each_required_group_is_mandatory_and_no_extra_group(self):
        for name in T.GROUPS:
            copied = cut()
            del copied["groups"][name]
            recalculate(copied)
            self.reject(lambda: T._cut(copied, self.p0, False))
        self.cut["groups"]["TERMINAL_SELF_TAIL"] = {"memberCount": 1, "totalBytes": 1}
        recalculate(self.cut)
        self.reject(lambda: T._cut(self.cut, self.p0, False))

    def test_each_fixed_group_cannot_omit_or_add_original(self):
        for name in T.FIXED_COUNTS:
            for difference in (-1, 1):
                copied = cut()
                copied["groups"][name]["memberCount"] += difference
                recalculate(copied)
                self.reject(lambda: T._cut(copied, self.p0, False))

    def test_before280_never_defaults_to_empty_extension(self):
        self.cut["groups"]["BEFORE_AUTHORITY"] = {"memberCount": 0, "totalBytes": 0}
        recalculate(self.cut)
        self.reject(lambda: T._cut(self.cut, self.p0, False))

    def test_p0_diagnostics_cannot_cross_platform_or_drop_windows_result(self):
        self.reject(lambda: T._cut(cut(True), self.p0, False))
        self.reject(lambda: T._cut(cut(False), self.p0, True))
        copied = cut(True)
        copied["groups"]["P0_EXPORT_DIAGNOSTICS"]["memberCount"] = 3
        recalculate(copied)
        self.reject(lambda: T._cut(copied, self.p0, True))

    def test_validation_requires_actual_summary_as_additional_member(self):
        for windows, count in ((False, 10), (False, 76), (True, 9), (True, 11)):
            copied = cut(windows)
            copied["groups"]["NEW_RECIPIENT_VALIDATION"]["memberCount"] = count
            recalculate(copied)
            self.reject(lambda: T._cut(copied, self.p0, windows))

    def test_posix_validation_full_roster_range_is_closed(self):
        self.cut["groups"]["NEW_RECIPIENT_VALIDATION"]["memberCount"] = 75
        recalculate(self.cut)
        self.assertIs(T._cut(self.cut, self.p0, False), self.cut)

    def test_map_bytes_are_real_external_length_not_self_total(self):
        for name in ("memberCount", "totalBytes"):
            copied = cut()
            copied[name] -= 1 if name == "memberCount" else copied["mapBytes"]
            self.reject(lambda: T._cut(copied, self.p0, False))
        self.cut["mapSha256"] = {"self": "recursive-map-is-not-a-digest"}
        self.reject(lambda: T._cut(self.cut, self.p0, False))

    def test_map_native_two_mib_limit_and_boolean_rejection(self):
        for value in (0, True, T.MAP_LIMIT + 1, "100"):
            copied = cut()
            copied["mapBytes"] = value
            self.reject(lambda: T._cut(copied, self.p0, False))

    def test_plaintext_shared_limit_accepts_equality_rejects_one_byte(self):
        self.p0["copy"]["totalBytes"] = T.posix.MAX_BYTES - self.cut["totalBytes"]
        self.assertIs(T._cut(self.cut, self.p0, False), self.cut)
        self.p0["copy"]["totalBytes"] += 1
        self.reject(lambda: T._cut(self.cut, self.p0, False))

    def test_two_archive_roots_are_charged_not_only_one(self):
        self.p0["copy"]["memberCount"] = T.posix.MAX_MEMBERS - self.cut["memberCount"] - 2
        self.assertIs(T._cut(self.cut, self.p0, False), self.cut)
        self.p0["copy"]["memberCount"] += 1
        self.reject(lambda: T._cut(self.cut, self.p0, False))

    def test_equal_map_hashes_never_remove_duplicate_byte_cost(self):
        self.p0["copy"]["totalBytes"] = T.posix.MAX_BYTES - self.cut["totalBytes"] + 1
        self.cut["mapSha256"] = self.p0["copy"]["mapSha256"]
        self.reject(lambda: T._cut(self.cut, self.p0, False))

    def test_cut_fields_and_types_do_not_accept_private_inventory(self):
        for replacement in (True, "13", -1, 0):
            copied = cut()
            copied["groups"]["RETURNED"]["memberCount"] = replacement
            self.reject(lambda: T._cut(copied, self.p0, False))
        self.cut["groups"]["RETURNED"]["path"] = "/not-a-public-field"
        self.reject(lambda: T._cut(self.cut, self.p0, False))

    def test_safe_manifest_has_exact_closed_top_level_fields(self):
        value = self.manifest()
        self.assertEqual(set(value), {"schema", "scope", "kind", "selection", "source", "github", "policy",
            "recipient", "p0", "predecessors", "cut", "transport", "finalPrivateOriginals", "testAcceptance",
            "productiveAuthority", "cacheAuthority", "exportSaveAuthority", "budgetAcceptance"})
        self.assertEqual(value["scope"], T.SCOPE)
        self.assertNotIn("artifact", value)  # Only the actual unchanged exporter injects it.
        self.assertLessEqual(len(wire(value)), T.MANIFEST_LIMIT)

    def test_safe_manifest_binds_original_p0_without_editing_it(self):
        raw = wire(self.p0)
        value = self.manifest()
        self.assertEqual(value["p0"], {"manifestSha256": hashlib.sha256(raw).hexdigest(),
            "artifact": self.p0["artifact"], "privateMemberCount": 20, "privateTotalBytes": 200})
        self.assertIsNot(value["p0"]["artifact"], self.p0["artifact"])
        self.assertEqual(wire(self.p0), raw)

    def test_literal_alias_contract_never_relabels_backend_originals(self):
        self.assertEqual(T.CARRIER_MEMBERS, ("evidence.tar.gz.gpg", "manifest.json",
            "custody-tail.tar.gz.gpg", "custody-tail-manifest.json"))
        self.assertEqual(self.manifest()["transport"], {"artifactMember": "custody-tail.tar.gz.gpg",
            "manifestMember": "custody-tail-manifest.json", "backendArtifact": "evidence.tar.gz.gpg",
            "backendManifest": "manifest.json"})

    def test_terminal_self_tail_is_not_promoted_or_recursively_included(self):
        value = self.manifest()
        self.assertEqual(value["finalPrivateOriginals"], {"disposition": "NOT_DELIVERED",
            "coverage": "EXCLUDED_FROM_K_AND_R", "requiredEvidence": "NOT_USED_AS_QUALIFICATION_ORIGINALS"})
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        for name in ("productiveAuthority", "cacheAuthority", "exportSaveAuthority"):
            self.assertIs(value[name], False)

    def test_service_id_and_run_id_preserve_distinct_exact_types(self):
        value = self.manifest()
        self.assertIs(type(value["github"]["jobId"]), int)
        self.assertIs(type(value["github"]["runId"]), str)
        self.assertIs(type(value["github"]["runAttempt"]), str)
        current = copy({name: value for name, value in self.p0.items() if name != "artifact"})
        for job_id in (True, "7001", 0, 10 ** 20):
            self.reject(lambda: T._manifest(self.p0, wire(self.p0), current, job_id, predecessors(), self.cut))

    def test_gate_role_is_actual_linux_not_selected_future_worker(self):
        value = self.manifest(prior("desktop-windows-x64", "gate"))
        self.assertEqual(value["github"]["role"], "linux-x64")
        self.assertEqual(value["github"]["job"], T.original.G.JOB)
        worker = self.manifest(prior("desktop-windows-x64"), cut(True))
        self.assertEqual(worker["github"]["role"], "windows-x64")

    def test_each_predecessor_digest_is_required_without_extra_fields(self):
        for name in T.PREDECESSOR_FIELDS:
            value = predecessors()
            del value[name]
            self.reject(lambda: T._predecessors(value))
        value = predecessors()
        value["sourcePath"] = "/not-a-public-field"
        self.reject(lambda: T._predecessors(value))

    def test_retention14_is_not_observed_provider_expiry(self):
        self.assertEqual(self.manifest()["policy"]["retentionDays"], 14)
        self.p0["policy"]["retentionDays"] = 15
        self.reject(lambda: self.manifest())

    def test_all_four_files_including_both_manifests_share_carrier_cap(self):
        first, second = b"a", b"b"
        artifact = {"name": T.posix.ARTIFACT, "sha256": "a" * 64,
            "size": T.posix.MAX_CIPHERTEXT_BYTES - self.p0["artifact"]["size"] - 2}
        T._carrier_limit(first, self.p0, second, artifact)
        artifact["size"] += 1
        self.reject(lambda: T._carrier_limit(first, self.p0, second, artifact))

    def test_each_manifest_has_individual64k_limit_before_carrier_sum(self):
        artifact = {"name": T.posix.ARTIFACT, "sha256": "a" * 64, "size": 1}
        for first, second in ((b"a" * (T.MANIFEST_LIMIT + 1), b"b"), (b"a", b"b" * (T.MANIFEST_LIMIT + 1))):
            self.reject(lambda: T._carrier_limit(first, self.p0, second, artifact))

    def test_complete_current_p0_graph_must_match_not_only_selected_fields(self):
        current = copy({name: value for name, value in self.p0.items() if name != "artifact"})
        with patch.object(T.original, "_manifest", return_value=current):
            self.assertIs(T._current_p0(self.p0, b"supplied-match-data\n", b"event", b"policy", None, False), current)
            current["github"]["eventSha256"] = "1" * 64
            self.reject(lambda: T._current_p0(self.p0, b"supplied-match-data\n", b"event", b"policy", None, False))

    def test_current_p0_match_hash_not_just_equal_supplied_matches(self):
        current = copy({name: value for name, value in self.p0.items() if name != "artifact"})
        with patch.object(T.original, "_manifest", return_value=current) as supplier:
            self.reject(lambda: T._current_p0(self.p0, b"different-supplied-match\n", b"event", b"policy", None, False))
            supplier.assert_not_called()

    def test_returned_safe_graphs_do_not_alias_cut_or_predecessor_inputs(self):
        original_cut = wire(self.cut)
        value = self.manifest()
        self.assertIsNot(value["cut"]["groups"], self.cut["groups"])
        value["cut"]["groups"]["BEFORE_AUTHORITY"]["totalBytes"] += 1
        self.assertEqual(wire(self.cut), original_cut)


if __name__ == "__main__":
    unittest.main(verbosity=2)
