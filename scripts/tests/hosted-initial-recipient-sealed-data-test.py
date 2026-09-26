#!/usr/bin/env python3
"""Tiny historical seal DATA controls; authored, not runtime/custody evidence.

No old suite/fixture, file tree, producer, owner, host or sampled clock is used.
The ten historical inputs below are independently constructed minimal grammar,
not authenticated Step evidence or a policy/key/recipient. No live return is
registered. Source/model review and separate authorization precede execution.
"""
from __future__ import annotations

import _strptime  # Finish standard date-parser imports before the no-IO guard.
import base64
from contextlib import ExitStack
import copy
import ctypes  # Standard-library initialization only, before the native guard.
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PURE = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or PURE and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("SEALED_DATA_SIDE_EFFECT_FORBIDDEN")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("sealed_data_source_under_review",
    ROOT / "scripts/run-hosted-initial-recipient-custody.py")
D = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = D
_spec.loader.exec_module(D)
NS = 1_000_000_000
PENDING = {"writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED",
    "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
    "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def close(scope="INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1"):
    return {"schema": 1, "scope": scope, "resources": [
        {"ordinal": 0, "label": "directory", "closeAttempted": True, "closed": True}],
        "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}


def data(kind="gate", role="linux-x64", *, early=False):
    """Only dictionaries/bytes: no Packets, Rig, source fixture or filesystem."""
    source, session = {"commit": "1" * 40, "tree": "2" * 40}, str(ROOT / "SUPPLIED-NOT-AN-EXISTING-SESSION")
    clock = {"role": role, "domain": D.O.clocks.DOMAINS[role], "ticksPerSecond": NS}
    # Handwritten arithmetic, not a call to the production schedule builder.
    work = (1130 if kind == "gate" else 1240) * NS
    frame = {"schema": 1, "scope": D.WINDOW_SCOPE, "clock": clock, "originalBootDigest": "7" * 64,
        "kind": kind, "originalJobBasisNs": 950 * NS, "jobEndNs": (1310 if kind == "gate" else 2150) * NS,
        "startNs": 1000 * NS, "workEndNs": work, "nativeFinalEndNs": work + 45 * NS,
        "readEndNs": work + 75 * NS, "sealEndNs": work + 105 * NS,
        "uploadEndNs": work + 165 * NS, "afterEndNs": work + 180 * NS}
    primary = {"step": "initial-originals" if kind == "gate" else "canonical-initialization", "outcome": "success",
        **{name: sha(name.encode("ascii")) for name in ("resultSha256", "handoffSha256", "inventorySha256")}}
    files = {name: wire({"scope": "SUPPLIED_HISTORICAL_DATA_NOT_ORIGINAL", "name": name})
        for name in D._CRYPTO_INPUT_LIMITS}
    files["fresh-match.json"] = files["original-match.json"]
    pins = {name: [17, format(index + 1, "032x") if role == "windows-x64" else index + 1]
        for index, name in enumerate(D._CRYPTO_DIRECTORIES)}
    observed = {"scope": "SUPPLIED_NOT_A_HOST"}
    context = {"schema": 1, "scope": D._CRYPTO_CONTEXT_SCOPE, "kind": kind, "root": str(ROOT),
        "session": session, "job": "4" * 32, "observed": observed, "window": frame, "primary": primary,
        "authority": {"returnSha256": sha(files["authority-return.json"]),
            "matchSha256": sha(files["original-match.json"]), "copySha256": sha(files["authority-map.json"])},
        "filesSha256": {name: sha(raw) for name, raw in files.items()},
        "directories": {**pins, "export-output": pins["export-output"] if role == "windows-x64" else None},
        "inheritedContext": {}, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    copied = {"mapSha256": sha(b"SUPPLIED-FROZEN-MAP"), "memberCount": 3, "totalBytes": 9,
        "origins": {name: sha(name.encode("ascii")) for name in D.ORIGINS}}
    manifest = {"schema": 4, "scope": D.E.SCOPE, "kind": kind, "selection": "desktop-" + role,
        "source": source, "github": {"runId": "7001", "runAttempt": 1, "job": "SUPPLIED-" + kind},
        "policy": {"origin": "reviewed-head", "sha256": sha(files["candidate-policy.json"]), "retentionDays": 14},
        "initialRecipient": {"matchSha256": sha(files["original-match.json"]),
            "freshReturnSha256": sha(files["authority-return.json"])}, "primary": primary, "copy": copied,
        "recipient": {"fingerprint": "A" * 40, "encryptionFingerprint": "B" * 40,
            "keySha256": sha(files["recipient-public.asc"]), "expiresAt": 1_800_000_000},
        **{name: PENDING[name] for name in ("testAcceptance", "productiveAuthority", "cacheAuthority",
            "exportSaveAuthority", "budgetAcceptance")},
        "artifact": {"name": "evidence.tar.gz.gpg", "size": 3, "sha256": sha(b"XYZ")}}
    context_raw, manifest_raw = wire(context), wire(manifest)
    phases = {name: sha(("SUPPLIED-PHASE-" + name).encode("ascii")) for name in D.native.PHASE_FILES}
    parent = {**close("INITIAL_CUSTODY_CRYPTO_PARENT_KNOWN_CLOSE_V1"), "contextSha256": sha(context_raw),
        "childSha256": sha(b"SUPPLIED-CHILD"), "authorityCopyCloseSha256": sha(b"SUPPLIED-COPY-CLOSE"),
        "phaseSha256": phases, "closedNs": work + 40 * NS}
    carrier = {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_CLOSED_RETURN_V1",
        **{name: manifest[name] for name in ("kind", "selection", "source", "github", "policy", "primary", "recipient")},
        "authority": manifest["initialRecipient"],
        "window": {**{name: frame[name] for name in frame if name not in ("schema", "scope", "kind")},
            "lastNs": work + 41 * NS, "lastLocal": 100.0},
        "copy": {**copied, "path": session + "/SUPPLIED-COPY", "directoryIdentity": pins["copied-evidence"],
            "sourceMetadataSha256": {name: sha((name + "-METADATA").encode("ascii")) for name in D.ORIGINS},
            "destinationMetadataSha256": sha(b"SUPPLIED-DESTINATION-METADATA")},
        "exporter": {"manifestBase64": base64.b64encode(manifest_raw).decode("ascii"),
            "manifestBytes": len(manifest_raw), "manifestSha256": sha(manifest_raw),
            "childSha256": parent["childSha256"], "ackSha256": phases["stdout.log"],
            "phaseSha256": phases, "nativeResources": parent["resources"]}, "parentClose": parent, **PENDING}
    carrier_raw = wire(carrier)
    step = {"schema": 1, "scope": D._EXPORT_STEP_SCOPE, "kind": kind, "step": "initial-custody-export",
        "primary": primary, "originalServiceJob": [9001, "2026-09-26T00:00:00Z", "SUPPLIED-NOT-A-RUNNER", 9002],
        "directory": session, "directoryIdentity": pins["returned"],
        "cryptoCarrier": {"sha256": sha(carrier_raw), "bytes": len(carrier_raw),
            "exporterReturnSha256": sha(manifest_raw), "metadataClose": close()}, "originalWindow": frame,
        "originalContextSha256": sha(context_raw), "observed": observed,
        "lowerNs": work + 42 * NS, "lowerLocal": 101.0,
        "sample": "AFTER_CRYPTO_CARRIER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN", **PENDING}
    raws = {"step": wire(step), "carrier": carrier_raw, "context": context_raw, "manifest": manifest_raw,
        **{name: files[leaf] for name, leaf in (("original-match", "original-match.json"),
            ("fresh-match", "fresh-match.json"), ("event", "event.json"), ("policy", "candidate-policy.json"),
            ("public", "recipient-public.asc"))}}
    originals = {name: sha(("SUPPLIED-ORIGINAL-" + name).encode("ascii")) for name in D.N.ORIGINAL_KEYS}
    originals.update(event=sha(raws["event"]), match=sha(raws["original-match"]), candidate_policy_raw=sha(raws["policy"]))
    read = frame["readEndNs"]
    binding = {name: sha(name.encode("ascii")) for name in
        ("contextSha256", "sourceBeforeSha256", "sourceAfterSha256", "querySessionSha256", "childSha256")}
    binding.update(expectedMatchSha256=originals["match"], freshMatchSha256=originals["match"],
        originalsSha256=originals, phaseSha256=phases, ackSha256=phases["stdout.log"], invocation="9" * 32,
        startedNs=read - 14 * NS, acquiredNs=read - 13 * NS, checkedNs=read - 12 * NS,
        closedNs=read - 11 * NS, workEndNs=read, finalEndNs=read)
    collected = {"schema": 1, "scope": D._COLLECT_SCOPE, "kind": kind, "edge": "POST_EXPORT",
        "predecessor": {"step": "initial-custody-export", "outcome": "success", "stepSha256": sha(raws["step"]),
            "cryptoCarrierSha256": sha(carrier_raw), "exporterReturnSha256": sha(manifest_raw)},
        "primary": primary, "originalWindow": frame, "lastNs": read - 10 * NS, "lastLocal": 102.0,
        "authority": copy.deepcopy(binding), "parentClose": close("INITIAL_POST_EXPORT_AUTHORITY_PARENT_KNOWN_CLOSE_V1"),
        **PENDING}
    raws["collect"] = wire(collected)
    first = read + (-5 if early else 5) * NS
    end = min(first + 30 * NS, frame["sealEndNs"])
    binding.update(startedNs=first + NS, acquiredNs=first + 2 * NS, checkedNs=first + 3 * NS,
        closedNs=first + 5 * NS, workEndNs=end, finalEndNs=end)
    authority = {"schema": 1, "scope": "INITIAL_SEAL_AUTHORITY_CLOSED_RETURN_V1", "edge": "SEAL", "authority": binding,
        "parentClose": close("INITIAL_SEAL_AUTHORITY_PARENT_KNOWN_CLOSE_V1"),
        "preCloseNs": first + 4 * NS, "closedNs": first + 5 * NS,
        "testAcceptance": "NOT_PERFORMED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    seal = {"schema": 1, "scope": D._TAIL_SEAL_SCOPE, "kind": kind, "edge": "SEAL",
        "predecessor": {"step": "initial-custody", "outcome": "success", "collectSha256": sha(raws["collect"]),
            "cryptoStepSha256": sha(raws["step"]), "cryptoCarrierSha256": sha(carrier_raw),
            "exporterReturnSha256": sha(manifest_raw)}, "primary": primary,
        **{name: manifest[name] for name in ("source", "github", "policy")}, "originalWindow": frame,
        "firstNs": first, "hardEndNs": end, "lastNs": first + 6 * NS, "lastLocal": 103.0,
        "manifestSha256": sha(manifest_raw), "output": {
            "scope": "THIS_SEAL_FILE_OBSERVATION_NOT_HISTORICAL_POSIX_OUTPUT_PIN", "directoryIdentity": pins["export-output"],
            "fileMetadataSha256": sha(b"SUPPLIED-SEAL-OBSERVATION-NOT-A-FILE"), "artifact": manifest["artifact"]},
        "authority": authority, "inputMetadataClose": close(), "decryption": "NOT_PERFORMED", "upload": "NOT_PERFORMED",
        **PENDING}
    return raws, seal


class HistoricalSealDataControls(unittest.TestCase):
    def decode(self, raws, seal, *, outcome="success", expected=None, raw=None):
        global PURE
        raw = wire(seal) if raw is None else raw
        checksum = sha(raw) if expected is None else expected
        PURE = True
        try:
            return D._historical_seal_record(raw, raws, outcome=outcome, expected_sha256=checksum)
        finally:
            PURE = False

    def reject(self, change, pattern="HISTORICAL_SEAL", *, kind="gate", role="linux-x64", early=False):
        raws, seal = data(kind, role, early=early)
        change(seal)
        # Every semantic negative is independently rehashed after mutation.
        with self.assertRaisesRegex(ValueError, pattern):
            self.decode(raws, seal)

    def test_gate_worker_linux_windows_and_both_original_caps(self):
        for kind in ("gate", "worker"):
            for role in ("linux-x64", "windows-x64"):
                for early in (False, True):
                    with self.subTest(kind=kind, role=role, early=early):
                        raws, seal = data(kind, role, early=early)
                        result = self.decode(raws, seal)
                        self.assertEqual(wire(result), wire(seal))
                        self.assertEqual(set(raws), set(D._TAIL_LIMITS))
                        self.assertEqual(result["hardEndNs"], min(seal["firstNs"] + 30 * NS,
                            seal["originalWindow"]["sealEndNs"]))

    def test_supplied_success_and_exact_hash_are_required_not_authenticated(self):
        raws, seal = data()
        for outcome in (None, True, "failure", "cancelled", "skipped", "Success"):
            with self.subTest(outcome=outcome), self.assertRaisesRegex(ValueError, "HISTORICAL_SEAL_SUPPLIED_STEP"):
                self.decode(raws, seal, outcome=outcome)
        for expected in ("0" * 64, "A" * 64, "0" * 63, None):
            with self.subTest(hash_shape=type(expected).__name__), self.assertRaises(ValueError):
                D._historical_seal_record(wire(seal), raws, outcome="success", expected_sha256=expected)

    def test_exact_seal_fields_types_canonical_encoding_and_size(self):
        for change in (lambda v: v.update(extra=True), lambda v: v.pop("output"), lambda v: v.update(schema=True),
                lambda v: v.update(scope="OTHER"), lambda v: v.update(kind="worker"), lambda v: v.update(edge="UPLOAD"),
                lambda v: v.update(firstNs=True), lambda v: v.update(hardEndNs=1.0), lambda v: v.update(lastNs=-1)):
            with self.subTest(change=change.__code__.co_firstlineno):
                self.reject(change, "HISTORICAL_SEAL|BOOTSTRAP_ORIGIN_INTEGER")
        raws, seal = data()
        for raw in (wire(seal).rstrip(), b" " + wire(seal), b"{}\n", b"x" * (D.native.LIMIT + 1)):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                self.decode(raws, seal, raw=raw)
        with self.assertRaises(ValueError):
            D._historical_seal_record(bytearray(wire(seal)), raws, outcome="success", expected_sha256=sha(wire(seal)))

    def test_ten_input_roster_bytes_hashes_and_history_remain_binding(self):
        raws, seal = data()
        variants = ({name: raw for name, raw in raws.items() if name != "collect"}, {**raws, "extra": b"{}\n"},
            {**raws, "collect": b""}, {**raws, "event": bytearray(raws["event"])},
            {**raws, "event": wire({"scope": "DIFFERENT_PRIOR_EVENT"})},
            {**raws, "collect": b"x" * (D._TAIL_LIMITS["collect"] + 1)})
        for index, variant in enumerate(variants):
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "TAIL_INPUT|COLLECT_ORIGINAL_INPUT_HASH"):
                self.decode(variant, seal)

    def test_rehashed_predecessor_primary_source_job_policy_and_manifest_swaps(self):
        for change in (lambda v: v["predecessor"].update(collectSha256="0" * 64),
                lambda v: v["primary"].update(resultSha256="0" * 64), lambda v: v["source"].update(tree="3" * 40),
                lambda v: v["github"].update(runId="7002"), lambda v: v["policy"].update(origin="trusted-main"),
                lambda v: v.update(manifestSha256="0" * 64), lambda v: v["originalWindow"].update(jobEndNs=1)):
            with self.subTest(change=change.__code__.co_firstlineno):
                self.reject(change, "HISTORICAL_SEAL_BINDINGS")

    def test_canonical_embedded_binding_refuses_boolean_integer_alias(self):
        self.reject(lambda v: v["github"].update(runAttempt=True), "HISTORICAL_SEAL_BINDINGS")
        self.reject(lambda v: v["output"]["artifact"].update(size=3.0), "HISTORICAL_SEAL_ARTIFACT")

    def test_internally_consistent_rehashed_authority_match_event_policy_swaps(self):
        def substitute_match(value):
            binding = value["authority"]["authority"]
            binding.update(expectedMatchSha256="0" * 64, freshMatchSha256="0" * 64)
            binding["originalsSha256"]["match"] = "0" * 64
        self.reject(substitute_match, "HISTORICAL_SEAL_AUTHORITY_INPUTS")
        for name in ("event", "candidate_policy_raw"):
            with self.subTest(name=name):
                self.reject(lambda v: v["authority"]["authority"]["originalsSha256"].update({name: "0" * 64}),
                    "HISTORICAL_SEAL_AUTHORITY_INPUTS")

    def test_collect_cannot_follow_seal_first_even_with_rehashed_predecessor(self):
        raws, seal = data(early=True)
        collected = json.loads(raws["collect"])
        collected["lastNs"] = seal["firstNs"] + 1
        raws["collect"] = wire(collected)
        seal["predecessor"]["collectSha256"] = sha(raws["collect"])
        with self.assertRaisesRegex(ValueError, "HISTORICAL_SEAL_CHRONOLOGY"):
            self.decode(raws, seal)
        collected["lastNs"] = seal["firstNs"]
        raws["collect"] = wire(collected)
        seal["predecessor"]["collectSha256"] = sha(raws["collect"])
        self.assertEqual(self.decode(raws, seal)["firstNs"], collected["lastNs"])

    def test_exact_end_and_original_cap_cannot_be_widened(self):
        def wider(value):
            value["hardEndNs"] += 1
            value["authority"]["authority"].update(workEndNs=value["hardEndNs"], finalEndNs=value["hardEndNs"])
        for early in (False, True):
            with self.subTest(early=early):
                self.reject(wider, "TAIL_AUTHORITY_RECORD_TIME", early=early)
        self.reject(lambda v: v.update(lastNs=v["hardEndNs"]), "HISTORICAL_SEAL_CHRONOLOGY")
        self.reject(lambda v: v["authority"]["authority"].update(workEndNs=v["hardEndNs"] - 1),
            "TAIL_AUTHORITY_RECORD_TIME")
        self.reject(lambda v: v["authority"]["authority"].update(finalEndNs=v["hardEndNs"] + 1),
            "TAIL_AUTHORITY_RECORD_TIME")

    def test_ordered_authority_closes_and_historical_local_floor(self):
        self.reject(lambda v: v.update(lastNs=v["authority"]["closedNs"] - 1), "HISTORICAL_SEAL_CHRONOLOGY")
        self.reject(lambda v: v.update(lastLocal=101.0), "HISTORICAL_SEAL_CHRONOLOGY")
        self.reject(lambda v: v["authority"].update(preCloseNs=v["authority"]["closedNs"] + 1),
            "TAIL_AUTHORITY_RECORD_TIME")
        self.reject(lambda v: v["authority"]["authority"].update(closedNs=v["authority"]["closedNs"] + 1),
            "TAIL_AUTHORITY_RECORD_TIME")
        self.reject(lambda v: v["authority"]["authority"].update(closedNs=float(v["authority"]["closedNs"])),
            "BOOTSTRAP_ORIGIN_INTEGER")
        self.reject(lambda v: v["authority"]["authority"].update(closedNs=True), "TAIL_AUTHORITY_RECORD_TIME")

    def test_pending_self_flags_and_no_acceptance_cannot_be_promoted(self):
        for name in (*PENDING, "decryption", "upload"):
            with self.subTest(name=name):
                self.reject(lambda v: v.update({name: True if PENDING.get(name) is False else "ACCEPTED"}),
                    "COLLECT_PENDING_FLAGS|HISTORICAL_SEAL_NOT_ACCEPTANCE")

    def test_input_metadata_and_authority_closes_remain_only_historical_data(self):
        for change in (lambda v: v["inputMetadataClose"].update(extra=True),
                lambda v: v["inputMetadataClose"].update(retirement="UNKNOWN"),
                lambda v: v["inputMetadataClose"]["resources"][0].update(closeAttempted=False),
                lambda v: v["inputMetadataClose"]["resources"][0].update(closed=False),
                lambda v: v["inputMetadataClose"]["resources"][0].update(ordinal=True),
                lambda v: v["authority"]["parentClose"]["resources"][0].update(closed=False)):
            with self.subTest(change=change.__code__.co_firstlineno):
                self.reject(change, "COLLECT_FILE_CLOSE|COLLECT_CLOSE_ROW")

    def test_output_scope_artifact_and_windows_original_pin_cannot_change(self):
        self.reject(lambda v: v["output"].update(scope="ORIGINAL_POSIX_CRYPTO_PIN"), "HISTORICAL_SEAL_OUTPUT_SCOPE")
        self.reject(lambda v: v["output"].update(extra=True), "HISTORICAL_SEAL_OUTPUT_FIELDS")
        self.reject(lambda v: v["output"].update(directoryIdentity=[True, 1]), "DIRECTORY_IDENTITY")
        self.reject(lambda v: v["output"].update(fileMetadataSha256="not-a-digest"), "DIGEST")
        self.reject(lambda v: v["output"]["artifact"].update(sha256="0" * 64), "HISTORICAL_SEAL_ARTIFACT")
        self.reject(lambda v: v["output"].update(directoryIdentity=[17, "f" * 32]),
            "HISTORICAL_SEAL_WINDOWS_OUTPUT_PIN", role="windows-x64")

    def test_posix_seal_pin_and_file_metadata_are_not_current_file_proof(self):
        raws, seal = data()
        self.assertIsNone(json.loads(raws["context"])["directories"]["export-output"])
        seal["output"].update(directoryIdentity=[18, 77], fileMetadataSha256=sha(b"DIFFERENT-DECLARED-METADATA"))
        result = self.decode(raws, seal)
        self.assertEqual(result["output"], seal["output"])
        self.assertEqual(result["upload"], "NOT_PERFORMED")
        self.assertIs(result["productiveAuthority"], False)

    def test_decoder_mints_no_live_returns_clocks_attempts_or_outputs(self):
        raws, seal = data()
        registry_names = ("_WINDOWS", "_PRIMARY_ATTEMPTS", "_PRIMARY_OWNERS", "_PRIMARY_RETURNS", "_PRELIMINARIES",
            "_CUSTODY_OWNERS", "_CUSTODY_CHILD_CLOCKS", "_AUTHORITY_RETURNS", "_AUTHORITY_ATTEMPTS", "_CRYPTO_ATTEMPTS",
            "_CRYPTO_RETURNS", "_CRYPTO_NATIVE_RETURNS", "_CRYPTO_READ_FENCES", "_CRYPTO_CARRIERS", "_COLLECT_ATTEMPTS",
            "_EXPORT_STEPS", "_COLLECT_INPUTS", "_COLLECT_CLOCKS", "_COLLECT_AUTHORITY_RETURNS", "_COLLECT_RETURNS",
            "_COLLECT_OUTPUTS", "_TAIL_ATTEMPTS", "_TAIL_INPUTS", "_TAIL_CLOCKS", "_TAIL_AUTHORITIES", "_TAIL_SEALS", "_TAIL_OUTPUTS")
        originals = {name: getattr(D, name) for name in registry_names}
        self.assertTrue(all(value == {} for value in originals.values()))
        failure = AssertionError("SEALED_DATA_LIVE_BOUNDARY_FORBIDDEN")
        with ExitStack() as stack:
            for module, names in ((D, ("Window", "_TailInput", "_TailClock", "_PrimaryOwner", "_checked_tail_input",
                    "_tail_host", "_tail_actual", "_tail_ciphertext", "_tail_pre_metadata")),
                    (D.native, ("Owner",)), (D.O.clocks, ("observe", "checked_now", "local_deadline")),
                    (D.O.wire, ("raw_now",))):
                for name in names:
                    stack.enter_context(patch.object(module, name, side_effect=failure))
            result = self.decode(raws, seal)
        self.assertEqual(wire(result), wire(seal))
        for name, original in originals.items():
            self.assertIs(getattr(D, name), original)
            self.assertEqual(original, {})
        self.assertEqual(D._PRIMARY_QUARANTINE, [])
        self.assertEqual(D.native.QUARANTINE, [])
        self.assertEqual(D.C.QUARANTINE, [])
        self.assertEqual(D.Q.QUARANTINE, [])


if __name__ == "__main__":
    unittest.main()
