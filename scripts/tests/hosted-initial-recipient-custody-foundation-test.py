#!/usr/bin/env python3
"""NEW supplied controls for the Stage1 custody foundation, not custody proof.

The compact generators below fill the declared counts with synthetic one-byte
members and empty directory rows. They do NOT reproduce the accepted reader,
collect real originals, authenticate Steps or validate an entire primary history.
No existing test/fixture is loaded. Only the actual new foundation and its pure
grammar/clock helpers run when this file is eventually executed. All clock/boot
observations are explicit models; native owners/acquisition/old collectors refuse.
"""
from __future__ import annotations

import base64
import ctypes  # Stdlib initialization before the no-native audit boundary.
import dataclasses
import hashlib
import importlib.util
import json
import math
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
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("custody_foundation_supplied_models",
    ROOT / "scripts/run-hosted-initial-recipient-custody.py")
D = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = D
_spec.loader.exec_module(D)
NS = 1_000_000_000
BASIS, START, LOCAL, BOOT = 30 * NS, 50 * NS, 100.0, "a" * 64


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_row(name, provenance="ACTUAL_RETAINED_BYTES", raw=b"x"):
    # Independent test grammar, not N._worker_file or the production classifier.
    return {"relative": name, "parent": name.rsplit("/", 1)[0], "maximum": max(1, len(raw)),
            "bytes": len(raw), "sha256": digest(raw), "provenance": provenance}


def primary_model(kind="gate", role="linux-x64"):
    """Only an in-memory carrier-shape model; success/hash inputs are supplied."""
    roots = {name: Path("/synthetic") / ("primary-" + name) for name in
             (("P",) if kind == "gate" else ("P", "E", "R", "S", "I", "T", "C"))}
    path = (roots["P"] if kind == "gate" else roots["I"]).with_name("synthetic-handoff")
    identity = (1, "f" * 32) if role == "windows-x64" else (1, 9999)
    pending = wire({"supplied": "initialization-or-gate-result"})
    result = digest(pending)
    if kind == "gate":
        pin_names = (".", "control-home", "temporary", "service", "source-before", "source-after",
                     "acquisition-queries")
        eligibility = {"supplied": "gate-eligibility-NOT-authenticated-history"}
        index = {"schema": 1, "scope": D.N.GATE_INVENTORY_SCOPE, "root": str(roots["P"]),
            "contextSha256": "1" * 64, "initialOriginalsSha256": result,
            "gateEligibilitySha256": digest(wire(eligibility)), "source": {}, "github": {}, "policy": {},
            "directories": sorted((*pin_names, *(f"supplied-empty-{n:02d}" for n in range(51)))),
            "files": [{"relative": f"supplied-file-{n:03d}.bin", "maximum": 1, "bytes": 1,
                       "sha256": digest(b"x")} for n in range(281)],
            "copyState": "ORIGINAL_BYTES_NOT_COPIED", "nestedNativePins": "NOT_CAPTURED",
            "exportSaveAuthority": False}
        extra = {"gateEligibility": eligibility, "originalClosedNs": 10,
            "clock": {"supplied": role}, "bootDigest": BOOT, "preludeSha256": "2" * 64,
            "originalNativeDirectories": [{"path": str(roots["P"] if name == "." else roots["P"] / name),
                "identity": [1, n + 100]} for n, name in enumerate(pin_names)],
            "originalClose": {"retirement": "KNOWN", "resources": ["directory"] * 7}}
    else:
        index = worker_index(roots, role, result)
        authority, history = wire({"supplied": "authority-return"}), wire({"supplied": "initialization-history"})
        index["authoritySha256"] = digest(authority)
        extra = {"embeddedOriginals": [{"name": name, "bytes": len(raw), "sha256": digest(raw),
            "rawBase64": base64.b64encode(raw).decode("ascii")} for name, raw in (
                ("receiving-authority-return.json", authority), ("initialization-history.json", history))],
            "originalClose": {"authority": "KNOWN_RESOURCE_CLOSE_ONLY", "receiving": "KNOWN_RESOURCE_CLOSE_ONLY"}}
    value = {"schema": 1, "scope": D.N.GATE_HANDOFF_SCOPE if kind == "gate" else D.N.WORKER_HANDOFF_SCOPE,
        "directory": str(path), "directoryIdentity": list(identity), "inventory": index, **extra,
        "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED",
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    return SimpleNamespace(kind=kind, role=role, roots=roots, path=path, identity=identity, result=result, value=value)


def worker_index(roots, role, result):
    """Small declaration generator, NOT a WorkerModel or accepted-reader fixture."""
    windows = role == "windows-x64"
    directories, files = [], []
    serial = 0

    def directory(name, provenance):
        nonlocal serial
        serial += 1
        identity = None if provenance == "ORIGINAL_AUTHORITY_DECLARED_DIRECTORY" else (
            [1, f"{serial:032x}"] if windows else [1, serial + 100])
        group, *parts = name.split("/")
        directories.append({"relative": name, "parent": name.rsplit("/", 1)[0] if parts else None,
            "path": str(roots[group].joinpath(*parts)), "identity": identity, "provenance": provenance})

    receiver = "RECEIVER_READBACK_NATIVE_PIN"
    for group, count in (("P", 58), ("E", 58), ("R", 105), ("S", 1)):
        directory(group, receiver)
        if group == "R":
            directory("R/crypto", receiver)
        for n in range(count - (2 if group == "R" else 1)):
            directory(f"{group}/supplied-empty-{n:03d}", receiver)
    for name in ("I", "I/canonical-init", "I/control-home", "I/temporary", "I/state", "I/state/gradle-home",
                 "I/state/evidence", "I/state/cancellations"):
        directory(name, "ORIGINAL_INITIALIZER_NATIVE_PIN")
    for name in ("I/authority", "I/authority/control-home", "I/authority/temporary", "I/authority/service",
                 "I/authority/source-before", "I/authority/source-after", "I/authority/acquisition-queries"):
        directory(name, "ORIGINAL_AUTHORITY_NATIVE_PIN")
    for parent in ("I/authority/source-before", "I/authority/source-after", "I/authority/acquisition-queries"):
        directory(parent + "/query-home", "ORIGINAL_AUTHORITY_DECLARED_DIRECTORY")
        files.append(file_row(parent + "/owner.json", "ORIGINAL_AUTHORITY_QUERY_DECLARATION"))
        for number in range(16):
            name = parent + f"/query-{number + 1:032x}"
            directory(name, "ORIGINAL_AUTHORITY_DECLARED_DIRECTORY")
            for leaf in ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"):
                files.append(file_row(name + "/" + leaf, "ORIGINAL_AUTHORITY_QUERY_DECLARATION"))
    directory("T", "SENDER_STEP_RECEIVER_READBACK_NATIVE_PIN")
    directory("C", "CRYPTO_SIDECAR_RECEIVER_READBACK_NATIVE_PIN")
    operations = tuple(f"gpg-{n + 1:032x}" if windows else f"gpg-supplied_{n}" for n in range(3 if windows else 2))
    for name in ("gnupg", "tmp", *operations):
        directory("R/crypto/" + name, "AUTHENTICATED_ORIGINAL_CRYPTO_NATIVE_PIN")
    crypto_names = ["recipient.asc", "recipient.gpg"]
    if windows:
        crypto_names.append("recipient-validation-result-" + "e" * 32 + ".json")
    crypto_names.extend(name + "/" + leaf for name in operations for leaf in
                        (("stdout", "stderr") if windows else ("stdout", "stderr", "status", "process.json")))
    files.extend(file_row("R/crypto/" + name, "AUTHENTICATED_CRYPTO_DECLARATION") for name in crypto_names)
    for group, count in (("P", 284), ("E", 281), ("R", 498), ("S", 3)):
        files.extend(file_row(f"{group}/supplied-file-{n:03d}.bin") for n in range(count))
    files.extend(file_row(f"I/authority/supplied-retained-{n:02d}.json") for n in range(38))
    files.extend(file_row(f"I/supplied-initializer-{n:02d}.json") for n in range(12))
    files.extend((file_row("T/step-pending.json"), file_row("C/crypto-originals.json")))
    return {"schema": 1, "scope": D.N.WORKER_INVENTORY_SCOPE,
        "roots": [{"group": key, "path": str(path)} for key, path in roots.items()],
        "source": {}, "github": {}, "clock": {"supplied": role},
        "senderSha256": "1" * 64, "recipientStepSha256": "2" * 64, "recipientCryptoOriginalsSha256": "3" * 64,
        "initializationSha256": result, "authoritySha256": "4" * 64, "workerIdentitySha256": "5" * 64,
        "files": sorted(files, key=lambda row: row["relative"]), "fileCount": len(files),
        "fileCounts": {group: sum(row["relative"].split("/", 1)[0] == group for row in files) for group in roots},
        "directories": sorted(directories, key=lambda row: row["relative"]), "directoryCount": len(directories),
        "directoryCounts": {group: sum(row["relative"].split("/", 1)[0] == group for row in directories) for group in roots},
        "totalBytes": sum(row["bytes"] for row in files), "copyState": "ORIGINAL_BYTES_NOT_COPIED",
        "liveRecipient": "NOT_TRANSFERRED", "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
        "exportSaveAuthority": False}


class OfflineFoundation(unittest.TestCase):
    def setUp(self):
        for target, name in ((D.A, "acquire_bootstrap"), (D.N, "_retained_match_inputs"),
                (D.N, "_retained_match_at"), (D.N, "_gate_inventory"), (D.N, "_capture_worker_reader"),
                (D.N, "_capture_worker_originals"), (D.N, "_worker_crypto_index"), (D.native, "phase"),
                (D.native.Owner, "__init__"), (D.Q.NativeGitQueries, "__init__"),
                (D.O.clocks, "observe"), (D.C, "boot_digest")):
            self.install(target, name, side_effect=AssertionError("FOUNDATION_MUST_NOT_EXECUTE_OLD_OR_NATIVE_PIPELINE"))

    def install(self, target, name, value=None, **kwargs):
        manager = patch.object(target, name, **kwargs) if kwargs else patch.object(target, name, value)
        result = manager.start()
        self.addCleanup(manager.stop)
        return result


class PrimaryGrammarControls(OfflineFoundation):
    def decode(self, model, **changes):
        raw = wire(model.value)
        kwargs = {"outcome": "success", "result_sha256": model.result, "handoff_sha256": digest(raw)}
        kwargs.update(changes)
        return D.primary_record(model.kind, model.role, model.roots, model.path, model.identity, raw, **kwargs)

    def refuse(self, model, pattern, **changes):
        with self.assertRaisesRegex(ValueError, pattern):
            self.decode(model, **changes)

    def test_gate_model_retains_seven_original_pins_and_fifty_one_declarations(self):
        model = primary_model()
        result = self.decode(model)
        self.assertIs(type(result), D.Primary)
        self.assertEqual((len(result.files), len(result.directories)), (281, 58))
        self.assertEqual(sum(row[1] is not None for row in result.directories), 7)
        self.assertEqual(sum(row[1] is None for row in result.directories), 51)
        self.assertEqual(result.handoff_raw, wire(model.value))
        self.assertEqual(result.embedded, ())

    def test_each_gate_pin_must_be_in_the_directory_roster_despite_preserved_counts(self):
        for missing in (".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries"):
            with self.subTest(missing=missing):
                model = primary_model()
                rows = model.value["inventory"]["directories"]
                rows[rows.index(missing)] = "supplied-replacement-empty"
                rows.sort()
                self.assertEqual(len(rows), 58)
                self.refuse(model, "GATE_ALL_ORIGINAL_PINS_REQUIRED")

    def test_gate_pin_alias_duplicate_path_and_changed_pin_roster_refuse(self):
        for mode in ("identity", "path", "roster"):
            model = primary_model()
            rows = model.value["originalNativeDirectories"]
            if mode == "identity":
                rows[1]["identity"] = rows[0]["identity"][:]
            elif mode == "path":
                rows[1]["path"] = rows[0]["path"]
            else:
                rows[1]["path"] += "-replacement"
            self.refuse(model, "PRIMARY_DIRECTORY_ALIAS|GATE_DUPLICATE_NATIVE_PIN|GATE_NATIVE_PIN_ROSTER")

    def test_primary_success_and_both_original_digest_edges_are_required(self):
        model = primary_model()
        for outcome in ("failure", "cancelled", "skipped", "NOT_OBSERVED"):
            self.refuse(model, "PRIMARY_SUCCESS_REQUIRED", outcome=outcome)
        self.refuse(model, "PRIMARY_HANDOFF_HASH", handoff_sha256="0" * 64)
        self.refuse(model, "GATE_INDEX_SCOPE", result_sha256="0" * 64)
        model.value["writerReturn"] = "KNOWN"
        self.refuse(model, "PRIMARY_PENDING_RECORD")

    def test_name_case_parent_and_empty_file_hash_controls_are_not_count_only(self):
        model = primary_model()
        files = model.value["inventory"]["files"]
        files[1]["relative"] = files[0]["relative"].upper()
        files.sort(key=lambda row: row["relative"])
        # The maintained component grammar rejects uppercase before the final
        # names pass, using QueryError (RuntimeError), not the driver's ValueError.
        with self.assertRaisesRegex(D.Q.QueryError, "QUERY_COMPONENT"):
            self.decode(model)
        for mode in ("parent", "empty"):
            model = primary_model()
            files = model.value["inventory"]["files"]
            if mode == "parent":
                files[0]["relative"] = "not-declared/child.bin"
            else:
                files[0]["bytes"] = 0
            files.sort(key=lambda row: row["relative"])
            self.refuse(model, "PRIMARY_NAMES|GATE_EMPTY_HASH")

    def test_worker_count_models_keep_memory_originals_distinct_from_disk_files(self):
        for role, count, directories in (("linux-x64", 1371, 294), ("windows-x64", 1370, 295)):
            with self.subTest(role=role):
                result = self.decode(primary_model("worker", role))
                self.assertEqual((len(result.files), len(result.directories)), (count, directories))
                self.assertEqual(sum(row[1] is None for row in result.directories), 51)
                self.assertEqual(tuple(name for name, _ in result.embedded),
                    ("receiving-authority-return.json", "initialization-history.json"))
                self.assertTrue(all(type(raw) is bytes for _, raw in result.embedded))
                self.assertTrue(all(name not in {row[0] for row in result.files} for name, _ in result.embedded))

    def test_swapping_worker_pin_and_declared_provenance_cannot_preserve_acceptance(self):
        model = primary_model("worker")
        rows = model.value["inventory"]["directories"]
        pinned = next(row for row in rows if row["relative"] == "P")
        declared = next(row for row in rows if row["relative"] == "I/authority/source-before/query-home")
        for field in ("identity", "provenance"):
            pinned[field], declared[field] = declared[field], pinned[field]
        self.assertEqual(sum(row["identity"] is None for row in rows), 51)
        self.refuse(model, "WORKER_DIRECTORY_PROVENANCE")

    def test_required_worker_native_paths_cannot_be_replaced_by_equal_count_receiver_rows(self):
        model = primary_model("worker")
        row = next(row for row in model.value["inventory"]["directories"] if row["relative"] == "I/control-home")
        row.update(relative="P/replacement", parent="P", path=str(model.roots["P"] / "replacement"),
                   provenance="RECEIVER_READBACK_NATIVE_PIN")
        self.refuse(model, "WORKER_REQUIRED_PIN_PATHS")

    def test_swapped_crypto_and_authority_file_provenances_are_not_global_counts(self):
        for donor in ("AUTHENTICATED_CRYPTO_DECLARATION", "ORIGINAL_AUTHORITY_QUERY_DECLARATION"):
            model = primary_model("worker")
            rows = model.value["inventory"]["files"]
            target = next(row for row in rows if row["relative"].startswith("P/"))
            source = next(row for row in rows if row["provenance"] == donor)
            target["provenance"], source["provenance"] = source["provenance"], target["provenance"]
            self.refuse(model, "WORKER_FILE_PROVENANCE")

    def test_crypto_directory_names_are_role_specific_shallow_not_arbitrary_subtrees(self):
        for role, wrong in (("linux-x64", "gnupg/nested"), ("linux-x64", "private-keys-v1.d"),
                            ("linux-x64", "gpg-UPPER"), ("windows-x64", "gpg-too_short"),
                            ("windows-x64", "gpg-" + "g" * 32)):
            with self.subTest(role=role, name=wrong):
                with self.assertRaisesRegex(ValueError, "WORKER_CRYPTO_DIRECTORY"):
                    D._worker_directory_provenance("R/crypto/" + wrong, role)
        self.assertEqual(D._worker_directory_provenance("R/crypto", "linux-x64"), "RECEIVER_READBACK_NATIVE_PIN")
        self.assertEqual(D._worker_directory_provenance("R/crypto/gpg-a_1", "linux-x64"),
                         "AUTHENTICATED_ORIGINAL_CRYPTO_NATIVE_PIN")

    def test_crypto_home_and_operation_directory_totals_remain_required(self):
        model = primary_model("worker")
        row = next(row for row in model.value["inventory"]["directories"] if row["relative"] == "R/crypto/gnupg")
        row.update(relative="R/crypto/gpg-replacement", path=str(model.roots["R"] / "crypto/gpg-replacement"))
        self.refuse(model, "WORKER_CRYPTO_DIRECTORY_COUNT")

    def test_worker_totals_and_embedded_originals_refuse_changed_declarations(self):
        for mode in ("file-count", "total", "embedded-size", "embedded-name", "authority-hash"):
            model = primary_model("worker")
            index = model.value["inventory"]
            if mode == "file-count":
                index["fileCount"] = True
            elif mode == "total":
                index["totalBytes"] += 1
            elif mode == "embedded-size":
                model.value["embeddedOriginals"][1]["bytes"] += 1
            elif mode == "embedded-name":
                model.value["embeddedOriginals"][1]["name"] = "invented-disk-file.json"
            else:
                index["authoritySha256"] = "0" * 64
            self.refuse(model, "WORKER_COMPLETE_ROSTERS|WORKER_TOTAL_BYTES|WORKER_EMBEDDED_|WORKER_AUTHORITY_RETURN_BINDING")


class ScheduleControls(OfflineFoundation):
    def test_exact_gate_worker_tail_offsets_and_residual_boundaries(self):
        for kind, offset, work_offset, job_offset in (("gate", 0, 180, 360), ("gate", 179, 180, 360),
                ("worker", 0, 240, 1200), ("worker", 780, 1020, 1200), ("worker", 1019, 1020, 1200)):
            result = D.schedule(kind, BASIS, BASIS + offset * NS)
            expected_work = BASIS + work_offset * NS
            self.assertEqual(result["workEndNs"], expected_work)
            self.assertEqual(result["jobEndNs"], BASIS + job_offset * NS)
            self.assertEqual(tuple(result[name] - expected_work for name in D.WINDOW_NAMES),
                             tuple(value * NS for value in (0, 45, 75, 105, 165, 180)))
            self.assertLessEqual(result["afterEndNs"], result["jobEndNs"])

    def test_no_work_at_exact_residual_boundary_and_invalid_clock_types_refuse(self):
        for kind, offset in (("gate", 180), ("gate", 181), ("worker", 1020), ("worker", 1200)):
            with self.assertRaisesRegex(ValueError, "WINDOW_NO_WORK"):
                D.schedule(kind, BASIS, BASIS + offset * NS)
        for kind, basis, start in (("ordinary", BASIS, START), ("gate", True, START),
                                  ("gate", BASIS, float(START)), ("gate", BASIS, BASIS - 1),
                                  ("gate", D.O.clocks.UINT64, D.O.clocks.UINT64)):
            with self.assertRaises(ValueError):
                D.schedule(kind, basis, start)


class FalseyFailure(RuntimeError):
    def __init__(self, text):
        super().__init__(text)
        self.truthiness_calls = 0

    def __bool__(self):
        self.truthiness_calls += 1
        return False


class WindowControls(OfflineFoundation):
    def setUp(self):
        super().setUp()
        self.install(D, "_WINDOWS", {})  # Supplied model isolation; no real owner/registry is adopted.
        self.clock = D.O.clocks.ClockIdentity("linux-x64", D.O.clocks.DOMAINS["linux-x64"], NS)
        self.first = D.O.clocks.Reading(self.clock, START)
        self.local_current, self.raw_current = LOCAL, START
        self.local_values = self.raw_values = None
        self.local_action = self.raw_action = self.boot_action = self.cancel_action = None
        self.local_calls = self.raw_calls = self.boot_calls = self.cancel_calls = 0
        self.minimums = []
        self.install(D, "time", SimpleNamespace(monotonic=self.local_sample))
        self.install(D.O.clocks, "checked_now", side_effect=self.raw_sample)
        self.install(D.C, "boot_digest", side_effect=self.boot_sample)
        self.window = self.new_window()

    def new_window(self, **changes):
        inputs = {"first": self.first, "local": LOCAL, "original_boot": BOOT,
                  "limits": D.schedule("gate", BASIS, START), "cancelled": self.cancel}
        inputs.update(changes)
        return D.Window(**inputs)

    def local_sample(self):
        self.local_calls += 1
        if self.local_action is not None:
            return self.local_action()
        if self.local_values is not None:
            return next(self.local_values)
        self.local_current += 0.01
        return self.local_current

    def raw_sample(self, clock, *, minimum_ns):
        self.raw_calls += 1
        self.assertIs(clock, self.clock)
        self.minimums.append(minimum_ns)
        if self.raw_action is not None:
            return self.raw_action()
        if self.raw_values is not None:
            return next(self.raw_values)
        self.raw_current += 1
        return self.raw_current

    def boot_sample(self, role):
        self.boot_calls += 1
        self.assertEqual(role, self.clock.role)
        return self.boot_action() if self.boot_action is not None else BOOT

    def cancel(self):
        self.cancel_calls += 1
        if self.cancel_action is not None:
            self.cancel_action()

    def counters(self):
        return self.local_calls, self.raw_calls, self.boot_calls, self.cancel_calls

    def sticky(self, window, original):
        self.assertIs(D._WINDOWS[id(window)].failure, original)
        counts = self.counters()
        for invoke in (window.now, lambda: window.deadline(0), lambda: window.now(final=True)):
            with self.assertRaises(type(original)) as caught:
                invoke()
            self.assertIs(caught.exception, original)
        self.assertEqual(self.counters(), counts)
        self.assertFalse(D._WINDOWS[id(window)].busy)

    def test_now_keeps_original_clock_boot_and_each_validated_raw_minimum(self):
        self.local_values = iter((100.25, 100.5, 100.75))
        self.raw_values = iter((START + 10, START + 20))
        self.assertEqual(self.window.now(), START + 20)
        self.assertEqual(self.minimums, [START, START + 10])
        self.assertEqual(self.window.last, START + 20)
        self.assertIs(self.window.clock, self.clock)
        self.assertEqual(D._WINDOWS[id(self.window)].local_last, 100.75)
        self.assertEqual((self.boot_calls, self.cancel_calls), (1, 1))

    def test_deadline_charges_the_initial_local_sample_and_only_shortens(self):
        self.local_values = iter((101.0, 101.1, 101.2, 101.3))
        self.raw_values = iter((START + NS, START + 2 * NS))
        end = self.window.deadline(5)
        self.assertEqual(end, math.nextafter(106.0, -math.inf))
        self.assertLess(end, 106.0)
        self.assertEqual(D._WINDOWS[id(self.window)].local_last, 101.3)
        self.assertEqual(self.minimums, [START, START + NS])

    def test_initial_deadline_sample_is_checked_against_prior_local_highwater(self):
        self.local_values = iter((101.0, 102.0, 103.0))
        self.window.now()
        raw_calls = self.raw_calls
        self.local_values = iter((102.5,))
        with self.assertRaisesRegex(ValueError, "WINDOW_DEADLINE_LOCAL") as caught:
            self.window.deadline(5)
        self.assertEqual(self.raw_calls, raw_calls)
        self.assertEqual(D._WINDOWS[id(self.window)].local_last, 103.0)
        self.sticky(self.window, caught.exception)

    def test_initial_deadline_sample_cannot_be_forgotten_before_the_next_local_read(self):
        self.local_values = iter((102.0, 101.0))
        with self.assertRaisesRegex(ValueError, "WINDOW_LOCAL_EXPIRED_OR_BACKWARDS") as caught:
            self.window.deadline(5)
        self.assertEqual(D._WINDOWS[id(self.window)].local_last, 102.0)
        self.assertEqual(self.raw_calls, 0)
        self.sticky(self.window, caught.exception)

    def test_deadline_pre_sample_failure_is_sticky_before_any_later_argument_or_clock(self):
        error = FalseyFailure("SUPPLIED_INITIAL_LOCAL_FAILURE")
        def fail():
            raise error
        self.local_action = fail
        with self.assertRaises(FalseyFailure) as caught:
            self.window.deadline(5)
        self.assertIs(caught.exception, error)
        self.local_action = None
        self.assertEqual(self.raw_calls, 0)
        self.sticky(self.window, error)
        self.assertEqual(error.truthiness_calls, 0)

    def test_post_observation_conversion_failure_keeps_original_raw_highwater(self):
        error = FalseyFailure("SUPPLIED_CONVERSION_FAILURE")
        with patch.object(D.O.wire, "_directed_deadline", side_effect=error):
            with self.assertRaises(FalseyFailure) as caught:
                self.window.deadline(5)
        self.assertIs(caught.exception, error)
        self.assertEqual(self.window.last, START + 2)
        self.sticky(self.window, error)
        self.assertEqual(error.truthiness_calls, 0)

    def test_falsey_first_error_survives_a_secondary_binding_error_in_readonly_view(self):
        error = FalseyFailure("SUPPLIED_FIRST_CANCEL_FAILURE")
        def fail():
            raise error
        self.cancel_action = fail
        with self.assertRaises(FalseyFailure) as caught:
            self.window.now()
        self.assertIs(caught.exception, error)
        self.assertEqual(self.window.last, START + 1)
        self.window._bound = tuple(list(self.window._bound))
        with self.assertRaises(FalseyFailure) as secondary:
            _ = self.window.clock
        self.assertIs(secondary.exception, error)
        self.sticky(self.window, error)
        self.assertEqual(error.truthiness_calls, 0)

    def test_invalid_maximum_stage_and_limit_poison_only_the_original_use(self):
        for maximum in (True, 0, -1, 901, math.inf, math.nan, "1"):
            window = self.new_window()
            before = self.counters()
            with self.assertRaisesRegex(ValueError, "WINDOW_OPERATION_MAXIMUM") as caught:
                window.deadline(maximum)
            self.assertEqual(self.counters(), before)
            self.sticky(window, caught.exception)
        for changes in ({"final": 1}, {"stage": False}, {"stage": "new-time"}, {"limit": True}, {"limit": -1}):
            window = self.new_window()
            with self.assertRaises(ValueError) as caught:
                window.now(**changes)
            self.sticky(window, caught.exception)

    def test_raw_expiry_retains_observation_and_readonly_metadata_without_revival(self):
        work, final, clock = self.window.work, self.window.final, self.window.clock
        self.raw_values = iter((work,))
        with self.assertRaisesRegex(ValueError, "WINDOW_RAW_EXPIRED_OR_BINDING_CHANGED") as caught:
            self.window.now()
        self.assertEqual((self.window.work, self.window.final, self.window.last), (work, final, work))
        self.assertIs(self.window.clock, clock)
        self.sticky(self.window, caught.exception)

    def test_nested_limit_cannot_be_expanded_or_passed_at_equality(self):
        for limit, at in ((self.window.work + NS, self.window.work), (START + 20, START + 20)):
            window = self.new_window()
            self.raw_values = iter((at,))
            with self.assertRaisesRegex(ValueError, "WINDOW_RAW_EXPIRED_OR_BINDING_CHANGED") as caught:
                window.now(limit=limit)
            self.assertEqual(window.last, at)
            self.sticky(window, caught.exception)

    def test_all_named_stage_fences_are_the_original_finite_schedule(self):
        limits = D.schedule("gate", BASIS, START)
        for name in D.WINDOW_NAMES:
            window = self.new_window()
            self.raw_values = iter((limits[name],))
            with self.assertRaisesRegex(ValueError, "WINDOW_RAW_EXPIRED_OR_BINDING_CHANGED") as caught:
                window.now(stage=name)
            self.assertEqual(window.last, limits[name])
            self.sticky(window, caught.exception)

    def test_backwards_raw_never_replaces_the_previous_validated_highwater(self):
        self.raw_values = iter((START + 20, START + 19))
        with self.assertRaisesRegex(ValueError, "BOOTSTRAP_ORIGIN_INTEGER") as caught:
            self.window.now()
        self.assertEqual(self.window.last, START + 20)
        self.assertEqual(self.minimums, [START, START + 20])
        self.sticky(self.window, caught.exception)

    def test_final_local_backwards_keeps_the_last_raw_and_original_failure(self):
        self.local_values = iter((101.0, 102.0, 101.5))
        with self.assertRaisesRegex(ValueError, "WINDOW_FINAL_LOCAL") as caught:
            self.window.now()
        self.assertEqual(self.window.last, START + 2)
        self.sticky(self.window, caught.exception)

    def test_boot_change_and_boot_supplier_failure_do_not_relabel_original_boot(self):
        self.boot_action = lambda: "b" * 64
        with self.assertRaisesRegex(ValueError, "WINDOW_BOOT_CHANGED") as caught:
            self.window.now()
        self.assertEqual(self.window.last, START + 1)
        self.sticky(self.window, caught.exception)
        window = self.new_window()
        error = RuntimeError("SUPPLIED_BOOT_FAILURE")
        def fail():
            raise error
        self.boot_action = fail
        with self.assertRaises(RuntimeError) as caught:
            window.now()
        self.assertIs(caught.exception, error)
        self.assertEqual(window.last, START + 2)
        self.sticky(window, error)

    def test_swallowed_now_deadline_reentry_still_fails_the_outer_operation(self):
        for outer in ("now", "deadline"):
            for inner in ("now", "deadline"):
                window = self.new_window()
                nested = []
                def reenter():
                    try:
                        window.now() if inner == "now" else window.deadline(1)
                    except ValueError as error:
                        nested.append(error)
                self.cancel_action = reenter
                with self.assertRaisesRegex(ValueError, "WINDOW_REENTRY") as caught:
                    window.now() if outer == "now" else window.deadline(5)
                self.assertEqual(len(nested), 1)
                self.assertIs(caught.exception, nested[0])
                self.sticky(window, nested[0])
        self.cancel_action = None

    def test_deadline_reentry_guard_remains_active_through_the_conversion_helper(self):
        convert, nested = D.O.wire._directed_deadline, []
        def reenter(*args):
            try:
                self.window.now()
            except ValueError as error:
                nested.append(error)
            return convert(*args)
        with patch.object(D.O.wire, "_directed_deadline", side_effect=reenter):
            with self.assertRaisesRegex(ValueError, "WINDOW_REENTRY") as caught:
                self.window.deadline(5)
        self.assertEqual(len(nested), 1)
        self.assertIs(caught.exception, nested[0])
        self.sticky(self.window, nested[0])

    def test_equal_or_expanded_tuple_replacement_between_calls_cannot_be_adopted(self):
        for expanded in (False, True):
            window = self.new_window()
            window.now()
            old = window._bound
            replacement = list(old)
            if expanded:
                replacement[4] = tuple(value + 100 * NS for value in replacement[4])
            window._bound = tuple(replacement)
            self.assertIsNot(window._bound, old)
            before = self.counters()
            with self.assertRaisesRegex(ValueError, "WINDOW_ORIGINAL_BINDING") as caught:
                window.deadline(5)
            self.assertEqual(self.counters(), before)
            self.sticky(window, caught.exception)

    def test_reading_dictionary_replacement_between_calls_is_not_equal_history(self):
        self.window.now()
        object.__setattr__(self.first, "__dict__", dict(self.first.__dict__))
        before = self.counters()
        with self.assertRaisesRegex(ValueError, "RECIPIENT_HISTORY_CHANGED") as caught:
            self.window.now()
        self.assertEqual(self.counters(), before)
        self.sticky(self.window, caught.exception)

    def test_clock_dictionary_and_equal_nested_clock_replacement_are_not_original(self):
        self.window.now()
        object.__setattr__(self.clock, "__dict__", dict(self.clock.__dict__))
        with self.assertRaisesRegex(ValueError, "RECIPIENT_HISTORY_CHANGED") as caught:
            self.window.deadline(5)
        self.sticky(self.window, caught.exception)
        window = self.new_window()
        object.__setattr__(self.first, "clock", dataclasses.replace(self.clock))
        with self.assertRaisesRegex(ValueError, "RECIPIENT_HISTORY_CHANGED") as caught:
            window.now()
        self.sticky(window, caught.exception)

    def test_changed_clock_fields_and_reading_scalar_type_do_not_restore_a_window(self):
        for target, name, value in ((self.clock, "ticks_per_second", NS + 1),
                                    (self.first, "nanoseconds", True)):
            window = self.new_window()
            saved = getattr(target, name)
            object.__setattr__(target, name, value)
            with self.assertRaisesRegex(ValueError, "RECIPIENT_HISTORY_CHANGED") as caught:
                window.now()
            object.__setattr__(target, name, saved)
            self.sticky(window, caught.exception)

    def test_last_raw_supplier_mutation_is_refused_after_retaining_its_actual_return(self):
        def raw():
            if self.raw_calls == 2:
                object.__setattr__(self.clock, "__dict__", dict(self.clock.__dict__))
            return START + self.raw_calls
        self.raw_action = raw
        with self.assertRaisesRegex(ValueError, "RECIPIENT_HISTORY_CHANGED") as caught:
            self.window.now()
        self.assertEqual(D._WINDOWS[id(self.window)].last, START + 2)
        self.sticky(self.window, caught.exception)

    def test_last_local_supplier_cannot_replace_the_original_tuple(self):
        def local():
            if self.local_calls == 3:
                self.window._bound = tuple(list(self.window._bound))
            return LOCAL + self.local_calls / 10
        self.local_action = local
        with self.assertRaisesRegex(ValueError, "WINDOW_ORIGINAL_BINDING") as caught:
            self.window.now()
        self.assertEqual(D._WINDOWS[id(self.window)].last, START + 2)
        self.sticky(self.window, caught.exception)

    def test_mutating_supplied_limits_does_not_change_copied_original_schedule(self):
        limits = D.schedule("gate", BASIS, START)
        original = wire(limits)
        window = self.new_window(limits=limits)
        work = window.work
        limits["workEndNs"] += 100 * NS
        window.now()
        self.assertEqual(window.work, work)
        self.assertEqual(window._bound[3], original)

    def test_constructor_requires_exact_schedule_first_reading_and_registered_exact_handle(self):
        for change in ({"workEndNs": START + NS}, {"extra": "new-stage"}):
            limits = D.schedule("gate", BASIS, START)
            limits.update(change)
            with self.assertRaisesRegex(ValueError, "WINDOW_ARITHMETIC"):
                self.new_window(limits=limits)
        with self.assertRaisesRegex(ValueError, "WINDOW_ORIGINAL_START"):
            self.new_window(first=dataclasses.replace(self.first, nanoseconds=START + 1))
        class OtherWindow(D.Window):
            pass
        with self.assertRaisesRegex(ValueError, "WINDOW_NOT_NEW"):
            OtherWindow(self.first, LOCAL, BOOT, D.schedule("gate", BASIS, START), self.cancel)
        alien = object.__new__(D.Window)
        with self.assertRaisesRegex(ValueError, "WINDOW_ORIGINAL_HANDLE"):
            alien.now()
        self.assertEqual(self.counters(), (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
