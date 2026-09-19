#!/usr/bin/env python3
"""New file-leaf controls, NOT a producer, native process or hosted execution.

Actual ordinary-UID POSIX files use the unchanged strict file supplier. Supplied
producer records and the parent protocol are explicit models; old test methods
are not selected. Large budgets, adverse callbacks and Windows API answers are
models, not measured cohorts or native qualification. Fixtures stay on disk.
"""
from contextlib import ExitStack
from dataclasses import replace
import copy
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_bootstrap_collect_files as C

spec = importlib.util.spec_from_file_location("file_collection_producer_fixtures",
    ROOT / "scripts/tests/hosted-cache-bootstrap-producer-test.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
FILES, P = C.files, C.inventory.producer
EVIDENCE_ROOT = None


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("ascii")


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class ParentModel:
    """File-owner protocol only; no original native/RAW owner is instantiated."""
    def __init__(self, end):
        self.deadline = end
        self.resources, self.allocations, self.events, self.errors = [], [], [], []
        self.original, self.closed, self.unknown = None, False, False
        self.cancelled = lambda: None
        self.after_acquire = self.before_close = self.after_close = lambda _value: None

    def end(self):
        if self.closed or self.unknown or self.original is not None:
            raise RuntimeError("MODEL_PARENT_NOT_LIVE")
        return self.deadline

    def error(self, stage, error, *, unknown=False):
        if self.original is None:
            self.original = error
        self.unknown |= unknown or any("UNKNOWN" in note for note in getattr(error, "__notes__", ()))
        self.errors.append((stage, error, self.unknown))

    def register(self, label, value):
        self.allocations.append(value)  # Independent fixture-cleanup originals.
        self.resources.append({"label": label, "owner": value, "attempted": False, "closed": False})
        self.events.append(("acquire", value))

    def acquire(self, label, factory):
        self.end()
        try:
            value = factory()
        except BaseException as error:
            self.error(label, error, unknown=True)
            raise
        if any(row["owner"] is value for row in self.resources):
            raise RuntimeError("MODEL_DUPLICATE_OWNER")
        self.register(label, value)
        self.after_acquire(value)
        self.end()
        return value

    def close_one(self, value):
        row = next(row for row in self.resources if row["owner"] is value)
        if row["attempted"]:
            return
        row["attempted"] = True
        self.events.append(("close", value))
        try:
            self.before_close(value)
            value.close()
            row["closed"] = True
        except BaseException as error:
            self.error(row["label"], error, unknown=True)
        self.after_close(value)


class FileLeafControls(unittest.TestCase):
    def setUp(self):
        self.assertEqual(os.name, "posix", "Select these actual POSIX controls only on POSIX")
        self.assertNotEqual(os.getuid(), 0, "The real private reader requires an ordinary UID")
        self.stack = ExitStack()
        self.fixture = F.ProducerModels()
        self.fixture.setUp()  # Pure synthetic record SETUP, no old tests or producer.
        self.local = time.monotonic()
        self.started = self.local
        self.stack.enter_context(patch.object(C.time, "monotonic", side_effect=lambda: self.local))
        self.owner = ParentModel(self.local + 600)
        self.addCleanup(self.finish_fixtures)
        self.base = Path(tempfile.mkdtemp(prefix="collection-file-control-", dir=EVIDENCE_ROOT))
        self.live = self.mkdir("checkout")
        state = self.mkdir("initializer/state")
        self.target = self.mkdir("initializer/configuration-custody/retained")
        self.fixture.context.update(root=str(self.live), gradleHome=str(state / "gradle-home"))
        self.canonical_raw = encoded(self.fixture.context)
        self.request = P.make_request(self.fixture.admitted_raw, self.canonical_raw,
                                     invocation="b" * 32, ancestor_invocations=["c" * 32])
        self.request_raw = P.encoded(self.request)
        self.source = self.mkdir(str(Path(self.request["evidenceDirectory"]).relative_to(self.base)))
        self.start = copy.deepcopy(self.fixture.start)
        for key in ("cwd", "wrapper", "gradleHome", "evidenceDirectory"):
            self.start[key] = self.request[key]
        self.receipt = copy.deepcopy(self.fixture.receipt)
        for key in self.start:
            if key in ("cwd", "wrapper", "gradleHome", "evidenceDirectory"):
                self.receipt[key] = self.start[key]
        self.receipt.update(executedArgv=self.request["executedArgv"], stopArgv=self.request["stopArgv"])
        self.receipt["ownership"]["launches"] = [self.fixture.launch(self.request["executedArgv"], 101),
                                                  self.fixture.launch(self.request["stopArgv"], 102)]
        self.payload = {"product.stdout.log": b"configuration only\n", "product.stderr.log": b"",
                        "stop.stdout.log": b"same home stop\n", "stop.stderr.log": b""}
        self.records = []
        self.save_records()

    def finish_fixtures(self):
        self.stack.close()
        self.fixture.doCleanups()
        # Fixture-only cleanup of independently captured tiny POSIX handles.
        # It never changes the leaf's FAILED/UNKNOWN outcome or restores an owner.
        for value in reversed(self.owner.allocations):
            if type(value) in (FILES.PosixFile, FILES.PosixPrivateDirectory) and not value.closed:
                try:
                    value.close()
                except BaseException:
                    pass  # Strict close still releases pins; harness checks the FD roster.

    def mkdir(self, relative):
        path = self.base
        for part in Path(relative).parts:
            path /= part
            if not path.exists():
                path.mkdir(mode=0o700)
        return path

    def write(self, path, raw):
        self.mkdir(str(path.parent.relative_to(self.base)))
        path.write_bytes(raw)
        path.chmod(0o600)

    def add_report(self, name="build/reports/problems/problem.html", raw=b"report", *, changed=True):
        record = {"source": name, "sha256": P.digest(raw), "bytes": len(raw),
                  "classification": "changed-since-admission" if changed else "preexisting-unchanged"}
        if changed:
            record["retained"] = "reports/" + name
            self.payload[record["retained"]] = raw
        self.records.append(record)
        self.records.sort(key=lambda row: row["source"])

    def save_records(self):
        self.receipt["reports"] = copy.deepcopy(self.records)
        self.start_raw = encoded(self.start)
        self.receipt_raw = encoded(self.receipt)
        self.manifest_raw = encoded({"schema": 1, "records": self.records,
            "limitation": "Changed bytes are not proof of test execution; use the unchanged product assessor."})
        self.payload.update({"start.json": self.start_raw, "receipt.json": self.receipt_raw,
                             "report-manifest.json": self.manifest_raw})
        for name, raw in self.payload.items():
            self.write(self.source / name, raw)

    def originals(self):
        identity = lambda path: (path.stat().st_dev, path.stat().st_ino)
        bindings = {name: FILES._info_binding(FILES._info((self.source / name).stat()))
                    for name in ("start.json", "receipt.json", "report-manifest.json")}
        return C.FileOriginals(self.request_raw, self.fixture.admitted_raw, self.canonical_raw, self.start_raw,
            self.receipt_raw, self.manifest_raw, 0, identity(self.source), identity(self.target), FILES.encoded(bindings))

    def run_leaf(self, originals=None):
        return C.collect_inventory(self.owner, self.originals() if originals is None else originals)

    def refuse(self, reason, originals=None, *, unknown=None):
        with self.assertRaisesRegex(BaseException, reason) as caught:
            self.run_leaf(originals)
        error = caught.exception
        result = error.bootstrap_collection_result
        self.assertIs(result["completed"], False)
        self.assertIs(result["nextPhaseAuthority"], False)
        self.assertIs(result["exportSaveAuthority"], False)
        self.assertIs(error, self.owner.original)
        if unknown is not None:
            self.assertEqual(result["collectionState"], "UNKNOWN" if unknown else "FAILED")
            self.assertEqual(result["leafHandleClose"], "UNKNOWN" if unknown else "KNOWN")
        return error

    def test_copies_only_seven_original_files_and_changed_retained_reports(self):
        self.add_report(raw=b"retained report")
        self.add_report("library/p2p-core/build/test-results/test/TEST-A.xml", b"", changed=True)
        self.add_report("samples/cli/build/reports/old.xml", b"unchanged", changed=False)
        self.save_records()
        self.write(self.live / "build/reports/problems/problem.html", b"NOT the retained bytes")
        result = self.run_leaf()
        value = json.loads(result.raw)
        self.assertEqual(value["collectionState"], "COPIED_AND_READ_BACK")
        self.assertIs(value["completed"], True)
        self.assertEqual(value["leafHandleClose"], "KNOWN")
        self.assertFalse(self.owner.closed)
        self.assertIsNone(self.owner.original)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in self.owner.resources))
        self.assertEqual({p.relative_to(self.target).as_posix() for p in self.target.rglob("*") if p.is_file()},
                         set(self.payload))
        self.assertEqual({row["path"]: (row["bytes"], row["sha256"]) for row in value["files"]},
                         {name: (len(raw), P.digest(raw)) for name, raw in self.payload.items()})
        for name, raw in self.payload.items():
            self.assertEqual((self.target / name).read_bytes(), raw)
            self.assertEqual((self.source / name).read_bytes(), raw)
        expected_members = set(self.payload)
        for name in self.payload:
            expected_members.update(str(path) for path in Path(name).parents if str(path) != ".")
        metadata_bytes = sum(len(self.payload[name]) for name in ("start.json", "receipt.json", "report-manifest.json"))
        total = sum(map(len, self.payload.values()))
        self.assertEqual(value["counts"], {"sourceReadBytes": 2 * total + metadata_bytes,
            "destinationReadBytes": total, "outputBytesRequested": total, "outputBytesAcknowledged": total,
            "sourceMembers": len(expected_members), "destinationMembers": len(expected_members),
            "sourceFinalMembers": len(expected_members), "destinationFinalMembers": len(expected_members)})
        self.assertEqual(value["inputProvenance"], "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL")
        self.assertEqual(value["enclosingOwnerRetirement"], "NOT_OBSERVED_HERE")
        self.assertEqual(value["readBoundary"], "POSIX_POSITIVE_READ_EMPTY_AND_SAME_DESCRIPTOR_VERIFY")
        for name, expected in (("noLoaderObservation", "NOT_OBSERVED"), ("dependencyPopulation", "NOT_ATTESTED"),
                ("budgetAcceptance", "NOT_ADMITTED"), ("testAcceptance", "NOT_PERFORMED"),
                ("nextPhaseAuthority", False), ("exportSaveAuthority", False)):
            self.assertEqual(value[name], expected)
        self.assertEqual(json.loads(result.inventory_raw)["collectionState"], "NOT_PERFORMED")
        self.assertEqual(value["localWindow"]["end"] - result.local_started, 120)

    def test_empty_logs_and_no_reports_still_use_positive_exhaustion_reads(self):
        for name in ("product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log"):
            self.payload[name] = b""
        self.save_records()
        observed, original = [], FILES.PosixFile.read
        def read(reader, size):
            observed.append((reader.path, size))
            return original(reader, size)
        with patch.object(FILES.PosixFile, "read", read):
            value = json.loads(self.run_leaf().raw)
        self.assertEqual(len(value["files"]), 7)
        self.assertTrue(all(type(size) is int and 0 < size <= 65536 for _path, size in observed))
        for name in ("product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log"):
            self.assertEqual([size for path, size in observed if path == self.source / name], [1, 1])
            self.assertEqual([size for path, size in observed if path == self.target / name], [1])

    def test_streams_across_64k_boundary_and_accepts_nonempty_fragments(self):
        self.payload["product.stdout.log"] = b"x" * 65537
        self.save_records()
        calls, original = [], FILES.PosixFile.read
        def read(reader, size):
            calls.append(size)
            return original(reader, min(size, 8191))
        with patch.object(FILES.PosixFile, "read", read):
            self.run_leaf()
        self.assertIn(65536, calls)
        self.assertTrue(all(0 < size <= 65536 for size in calls))
        self.assertEqual((self.target / "product.stdout.log").read_bytes(), b"x" * 65537)

    def test_all_metadata_validated_before_any_copy_output(self):
        path = self.source / "report-manifest.json"
        self.write(path, b"!" + path.read_bytes()[1:])
        # Even a supplied binding updated to the changed file cannot alter raw originals.
        self.refuse("METADATA_BYTES_CHANGED", unknown=False)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_same_bytes_replacement_is_not_original_metadata(self):
        original = self.originals()
        path = self.source / "start.json"
        path.rename(self.base / "original-start.json")
        self.write(path, self.start_raw)
        self.refuse("ORIGINAL_FILE_REPLACED", original, unknown=False)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_same_bytes_replacement_is_not_original_evidence_directory(self):
        original = self.originals()
        self.source.rename(self.source.with_name("saved-original"))
        self.source.mkdir(mode=0o700)
        for name, raw in self.payload.items():
            self.write(self.source / name, raw)
        self.refuse("ORIGINAL_DIRECTORY_REPLACED", original, unknown=False)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_nonempty_target_refuses_without_overwrite_and_counts_observed_entry(self):
        self.write(self.target / "owner-original", b"keep")
        error = self.refuse("TARGET_NOT_EMPTY", unknown=False)
        self.assertEqual(error.bootstrap_collection_result["counts"]["destinationMembers"], 1)
        self.assertEqual((self.target / "owner-original").read_bytes(), b"keep")
        self.assertEqual(len(list(self.target.iterdir())), 1)

    def test_missing_log_is_not_inferred_from_success_receipt(self):
        (self.source / "stop.stderr.log").rename(self.base / "original-stop.log")
        self.refuse("UNLISTED_OR_MISSING_MEMBER", unknown=False)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_unlisted_source_directory_is_refused_without_following_it(self):
        (self.source / "unexpected").mkdir(mode=0o700)
        error = self.refuse("UNLISTED_OR_MISSING_MEMBER", unknown=False)
        self.assertEqual(error.bootstrap_collection_result["counts"]["sourceMembers"], 8)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_symlink_log_is_refused_and_original_target_is_preserved(self):
        path = self.source / "product.stdout.log"
        path.rename(self.base / "original-product.log")
        path.symlink_to(self.base / "original-product.log")
        self.refuse("symbolic links|SEED_", unknown=True)
        self.assertTrue(path.is_symlink())
        self.assertEqual((self.base / "original-product.log").read_bytes(), b"configuration only\n")

    def test_fifo_log_refuses_without_waiting_for_a_writer(self):
        path = self.source / "product.stdout.log"
        path.rename(self.base / "original-product.log")
        os.mkfifo(path, 0o600)
        self.refuse("SEED_DESCRIPTOR_IDENTITY_OR_KIND", unknown=True)

    def test_hardlinked_logs_are_not_independent_original_files(self):
        path = self.source / "product.stdout.log"
        path.rename(self.base / "original-product.log")
        os.link(self.source / "product.stderr.log", path)
        self.refuse("SEED_DESCRIPTOR_IDENTITY_OR_KIND", unknown=True)

    def test_broad_retained_report_parent_is_not_silently_chmodded(self):
        self.add_report()
        self.save_records()
        broad = self.source / "reports/build"
        broad.chmod(0o755)
        self.refuse("SEED_PRIVATE_MODE", unknown=True)
        self.assertEqual(broad.stat().st_mode & 0o777, 0o755)

    def test_declared_report_hash_mismatch_preserves_failure_and_partial_files(self):
        self.add_report()
        self.records[0]["sha256"] = P.digest(b"other!")
        self.save_records()
        self.refuse("HASH_CHANGED", unknown=False)
        self.assertTrue((self.target / "receipt.json").is_file())
        self.assertFalse((self.target / "reports/build/reports/problems/problem.html").exists())

    def test_source_growth_at_rewind_cannot_be_copied(self):
        original = FILES.PosixFile.seek
        def seek(reader, offset, whence=0):
            if reader.path == self.source / "product.stdout.log":
                with reader.path.open("ab") as stream:
                    stream.write(b"growth")
            return original(reader, offset, whence)
        with patch.object(FILES.PosixFile, "seek", seek):
            self.refuse("SEED_IMMUTABLE_INPUT_CHANGED", unknown=True)
        self.assertFalse((self.target / "product.stdout.log").exists())

    def test_destination_replacement_before_readback_refuses_same_bytes(self):
        def after_close(value):
            if type(value) is FILES.PosixFile and value.writable and value.path == self.target / "product.stdout.log":
                value.path.rename(self.base / "original-copied.log")
                self.write(value.path, self.payload["product.stdout.log"])
        self.owner.after_close = after_close
        self.refuse("ORIGINAL_FILE_REPLACED", unknown=False)
        self.assertTrue((self.base / "original-copied.log").is_file())

    def test_late_source_membership_change_cannot_pass_final_recheck(self):
        opened = 0
        def after_acquire(value):
            nonlocal opened
            if type(value) is FILES.PosixFile and value.path == self.source / "product.stderr.log":
                opened += 1
                if opened == 2:  # New final-check reader, after copy and readback.
                    self.write(self.source / "late-unlisted", b"late")
        self.owner.after_acquire = after_acquire
        self.refuse("FINAL_DIRECTORY_CHANGED", unknown=False)
        self.assertEqual(opened, 2)

    def test_nonempty_exhaustion_read_is_not_eof(self):
        original = FILES.PosixFile.read
        def read(reader, size):
            part = original(reader, size)
            return b"!" if not part and reader.path == self.source / "start.json" else part
        with patch.object(FILES.PosixFile, "read", read):
            self.refuse("SIZE_OR_STAMP_CHANGED", unknown=False)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_zero_progress_read_cannot_create_output(self):
        with patch.object(FILES.PosixFile, "read", return_value=b""):
            self.refuse("SHORT_OR_EXCESS_READ", unknown=False)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_short_write_fails_with_requested_and_acknowledged_counts_separate(self):
        original = FILES.PosixFile.write
        def write(writer, raw):
            return original(writer, raw[:1])
        with patch.object(FILES.PosixFile, "write", write):
            error = self.refuse("SHORT_WRITE", unknown=False)
        counts = error.bootstrap_collection_result["counts"]
        self.assertGreater(counts["outputBytesRequested"], 1)
        self.assertEqual(counts["outputBytesAcknowledged"], 1)
        self.assertEqual((self.target / "product.stdout.log").stat().st_size, 1)

    def test_falsey_sync_failure_remains_original_after_known_cleanup(self):
        failure = FalseyFailure("SYNC_MODEL_FAILURE")
        with patch.object(FILES.PosixFile, "sync", side_effect=failure):
            error = self.refuse("SYNC_MODEL_FAILURE", unknown=False)
        self.assertIs(error, failure)
        self.assertTrue(error.bootstrap_collection_resources)

    def test_cancellation_after_metadata_preflight_precedes_output(self):
        failure = FalseyFailure("CANCEL_MODEL_FAILURE")
        def cancelled():
            if len(self.owner.allocations) >= 5 and all(value.closed for value in self.owner.allocations[2:5]):
                raise failure
        self.owner.cancelled = cancelled
        self.assertIs(self.refuse("CANCEL_MODEL_FAILURE", unknown=False), failure)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_local_expiry_after_read_stops_new_work_but_attempts_known_close(self):
        original = FILES.PosixFile.read
        def read(reader, size):
            part = original(reader, size)
            self.local = self.started + 120
            return part
        with patch.object(FILES.PosixFile, "read", read):
            self.refuse("LOCAL_EXPIRED", unknown=True)
        self.assertEqual(len(self.owner.allocations), 3)
        self.assertEqual(len([event for event in self.owner.events if event[0] == "close"]), 1)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_close_uncertainty_stops_other_closes_and_keeps_original_references(self):
        failure = FalseyFailure("CLOSE_MODEL_UNKNOWN")
        def before_close(_value):
            raise failure
        self.owner.before_close = before_close
        error = self.refuse("CLOSE_MODEL_UNKNOWN", unknown=True)
        self.assertIs(error, failure)
        self.assertEqual(len(error.bootstrap_collection_resources), 3)
        self.assertEqual(len([event for event in self.owner.events if event[0] == "close"]), 1)
        self.assertTrue(all(not value.closed for value in self.owner.allocations))

    def test_post_factory_registration_loss_is_unknown_without_fallback_close(self):
        self.owner.after_acquire = lambda _value: self.owner.resources.pop()
        error = self.refuse("UNREGISTERED_RETURN", unknown=True)
        self.assertEqual(len(error.bootstrap_collection_resources), 1)
        self.assertIs(error.bootstrap_collection_resources[0].value, self.owner.allocations[0])
        self.assertFalse(self.owner.allocations[0].closed)
        self.assertFalse(any(event[0] == "close" for event in self.owner.events))

    def test_post_factory_registration_loss_preserves_actual_first_acquire_error(self):
        failure = FalseyFailure("POST_FACTORY_ORIGINAL_FAILURE")
        def after_acquire(_value):
            self.owner.resources.pop()
            raise failure
        self.owner.after_acquire = after_acquire
        error = self.refuse("POST_FACTORY_ORIGINAL_FAILURE", unknown=True)
        self.assertIs(error, failure)
        self.assertIs(self.owner.errors[0][1], failure)
        self.assertEqual(self.owner.errors[0][0], "bootstrap-collection-acquire")
        self.assertIn("UNREGISTERED_RETURN", str(self.owner.errors[1][1]))
        self.assertEqual(len(error.bootstrap_collection_resources), 1)
        pin = error.bootstrap_collection_resources[0]
        self.assertIs(pin.value, self.owner.allocations[0])
        self.assertIsNone(pin.row)
        self.assertFalse(pin.attempted)
        self.assertFalse(pin.closed)
        self.assertFalse(self.owner.allocations[0].closed)
        self.assertFalse(any(event[0] == "close" for event in self.owner.events))

    def test_post_factory_deadline_failure_keeps_and_closes_returned_root(self):
        self.owner.after_acquire = lambda _value: setattr(self.owner, "deadline", self.local)
        self.refuse("CALLER_EXPIRED", unknown=False)
        self.assertEqual(len(self.owner.allocations), 1)
        self.assertTrue(self.owner.allocations[0].closed)

    def test_parent_list_replacement_cannot_adopt_a_new_cleanup_owner(self):
        self.owner.after_acquire = lambda _value: setattr(self.owner, "resources", [])
        error = self.refuse("UNREGISTERED_RETURN|PARENT_NOT_LIVE", unknown=True)
        self.assertEqual(len(error.bootstrap_collection_resources), 1)
        self.assertFalse(self.owner.allocations[0].closed)
        self.assertFalse(any(event[0] == "close" for event in self.owner.events))

    def test_parent_cannot_invoke_a_resource_factory_twice(self):
        def twice(label, factory):
            value = factory()
            self.owner.register(label, value)
            factory()
            return value
        self.owner.acquire = twice
        self.refuse("FACTORY_REPEATED", unknown=False)
        self.assertEqual(len(self.owner.allocations), 1)
        self.assertTrue(self.owner.allocations[0].closed)

    def test_borrowed_existing_parent_resource_is_never_closed_by_leaf(self):
        borrowed = SimpleNamespace(close=lambda: self.fail("borrowed close"))
        self.owner.resources.append({"label": "existing", "owner": borrowed, "attempted": False, "closed": False})
        self.owner.acquire = lambda _label, _factory: borrowed
        self.refuse("BORROWED_OR_CHANGED_RETURN", unknown=False)
        self.assertEqual(self.owner.allocations, [])
        self.assertFalse(self.owner.resources[0]["attempted"])

    def test_earlier_leaf_resource_borrow_is_known_refusal_not_a_new_obligation(self):
        original, captured = FILES.private_root, []
        def private_root(path):
            if not captured:
                captured.append(original(path))
            return captured[0]
        with patch.object(FILES, "private_root", private_root):
            error = self.refuse("MODEL_DUPLICATE_OWNER", unknown=False)
        self.assertEqual(len(self.owner.allocations), 1)
        self.assertEqual(len(error.bootstrap_collection_resources), 1)
        self.assertTrue(captured[0].closed)
        self.assertEqual(len([event for event in self.owner.events if event[0] == "close"]), 1)

    def test_one_primary_failure_does_not_fill_parent_error_cap_during_known_closes(self):
        class TinyResource:
            closed = False
            def close(self):
                self.closed = True
        leaf = C._Copy(self.owner, C._Inputs(self.originals()), self.local)
        resources = [leaf.acquire("modeled-close", TinyResource) for _ in range(70)]
        original_error = self.owner.error
        def bounded_error(stage, error, *, unknown=False):
            if len(self.owner.errors) < 64:
                original_error(stage, error, unknown=unknown)
            else:
                self.owner.unknown = True
        # Same cap as the accepted parent Owner; resources here are inert models.
        leaf.error_original = bounded_error
        failure = FalseyFailure("ONE_ORIGINAL_FAILURE")
        leaf.error("body", failure)
        with self.assertRaises(FalseyFailure) as caught:
            leaf.close()
        self.assertIs(caught.exception, failure)
        self.assertFalse(self.owner.unknown)
        self.assertTrue(all(resource.closed for resource in resources))
        self.assertEqual(len(self.owner.errors), 1)

    def clock_cleanup_models(self, count):
        class KnownDirectoryModel:
            """No descriptor or own file deadline; just an original close duty."""
            def __init__(self):
                self.closed, self.close_calls, self.failure = False, 0, None
            def close(self):
                self.close_calls += 1
                if self.failure is not None:
                    raise self.failure
                self.closed = True
        original_error = self.owner.error
        def bounded_error(stage, error, *, unknown=False):
            if len(self.owner.errors) < 64:
                original_error(stage, error, unknown=unknown)
            else:
                self.owner.unknown = True
        self.owner.error = bounded_error
        leaf = C._Copy(self.owner, C._Inputs(self.originals()), self.local)
        return leaf, [leaf.acquire("modeled-directory", KnownDirectoryModel) for _ in range(count)]

    def expire_leaf(self, leaf):
        self.local = self.started + 120
        with self.assertRaisesRegex(C.CollectionFilesError, "LOCAL_EXPIRED") as caught:
            leaf.check()
        leaf.error("body", caught.exception)
        return caught.exception

    def test_preclose_error_cap_unknown_prevents_any_original_close(self):
        leaf, resources = self.clock_cleanup_models(2)
        primary = FalseyFailure("EARLIER_PARENT_ORIGINAL")
        self.owner.error("earlier-parent", primary)
        for _ in range(63):
            self.owner.error("retained-parent-error", RuntimeError("retained"))
        failure = FalseyFailure("PRECLOSE_ORIGINAL_CLOCK_FAILURE")
        with patch.object(C.time, "monotonic", side_effect=failure), self.assertRaises(FalseyFailure) as caught:
            leaf.close()
        self.assertIs(caught.exception, primary)
        self.assertIs(leaf.first, primary)
        self.assertIs(self.owner.original, primary)
        self.assertTrue(leaf.unknown)
        self.assertTrue(self.owner.unknown)
        self.assertEqual(len(self.owner.errors), 64)
        self.assertEqual([value.close_calls for value in resources], [0, 0])
        self.assertTrue(all(not pin.attempted and not pin.closed for pin in leaf.resources))
        self.assertEqual([pin.value for pin in leaf.resources], resources)
        self.assertFalse(any(event[0] == "close" for event in self.owner.events))
        self.assertFalse(self.owner.closed)

    def test_preclose_error_recorder_failure_prevents_any_original_close(self):
        leaf, resources = self.clock_cleanup_models(2)
        failure = FalseyFailure("PRECLOSE_ORIGINAL_CLOCK_FAILURE")
        secondary = RuntimeError("ERROR_RECORDER_FAILURE")
        def error_record(_stage, _error, *, unknown=False):
            raise secondary
        leaf.error_original = error_record
        with patch.object(C.time, "monotonic", side_effect=failure), self.assertRaises(FalseyFailure) as caught:
            leaf.close()
        self.assertIs(caught.exception, failure)
        self.assertIs(leaf.first, failure)
        self.assertIsNone(self.owner.original)
        self.assertIn("Seed owner-error-record retirement UNKNOWN: RuntimeError", getattr(failure, "__notes__", ()))
        self.assertTrue(leaf.unknown)
        self.assertFalse(self.owner.unknown)  # No recorder callback succeeded.
        self.assertEqual(self.owner.errors, [])
        self.assertEqual([value.close_calls for value in resources], [0, 0])
        self.assertTrue(all(not pin.attempted and not pin.closed for pin in leaf.resources))
        self.assertEqual([pin.value for pin in leaf.resources], resources)
        self.assertFalse(any(event[0] == "close" for event in self.owner.events))
        self.assertFalse(self.owner.closed)

    def test_known_local_expiry_is_one_event_but_every_original_close_is_sampled(self):
        leaf, resources = self.clock_cleanup_models(70)
        with patch.object(C.time, "monotonic", side_effect=lambda: self.local) as clock:
            primary = self.expire_leaf(leaf)
            with self.assertRaises(C.CollectionFilesError) as caught:
                leaf.close()
        self.assertIs(caught.exception, primary)
        self.assertIs(leaf.first, primary)
        self.assertIs(self.owner.original, primary)
        self.assertEqual(clock.call_count, 141)  # One expiry + two observations per known close.
        self.assertTrue(all(value.closed and value.close_calls == 1 for value in resources))
        self.assertEqual([value for event, value in self.owner.events if event == "close"], list(reversed(resources)))
        self.assertEqual(len(self.owner.errors), 1)
        self.assertFalse(leaf.unknown)
        self.assertFalse(self.owner.unknown)
        self.assertFalse(self.owner.closed)
        self.assertEqual((leaf.began, leaf.end_local, leaf.last), (self.started, self.started + 120, self.local))
        with self.assertRaises(C.CollectionFilesError):
            leaf.check()

    def test_matching_supplier_error_text_does_not_preconsume_leaf_expiry(self):
        leaf, resources = self.clock_cleanup_models(2)
        supplied = C.CollectionFilesError("BOOTSTRAP_COLLECT_LOCAL_EXPIRED")
        leaf.error("supplier", supplied)
        self.local = self.started + 120
        with self.assertRaises(C.CollectionFilesError) as caught:
            leaf.close()
        self.assertIs(caught.exception, supplied)
        self.assertEqual(len(self.owner.errors), 2)
        self.assertEqual(str(self.owner.errors[1][1]), str(supplied))
        self.assertIsNot(self.owner.errors[1][1], supplied)
        self.assertTrue(all(value.closed and value.close_calls == 1 for value in resources))
        self.assertFalse(self.owner.unknown)

    def test_clock_rethrowing_previous_leaf_expiry_is_not_a_new_leaf_observation(self):
        leaf, resources = self.clock_cleanup_models(1)
        primary = self.expire_leaf(leaf)
        with patch.object(C.time, "monotonic", side_effect=primary), self.assertRaises(C.CollectionFilesError) as caught:
            leaf.close()
        self.assertIs(caught.exception, primary)
        self.assertEqual(len(self.owner.errors), 3)  # Body plus two genuine supplier failures.
        self.assertTrue(all(row[1] is primary for row in self.owner.errors))
        self.assertTrue(resources[0].closed)
        self.assertEqual(resources[0].close_calls, 1)

    def test_backward_clock_after_recorded_expiry_is_not_suppressed(self):
        leaf, resources = self.clock_cleanup_models(1)
        primary = self.expire_leaf(leaf)
        self.local = self.started + 119
        with self.assertRaises(C.CollectionFilesError) as caught:
            leaf.close()
        self.assertIs(caught.exception, primary)
        self.assertEqual(len(self.owner.errors), 3)
        self.assertTrue(all("LOCAL_BACKWARDS" in str(row[1]) for row in self.owner.errors[1:]))
        self.assertEqual(leaf.last, self.started + 120)
        self.assertTrue(resources[0].closed)
        self.assertEqual(resources[0].close_calls, 1)

    def test_actual_close_error_matching_expiry_text_still_becomes_unknown(self):
        leaf, resources = self.clock_cleanup_models(3)
        primary = self.expire_leaf(leaf)
        failure = C.CollectionFilesError("BOOTSTRAP_COLLECT_LOCAL_EXPIRED")
        resources[-1].failure = failure
        with self.assertRaises(C.CollectionFilesError) as caught:
            leaf.close()
        self.assertIs(caught.exception, primary)
        self.assertTrue(any(row[1] is failure for row in self.owner.errors))
        self.assertTrue(leaf.unknown)
        self.assertTrue(self.owner.unknown)
        self.assertEqual([value.close_calls for value in resources], [0, 0, 1])
        self.assertFalse(any(value.closed for value in resources))
        self.assertFalse(self.owner.closed)

    def test_supplied_envelope_and_metadata_binding_errors_precede_callbacks(self):
        original = self.originals()
        bindings = json.loads(original.metadata_bindings_raw)
        cases = [replace(original, original_exit_code=False), replace(original, evidence_identity=list(original.evidence_identity)),
                 replace(original, retained_identity=original.evidence_identity),
                 replace(original, evidence_identity=(original.evidence_identity[0], "a" * 32)),
                 replace(original, metadata_bindings_raw=FILES.encoded({**bindings, "extra": bindings["start.json"]})),
                 replace(original, metadata_bindings_raw=FILES.encoded({**bindings, "start.json": {
                     "identity": [True, 2], "stampSha256": "a" * 64}})), replace(original, request_raw=bytearray(original.request_raw))]
        for changed in cases:
            with self.subTest(changed=type(changed.request_raw).__name__), self.assertRaises((ValueError, RuntimeError)):
                C.collect_inventory(self.owner, changed)
        self.assertEqual(self.owner.events, [])
        self.assertIsNone(self.owner.original)

    def test_inventory_name_grammar_cannot_expand_native_basename_admission(self):
        for name in (".hidden", "space name.xml", "TEST-A$Nested.xml", "x" * 129):
            record = {"source": "build/reports/" + name, "retained": "reports/build/reports/" + name,
                      "sha256": P.digest(b""), "bytes": 0, "classification": "changed-since-admission"}
            receipt = {**self.receipt, "reports": [record]}
            original = replace(self.originals(), receipt_raw=encoded(receipt), manifest_raw=encoded({"schema": 1,
                "records": [record], "limitation": C.inventory.LIMITATION}))
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "SEED_BASENAME"):
                C.collect_inventory(self.owner, original)
        self.assertEqual(self.owner.events, [])

    def test_alias_identity_is_refused_across_source_and_destination(self):
        inputs = C._Inputs(self.originals())
        leaf = C._Copy(self.owner, inputs, self.local)
        info = FILES._info((self.source / "start.json").stat())
        leaf.info(info, directory=False, side="source", path="start.json")
        with self.assertRaisesRegex(C.CollectionFilesError, "FILE_ALIAS"):
            leaf.info(info, directory=False, side="destination", path="start.json")

    def test_local_and_caller_windows_cannot_renew_or_accept_equality(self):
        leaf = C._Copy(self.owner, C._Inputs(self.originals()), self.local)
        self.owner.deadline = self.local + 1
        self.assertEqual(leaf.check(), self.local + 1)
        self.owner.deadline = self.local + 600
        self.local += 1
        with self.assertRaisesRegex(C.CollectionFilesError, "CALLER_EXPIRED"):
            leaf.check()
        self.local -= 1
        with self.assertRaisesRegex(C.CollectionFilesError, "LOCAL_BACKWARDS"):
            leaf.check()

    def test_cancellation_callback_time_is_charged_before_acquisition(self):
        self.owner.deadline = self.local + 1
        self.owner.cancelled = lambda: setattr(self, "local", self.local + 1)
        self.refuse("CALLER_EXPIRED", unknown=False)
        self.assertEqual(self.owner.allocations, [])

    def test_invalid_local_clocks_refuse_without_rounding_or_type_coercion(self):
        for value in (True, -1, float("inf"), float("nan"), "1", 1 << 10000):
            with self.subTest(kind=type(value).__name__), self.assertRaisesRegex(C.CollectionFilesError, "LOCAL_CLOCK"):
                C._local(value)

    def test_exact_native_member_depth_resource_and_byte_bounds_are_models(self):
        self.assertEqual((C.BLOCK, C.SECONDS, C.MEMBERS, C.DEPTH, C.RESOURCES), (65536, 120, 10000, 64, 4096))
        self.assertEqual(C.MAX_BYTES, 3 * 4194304 + 4 * 67108864 + 536870912)
        inputs = C._Inputs(self.originals())
        leaf = C._Copy(self.owner, inputs, self.local)
        for kind, limit in (("sourceReadBytes", 2 * C.MAX_BYTES + 3 * 4194304),
                            ("destinationReadBytes", C.MAX_BYTES), ("outputBytesRequested", C.MAX_BYTES),
                            ("outputBytesAcknowledged", C.MAX_BYTES)):
            leaf.charge(kind, limit)
            with self.assertRaisesRegex(C.CollectionFilesError, "BYTE_LIMIT"):
                leaf.charge(kind, 1)
        # Two tiny declared nodes test the count fence; no10,000-file tree is allocated.
        inputs.members = 9999
        with self.assertRaisesRegex(C.CollectionFilesError, "NATIVE_MEMBERS"):
            inputs.insert("new-dir/child", C._Member(0))
        depth = 64 - max(len(inputs.source.parts), len(inputs.target.parts))
        inputs.members, inputs.tree = 0, {}
        inputs.insert("/".join(["a"] * depth), C._Member(0))
        with self.assertRaisesRegex(C.CollectionFilesError, "NATIVE_DEPTH"):
            inputs.insert("/".join(["b"] * (depth + 1)), C._Member(0))
        self.owner.resources = [{"label": "model", "owner": object(), "attempted": False, "closed": False}
                                for _ in range(4096)]
        leaf = C._Copy(self.owner, C._Inputs(self.originals()), self.local)
        with self.assertRaisesRegex(C.CollectionFilesError, "RESOURCE_LIMIT"):
            leaf.acquire("never", lambda: self.fail("must not allocate"))
        self.assertEqual(self.owner.allocations, [])

    def test_windows_exhaustion_is_adapter_boundary_not_kernel_eof(self):
        info = FILES.windows.FileInfo((1, "a" * 32), False, 6, 1, 0, 1, 1, 1)
        class PinModel:
            path, handle = r"D:\model\log", 1
            def __init__(self):
                self.info, self.current, self.released = info, info, False
            def observe(self):
                return self.current
            def release(self):
                self.released = True
        class ApiModel:
            def __init__(self):
                self.position, self.read_calls = 0, []
            def seek(self, handle, offset, whence):
                assert handle == 1
                if whence == 0:
                    self.position = offset
                else:
                    assert whence == 1 and offset == 0
                return self.position
            def read(self, handle, count):
                assert handle == 1 and count > 0
                self.read_calls.append(count)
                part = b"abcdef"[self.position:self.position + count]
                self.position += len(part)
                return part
        api, pin = ApiModel(), PinModel()
        reader = FILES.windows.NativeFile(api, [pin], max_bytes=6, writable=False, deadline=self.local + 120)
        leaf = C._Copy(self.owner, C._Inputs(self.originals()), self.local)
        try:
            self.assertEqual(leaf.stream(reader, info, C._Member(6, 6, P.digest(b"abcdef")), "source"),
                             (6, P.digest(b"abcdef")))
            self.assertEqual(api.read_calls, [6])  # read(1) at exhaustion issued no API read.
            pin.current = replace(info, modified_100ns=2)
            with self.assertRaisesRegex(FILES.windows.FilesystemError, "Native input changed"):
                reader.verify()
            pin.current = info  # Fixture-only model restoration for its own close.
        finally:
            reader.close()
        self.assertTrue(pin.released)


if __name__ == "__main__":
    unittest.main()
