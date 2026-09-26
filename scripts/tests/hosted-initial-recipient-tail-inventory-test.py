#!/usr/bin/env python3
"""New existing-authority DATA roster controls, authored but not executed.

Small in-memory query grammar only: no old test/fixture import, disk tree,
hosted environment, clock, actual owner, original stream or native acceptance.
The synthetic phase/owner bodies are deliberately NOT qualification evidence.
"""
from __future__ import annotations

import _strptime
import base64
from contextlib import ExitStack
import copy
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("TAIL_INVENTORY_DATA_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("tail_inventory_source_under_review",
    ROOT / "scripts/run-hosted-initial-recipient-custody.py")
K = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = K
SPEC.loader.exec_module(K)
NS = 1_000_000_000
PENDING = {"writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED",
    "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
    "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def decoded(raw):
    return json.loads(raw)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inert(name):
    return encoded({"model": "INERT_NOT_AN_ORIGINAL_OR_NATIVE_RETURN", "name": name})


def closed(scope="INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1"):
    return {"schema": 1, "scope": scope, "resources": [
        {"ordinal": 0, "label": "directory", "closeAttempted": True, "closed": True}],
        "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}


def guarded(function, *args, **kwargs):
    global GUARDED
    previous, GUARDED = GUARDED, True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = previous


class Grammar:
    """New query/index grammar, with tiny inert prior bytes, never live objects."""

    def __init__(self, kind="gate", role="linux-x64"):
        self.kind, self.role = kind, role
        self.source = {"commit": "c" * 40, "tree": "d" * 40}
        self.clock = {"role": role, "domain": K.O.clocks.DOMAINS[role], "ticksPerSecond": NS}
        self.session = str(ROOT.parent / "NO-DIRECTORY-CREATED-K-GRAMMAR" / "returned")
        self.work = (280 if kind == "gate" else 360) * NS
        self.frame = {"schema": 1, "scope": K.WINDOW_SCOPE, "kind": kind, "clock": self.clock,
            "originalBootDigest": "8" * 64, "originalJobBasisNs": 100 * NS,
            "jobEndNs": (460 if kind == "gate" else 1300) * NS, "startNs": 120 * NS,
            **{name: self.work + delta * NS for name, delta in (("workEndNs", 0), ("nativeFinalEndNs", 45),
                ("readEndNs", 75), ("sealEndNs", 105), ("uploadEndNs", 165), ("afterEndNs", 180))}}
        self.observed = {"kind": kind, "role": role, "source": self.source, "firstUseAt": 1_700_000_000,
            "model": "NOT_ACTUAL_HOST_CONTEXT"}
        primary = {"step": "initial-originals" if kind == "gate" else "canonical-initialization", "outcome": "success",
            **{name: sha(inert(name)) for name in ("resultSha256", "handoffSha256", "inventorySha256")}}
        crypto_inputs = {name: inert(name) for name in K._CRYPTO_INPUT_LIMITS}
        crypto_inputs["fresh-match.json"] = crypto_inputs["original-match.json"]
        pins = {name: self.pin(10 + n) for n, name in enumerate(K._CRYPTO_DIRECTORIES)}
        self.crypto = {"schema": 1, "scope": K._CRYPTO_CONTEXT_SCOPE, "kind": kind, "root": str(ROOT),
            "session": self.session, "job": "a" * 32, "observed": self.observed, "window": self.frame,
            "primary": primary, "authority": {"returnSha256": sha(crypto_inputs["authority-return.json"]),
                "matchSha256": sha(crypto_inputs["original-match.json"]), "copySha256": sha(crypto_inputs["authority-map.json"])},
            "filesSha256": {name: sha(raw) for name, raw in crypto_inputs.items()},
            "directories": {**pins, "export-output": pins["export-output"] if role == "windows-x64" else None},
            "inheritedContext": {}, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        copied = {"mapSha256": sha(inert("p0-map")), "memberCount": 4, "totalBytes": 17,
            "origins": {name: sha(inert(name)) for name in K.ORIGINS}}
        manifest = {"schema": 4, "scope": K.E.SCOPE, "kind": kind, "selection": "MODEL-" + role,
            "source": self.source, "github": {"runId": "17", "runAttempt": "1", "job": "MODEL-" + kind},
            "policy": {"sha256": sha(crypto_inputs["candidate-policy.json"]), "origin": "reviewed-head", "retentionDays": 14},
            "initialRecipient": {"matchSha256": sha(crypto_inputs["original-match.json"]),
                "freshReturnSha256": sha(crypto_inputs["authority-return.json"])},
            "primary": primary, "copy": copied, "recipient": {"fingerprint": "E" * 40,
                "encryptionFingerprint": "F" * 40, "keySha256": sha(crypto_inputs["recipient-public.asc"]), "expiresAt": 1_900_000_000},
            **{name: PENDING[name] for name in ("testAcceptance", "productiveAuthority", "cacheAuthority", "exportSaveAuthority", "budgetAcceptance")},
            "artifact": {"name": "evidence.tar.gz.gpg", "size": 3, "sha256": sha(b"not")}}
        context_raw, manifest_raw = encoded(self.crypto), encoded(manifest)
        phases = {name: sha(inert("prior-" + name)) for name in K.native.PHASE_FILES}
        parent = {**closed("INITIAL_CUSTODY_CRYPTO_PARENT_KNOWN_CLOSE_V1"), "contextSha256": sha(context_raw),
            "childSha256": sha(inert("prior-child")), "authorityCopyCloseSha256": sha(inert("prior-close")),
            "phaseSha256": phases, "closedNs": self.work + 40 * NS}
        carrier = {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_CLOSED_RETURN_V1",
            **{name: manifest[name] for name in ("kind", "selection", "source", "github", "policy", "primary", "recipient")},
            "authority": manifest["initialRecipient"],
            "window": {**{name: value for name, value in self.frame.items() if name not in ("schema", "scope", "kind")},
                "lastNs": self.work + 41 * NS, "lastLocal": 70.0},
            "copy": {**copied, "path": self.session + "/INERT-COPY", "directoryIdentity": pins["copied-evidence"],
                "sourceMetadataSha256": {name: sha(inert(name + "-metadata")) for name in K.ORIGINS},
                "destinationMetadataSha256": sha(inert("destination-metadata"))},
            "exporter": {"manifestBase64": base64.b64encode(manifest_raw).decode("ascii"), "manifestBytes": len(manifest_raw),
                "manifestSha256": sha(manifest_raw), "childSha256": parent["childSha256"], "ackSha256": phases["stdout.log"],
                "phaseSha256": phases, "nativeResources": parent["resources"]}, "parentClose": parent, **PENDING}
        carrier_raw = encoded(carrier)
        self.step = {"schema": 1, "scope": K._EXPORT_STEP_SCOPE, "kind": kind, "step": "initial-custody-export",
            "primary": primary, "originalServiceJob": [51, "2026-09-26T00:00:00Z", "NOT-A-RUNNER", 52],
            "directory": self.session, "directoryIdentity": pins["returned"], "cryptoCarrier": {
                "sha256": sha(carrier_raw), "bytes": len(carrier_raw), "exporterReturnSha256": sha(manifest_raw), "metadataClose": closed()},
            "originalWindow": self.frame, "originalContextSha256": sha(context_raw), "observed": self.observed,
            "lowerNs": self.work + 42 * NS, "lowerLocal": 71.0,
            "sample": "AFTER_CRYPTO_CARRIER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN", **PENDING}
        self.prior = {"step": encoded(self.step), "carrier": carrier_raw, "context": context_raw, "manifest": manifest_raw,
            **{key: crypto_inputs[name] for key, name in (("original-match", "original-match.json"), ("fresh-match", "fresh-match.json"),
                ("event", "event.json"), ("policy", "candidate-policy.json"), ("public", "recipient-public.asc"))}}
        self.collect = {"schema": 1, "scope": K._COLLECT_SCOPE, "kind": kind, "edge": "POST_EXPORT",
            "predecessor": self.predecessor(False), "primary": primary, "originalWindow": self.frame,
            "lastNs": self.work + 56 * NS, "lastLocal": 72.0, "authority": {},
            "parentClose": closed("INITIAL_POST_EXPORT_AUTHORITY_PARENT_KNOWN_CLOSE_V1"), **PENDING}
        first = self.work + 76 * NS
        self.seal = {"schema": 1, "scope": K._TAIL_SEAL_SCOPE, "kind": kind, "edge": "SEAL", "predecessor": {},
            "primary": primary, **{name: manifest[name] for name in ("source", "github", "policy")}, "originalWindow": self.frame,
            "firstNs": first, "hardEndNs": self.frame["sealEndNs"], "lastNs": first + 12 * NS, "lastLocal": 73.0,
            "manifestSha256": sha(manifest_raw), "output": {"scope": "THIS_SEAL_FILE_OBSERVATION_NOT_HISTORICAL_POSIX_OUTPUT_PIN",
                "directoryIdentity": pins["export-output"], "fileMetadataSha256": sha(inert("seal-metadata")), "artifact": manifest["artifact"]},
            "authority": {"schema": 1, "scope": "INITIAL_SEAL_AUTHORITY_CLOSED_RETURN_V1", "edge": "SEAL", "authority": {},
                "parentClose": closed("INITIAL_SEAL_AUTHORITY_PARENT_KNOWN_CLOSE_V1"), "preCloseNs": first + 9 * NS,
                "closedNs": first + 10 * NS, "testAcceptance": "NOT_PERFORMED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False},
            "inputMetadataClose": closed(), "decryption": "NOT_PERFORMED", "upload": "NOT_PERFORMED", **PENDING}
        self.raws, self.full = {}, {}
        for side in ("authority-2", "authority-seal"):
            self.episode(side)
            self.relink()

    def pin(self, ordinal):
        return [35, format(ordinal, "032x") if self.role == "windows-x64" else ordinal]

    def predecessor(self, sealing):
        if not sealing:
            return {"step": "initial-custody-export", "outcome": "success", "stepSha256": sha(self.prior["step"]),
                "cryptoCarrierSha256": sha(self.prior["carrier"]), "exporterReturnSha256": sha(self.prior["manifest"])}
        return {"step": "initial-custody", "outcome": "success", "collectSha256": sha(self.prior["collect"]),
            "cryptoStepSha256": sha(self.prior["step"]), "cryptoCarrierSha256": sha(self.prior["carrier"]),
            "exporterReturnSha256": sha(self.prior["manifest"])}

    def query_session(self, context, side, originals, serial):
        root = Path(context["session"]) / side
        files = {"owner.json": inert("unqualified-query-owner")}
        queries, readbacks = [], []

        def retain(relative, raw, limit=None):
            files[relative] = raw
            path = root / relative
            readbacks.append({"parent": str(path.parent), "name": path.name, "maximum": max(1, len(raw)) if limit is None else limit,
                "retirement": "KNOWN", "result": "RETAINED", "bytes": len(raw), "sha256": sha(raw)})

        retain("owner.json", files["owner.json"])
        acquisition = side == "acquisition-queries"
        if acquisition:
            retain("event.bin", originals["event"])
        blob = originals["candidate_policy_entry"].split()[2].decode("ascii")
        commands = (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
            ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", self.source["commit"] + "^{tree}"),
            ("rev-parse", "--is-shallow-repository"), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
            ("rev-parse", "--verify", K.A.stages.BASE["commit"] + "^{tree}"),
            ("ls-tree", "-z", K.A.stages.BASE["commit"], "--", K.I.POLICY_PATH),
            ("merge-base", K.A.stages.BASE["commit"], self.source["commit"]), ("ls-tree", "-z", self.source["commit"], "--", K.I.POLICY_PATH),
            ("cat-file", "-s", blob), ("cat-file", "blob", blob))
        for number in range(24 if acquisition else 12):
            identifier = format(serial + number + 1, "032x")
            out, err = b"tiny-declared-stream", b""
            limit = K.I.EVENT_LIMIT if number % 12 == 1 else K.I.POLICY_LIMIT if number % 12 == 11 else 4096
            row = {"schema": 1, "scope": "NATIVE_OWNED_ORDINARY_GIT_QUERY", "id": identifier,
                "job": format(serial, "032x"), "state": str(root), "home": str(root / "query-home"), "cwd": str(ROOT),
                "argv": ["INERT-GIT-NOT-EXECUTED", "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                    "-C", str(ROOT), *commands[number % 12]], "stdoutLimit": limit, "stderrLimit": 4096, "timeoutSeconds": 15,
                "launchAttempted": True, "scopeAttempted": True, "waitExitCode": 0, "retirement": "KNOWN",
                "result": "READY_FOR_CALLER_SEAL", "errors": [], "ownedSurvivors": [],
                "ownership": {"discoveryErrors": [], "model": "NOT_NATIVE_EVIDENCE"},
                "outputs": {label: {"bytes": len(raw), "sha256": sha(raw)} for label, raw in (("stdout", out), ("stderr", err))}}
            queries.append(row)
            prefix = "query-" + identifier + "/"
            for name, raw, maximum in (("start.json", inert("unqualified-query-start"), None),
                    ("baseline.json", inert("unqualified-query-baseline"), None), ("stdout.log", out, limit),
                    ("stderr.log", err, 4096), ("result.json", encoded(row), None)):
                retain(prefix + name, raw, maximum)
            if acquisition and number == 11:
                for key in (*K.N.SOURCE_KEYS, *K.N.HTTP_KEYS):
                    retain(key + ".bin", originals[key])
        for key in (("observation", "match") if acquisition else K.N.SOURCE_KEYS):
            retain(key + ".bin", originals[key])
        raw = encoded({"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY", "job": format(serial, "032x"),
            "queries": queries, "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN", "firstError": None,
            "errors": [], "readbacks": readbacks})
        files["session-result.json"] = raw
        return files

    def episode(self, side):
        sealing = side == "authority-seal"
        first = self.work + (76 if sealing else 45) * NS
        original = {name: inert("supplied-" + name) for name in K.N.ORIGINAL_KEYS}
        blob = hashlib.sha1(b"blob " + str(len(self.prior["policy"])).encode("ascii") + b"\0" + self.prior["policy"]).hexdigest()
        original.update(event=self.prior["event"], match=self.prior["original-match"], candidate_policy_raw=self.prior["policy"],
            base_policy_entry=b"", ancestry_raw=(K.A.stages.BASE["commit"] + "\n").encode("ascii"),
            candidate_policy_entry=("100644 blob " + blob + "\t" + K.I.POLICY_PATH).encode("ascii") + b"\0")
        context = {"schema": 1, "scope": K.native.INITIAL_TAIL_AUTHORITY_CONTEXT_SCOPE if sealing else K.native.INITIAL_COLLECT_AUTHORITY_CONTEXT_SCOPE,
            "edge": "SEAL" if sealing else "POST_EXPORT", "kind": self.kind, "root": str(ROOT),
            "session": str(Path(self.session).parent / side), "job": ("b" if sealing else "9") * 32,
            "observed": self.observed, "originalWindow": self.frame, "originalServiceJob": self.step["originalServiceJob"],
            "predecessor": self.predecessor(sealing), "expectedMatch": decoded(self.prior["original-match"]),
            "eventSha256": sha(self.prior["event"]), "sourceReturnSha256": "0" * 64, "sourceReturnedNs": first + NS,
            "inheritedContext": {}, "directoryIdentity": self.pin(200 if sealing else 100),
            "parentFirstNs": first, "continuationEndNs": min(first + 30 * NS, self.frame["sealEndNs" if sealing else "readEndNs"]),
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        small, complete = {}, {}
        for index, part in enumerate(("source-before", "source-after", "acquisition-queries")):
            selected = original if part == "acquisition-queries" else {name: original[name] for name in K.N.SOURCE_KEYS}
            files = self.query_session(context, part, selected, (2000 if sealing else 1000) + index * 100)
            if part != "acquisition-queries":
                files["source-return.json"] = encoded({"schema": 1, "scope": K.N.SOURCE_SCOPE,
                    "originalsSha256": {name: sha(raw) for name, raw in selected.items()},
                    "sessionSha256": sha(files["session-result.json"]), "clock": self.clock,
                    "returnedNs": first + (1 if part == "source-before" else 6) * NS})
            complete.update({part + "/" + name: raw for name, raw in files.items()})
            small.update({part + "/" + name: raw for name, raw in files.items()
                if part + "/" + name in K._HISTORICAL_AUTHORITY_LIMITS})
        context["sourceReturnSha256"] = sha(small["source-before/source-return.json"])
        small["context.json"] = encoded(context)
        small.update({"service/" + name: inert("opaque-not-qualified-phase-" + name) for name in K.native.PHASE_FILES})
        small["service/child-result.json"] = encoded({"contextSha256": sha(small["context.json"]),
            "retirement": "PENDING_CHILD_CLOSE", "querySessionSha256": sha(small["acquisition-queries/session-result.json"]),
            "originalsSha256": {name: sha(raw) for name, raw in original.items()},
            "directoryIdentities": {".": context["directoryIdentity"], "service": self.pin(201 if sealing else 101)}})
        self.raws[side], self.full[side] = small, {**complete, **small}
        binding = {"expectedMatchSha256": sha(original["match"]), "freshMatchSha256": sha(original["match"]),
            "invocation": ("6" if sealing else "5") * 32, "startedNs": first + 2 * NS,
            "workEndNs": context["continuationEndNs"], "finalEndNs": context["continuationEndNs"],
            "acquiredNs": first + 4 * NS, "checkedNs": first + 8 * NS, "closedNs": first + 10 * NS}
        if sealing:
            self.seal["authority"]["authority"] = binding
        else:
            self.collect["authority"] = binding

    def relink(self):
        """Recompute outer hash links without fixing attacked semantic values."""
        for side in ("authority-2", "authority-seal"):
            if side not in self.raws:
                continue
            sealing, raw = side == "authority-seal", self.raws[side]
            context = decoded(raw["context.json"])
            if sealing:
                context["predecessor"]["collectSha256"] = sha(self.prior["collect"])
            context["sourceReturnSha256"] = sha(raw["source-before/source-return.json"])
            raw["context.json"] = encoded(context)
            child = decoded(raw["service/child-result.json"])
            child["contextSha256"] = sha(raw["context.json"])
            raw["service/child-result.json"] = encoded(child)
            binding = self.seal["authority"]["authority"] if sealing else self.collect["authority"]
            binding.update(contextSha256=sha(raw["context.json"]), sourceBeforeSha256=sha(raw["source-before/source-return.json"]),
                sourceAfterSha256=sha(raw["source-after/source-return.json"]), childSha256=sha(raw["service/child-result.json"]),
                querySessionSha256=sha(raw["acquisition-queries/session-result.json"]),
                originalsSha256={name: sha(raw["acquisition-queries/" + name + ".bin"]) for name in K.N.ORIGINAL_KEYS},
                phaseSha256={name: sha(raw["service/" + name]) for name in K.native.PHASE_FILES},
                ackSha256=sha(raw["service/stdout.log"]))
            self.full[side].update(raw)
            if not sealing:
                self.prior["collect"] = encoded(self.collect)
        if "authority-seal" in self.raws:
            self.seal["predecessor"] = self.predecessor(True)

    def index(self, authorities=None):
        raw = encoded(self.seal)
        return guarded(K._historical_tail_authority_indexes, self.prior, raw,
            self.raws if authorities is None else authorities, outcome="success", expected_sha256=sha(raw))

    def query(self, part, value=None):
        raw = dict(self.raws["authority-2"])
        if value is not None:
            raw[part + "/session-result.json"] = encoded(value)
        return guarded(K._historical_query_index, decoded(raw["context.json"]), part, raw)


class ExistingAuthorityInventoryControls(unittest.TestCase):
    def rejects(self, function, *args, reason=None, **kwargs):
        with self.assertRaises(ValueError) as caught:
            function(*args, **kwargs)
        if reason is not None:
            self.assertIn(reason, str(caught.exception))

    def test_exact_pair_558_files_116_directories_from_36_binding_inputs_each(self):
        model = Grammar()
        result = decoded(model.index())
        self.assertEqual((result["fileCount"], result["directoryCount"]), (558, 116))
        expected = {side + "/" + name: (len(raw), sha(raw)) for side, files in model.full.items() for name, raw in files.items()}
        self.assertEqual({row["relative"]: (row["bytes"], row["sha256"]) for row in result["files"]}, expected)
        self.assertEqual([len(value) for value in model.raws.values()], [36, 36])
        self.assertEqual(result["totalBytes"], sum(count for count, _ in expected.values()))
        for side in ("authority-2", "authority-seal"):
            self.assertEqual(sum(row["relative"].startswith(side + "/") for row in result["files"]), 279)

    def test_gate_worker_and_four_role_fields_are_historical_data_only(self):
        for kind, role in (("gate", "linux-x64"), *(("worker", role) for role in K.Q._ROLES)):
            with self.subTest(kind=kind, role=role):
                result = decoded(Grammar(kind, role).index())
                self.assertEqual(result["copyState"], "NOT_COPIED")
                self.assertEqual(result["readback"], "NOT_PERFORMED")
                self.assertEqual(result["beforeAuthority"], "NOT_IMPLEMENTED")
                self.assertFalse(result["productiveAuthority"])

    def test_both_existing_episodes_required_no_b_or_other_extension(self):
        model = Grammar()
        for keys in (("authority-2",), ("authority-seal",), ("authority-2", "authority-seal", "authority-before")):
            self.rejects(model.index, {key: model.raws.get(key, {}) for key in keys}, reason="HISTORY_AUTHORITY_PAIR")

    def test_binding_input_missing_extra_wrong_type_and_limit(self):
        model = Grammar()
        for change in (lambda raw: raw.pop("source-after/source-return.json"), lambda raw: raw.update(extra=b"x"),
                lambda raw: raw.update({"service/stdout.log": "not-bytes"}),
                lambda raw: raw.update({"context.json": b"x" * (K.native.LIMIT + 1)})):
            values = {key: dict(raw) for key, raw in model.raws.items()}
            change(values["authority-2"])
            self.rejects(model.index, values)

    def test_exact_query_counts_ids_and_readback_rosters(self):
        model = Grammar()
        for part in ("source-before", "source-after", "acquisition-queries"):
            original = decoded(model.raws["authority-2"][part + "/session-result.json"])
            for change in (lambda value: value["queries"].pop(), lambda value: value["queries"].append(value["queries"][0]),
                    lambda value: value["queries"][1].update(id=value["queries"][0]["id"]),
                    lambda value: value["readbacks"].pop(), lambda value: value["readbacks"].append(value["readbacks"][0])):
                value = copy.deepcopy(original)
                change(value)
                self.rejects(model.query, part, value)

    def test_reordered_extra_or_path_substituted_readbacks(self):
        model = Grammar()
        original = decoded(model.raws["authority-2"]["acquisition-queries/session-result.json"])
        for change in (lambda value: value["readbacks"].reverse(), lambda value: value["readbacks"][0].update(extra=0),
                lambda value: value["readbacks"][0].update(parent="/not-the-original"),
                lambda value: value["readbacks"][0].update(name="../owner.json"),
                lambda value: value["readbacks"][0].update(name="OWNER.JSON")):
            value = copy.deepcopy(original)
            change(value)
            self.rejects(model.query, "acquisition-queries", value)

    def test_each_query_stream_binds_declared_hash_and_count(self):
        model = Grammar()
        original = decoded(model.raws["authority-2"]["acquisition-queries/session-result.json"])
        for index, row in enumerate(original["readbacks"]):
            if row["name"] not in ("stdout.log", "stderr.log"):
                continue
            value = copy.deepcopy(original)
            value["readbacks"][index]["sha256"] = "0" * 64
            self.rejects(model.query, "acquisition-queries", value)

    def test_query_result_binds_exact_same_declared_query(self):
        model = Grammar()
        value = decoded(model.raws["authority-2"]["acquisition-queries/session-result.json"])
        next(row for row in value["readbacks"] if row["name"] == "result.json")["sha256"] = "1" * 64
        self.rejects(model.query, "acquisition-queries", value, reason="HISTORY_QUERY_RESULT_BINDING")

    def test_query_command_order_selected_executable_limits_and_typed_status(self):
        model = Grammar()
        original = decoded(model.raws["authority-2"]["source-before/session-result.json"])
        for change in (lambda row: row["argv"].append("--unexpected"), lambda row: row["argv"].__setitem__(0, "OTHER-GIT"),
                lambda row: row.update(stdoutLimit=True), lambda row: row.update(stderrLimit=4097),
                lambda row: row.update(timeoutSeconds=True), lambda row: row.update(timeoutSeconds=16),
                lambda row: row.update(waitExitCode=False), lambda row: row.update(retirement="UNKNOWN"),
                lambda row: row.update(scopeAttempted=1)):
            value = copy.deepcopy(original)
            change(value["queries"][1])
            self.rejects(model.query, "source-before", value)

    def test_source_return_clock_hash_and_typed_timestamp(self):
        for change in (lambda row: row.update(sessionSha256="0" * 64), lambda row: row.update(returnedNs=True),
                lambda row: row["clock"].update(ticksPerSecond=True),
                lambda row: row["originalsSha256"].update(base_policy_entry="0" * 64)):
            model = Grammar()
            raw = model.raws["authority-2"]
            value = decoded(raw["source-before/source-return.json"])
            change(value)
            raw["source-before/source-return.json"] = encoded(value)
            self.rejects(model.query, "source-before")

    def test_rehashed_context_source_service_job_window_and_policy_substitution(self):
        for change in (lambda context: context["observed"]["source"].update(commit="a" * 40),
                lambda context: context["originalServiceJob"].__setitem__(0, 999),
                lambda context: context["originalWindow"].update(afterEndNs=True),
                lambda context: context.update(eventSha256="0" * 64),
                lambda context: context["expectedMatch"].update(model="REPLACEMENT")):
            model = Grammar()
            context = decoded(model.raws["authority-2"]["context.json"])
            change(context)
            model.raws["authority-2"]["context.json"] = encoded(context)
            model.relink()
            self.rejects(model.index, reason="HISTORY_AUTHORITY_CONTEXT_BINDINGS")

    def test_rehashed_cross_episode_known_pin_alias_refused(self):
        model = Grammar("worker", "windows-x64")
        pin = decoded(model.raws["authority-2"]["context.json"])["directoryIdentity"]
        raw = model.raws["authority-seal"]
        for name in ("context.json", "service/child-result.json"):
            value = decoded(raw[name])
            if name == "context.json":
                value["directoryIdentity"] = pin
            else:
                value["directoryIdentities"]["."] = pin
            raw[name] = encoded(value)
        model.relink()
        self.rejects(model.index, reason="HISTORY_AUTHORITY_PAIR_LIMIT_OR_ALIAS")

    def test_phase_byte_binding_is_explicitly_not_complete_native_qualification(self):
        model = Grammar()
        model.raws["authority-2"]["service/baseline.json"] = inert("different-unqualified-native-body")
        self.rejects(model.index, reason="HISTORY_AUTHORITY_ORIGINAL_HASH")
        model.relink()
        value = decoded(model.index())
        self.assertEqual(value["nativeAcceptance"], "NOT_PERFORMED")
        self.assertEqual(value["readback"], "NOT_PERFORMED")

    def test_rehashed_source_bytes_still_match_bound_acquisition_policy(self):
        model = Grammar()
        model.raws["authority-2"]["source-before/candidate_policy_raw.bin"] = inert("replaced-source-policy")
        model.relink()
        self.rejects(model.index, reason="HISTORY_AUTHORITY_SOURCE_BYTES")

    def test_chronology_and_only_four_actually_declared_directory_pins(self):
        model = Grammar()
        value = decoded(model.index())
        self.assertEqual(sum(row["historicalPin"] is not None for row in value["directories"]), 4)
        self.assertEqual(sum(row["historicalPin"] is None for row in value["directories"]), 112)
        changed = decoded(model.raws["authority-2"]["source-after/source-return.json"])
        changed["returnedNs"] = model.frame["readEndNs"]
        model.raws["authority-2"]["source-after/source-return.json"] = encoded(changed)
        model.relink()
        self.rejects(model.index, reason="HISTORY_AUTHORITY_SOURCE_CHRONOLOGY")

    def test_session_caps_reject_huge_declared_bytes_without_allocating_them(self):
        model = Grammar()
        value = decoded(model.raws["authority-2"]["acquisition-queries/session-result.json"])
        for row in value["readbacks"]:
            if row["name"] in ("start.json", "baseline.json"):
                row.update(bytes=K.Q.MAX_RECEIPT_BYTES, maximum=K.Q.MAX_RECEIPT_BYTES, sha256="d" * 64)
        self.rejects(model.query, "acquisition-queries", value, reason="HISTORY_QUERY_SESSION_CAP")

    def test_empty_originals_and_streams_are_declared_not_freshly_read(self):
        result = decoded(Grammar().index())
        empty = [row for row in result["files"] if row["bytes"] == 0]
        self.assertTrue(empty)
        self.assertTrue(all(row["sha256"] == sha(b"") and row["maximum"] > 0 for row in empty))
        self.assertEqual(result["copyState"], "NOT_COPIED")
        self.assertEqual(result["readback"], "NOT_PERFORMED")
        self.assertEqual(result["budgetAcceptance"], "NOT_ADMITTED")

    def test_no_io_clock_owner_or_registry_capability_is_minted(self):
        model = Grammar()
        registries = (K._TAIL_INPUTS, K._TAIL_CLOCKS, K._TAIL_AUTHORITIES, K._TAIL_SEALS, K._TAIL_ATTEMPTS,
            K._COLLECT_INPUTS, K._COLLECT_CLOCKS, K._COLLECT_AUTHORITY_RETURNS, K._CUSTODY_OWNERS, K._PRIMARY_OWNERS)
        before = tuple(tuple(value.items()) for value in registries)
        with ExitStack() as stack:
            for target, name in ((K, "_paths"), (K.N, "host_context"), (K.N, "source_queries"),
                    (K.native, "Owner"), (K.native, "OriginalPhase"), (K.N, "SourceReturn"),
                    (K.time, "monotonic"), (K.time, "time"), (K.native.posix, "_key_identity")):
                stack.enter_context(patch.object(target, name, side_effect=AssertionError("LIVE_CALL_FORBIDDEN")))
            result = decoded(model.index())
        self.assertEqual(tuple(tuple(value.items()) for value in registries), before)
        self.assertFalse(result["exportSaveAuthority"])
        self.assertFalse(result["cacheAuthority"])


if __name__ == "__main__":
    unittest.main()
