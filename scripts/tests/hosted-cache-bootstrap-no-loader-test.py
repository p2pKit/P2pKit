#!/usr/bin/env python3
"""Whole no-loader leaf over explicit memory-only parent/clock/directory models.

No old test fixture, hosted environment, original producer, filesystem operation,
native handle, initializer contents or provider is used. Pure request rederivation
and the complete new leaf/reused ownership code execute, not AST excerpts.
"""
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).absolute().parents[1]))
import hosted_cache_bootstrap_no_loader as N


def originals():
    """Synthetic supplied DATA only: never an actual hosted identity admission."""
    source = {"commit": "a" * 40, "tree": "b" * 40}
    workflow = ".github/workflows/dependency-cache-bootstrap.yml"
    admission = {"schema": 1, "scope": "CACHE_BOOTSTRAP_HOSTED_IDENTITY_V1", "profile": "cache-bootstrap",
        "source": source, "selection": "desktop-linux-x64", "cacheCohort": {"profile": "desktop", "role": "linux-x64"},
        "producerCommand": ["help", "--console=plain", "--no-configure-on-demand"],
        "producerScope": "CONFIGURATION_ONLY_NOT_COMPLETE_DEPENDENCIES_OR_TESTS", "testAcceptance": "NOT_PERFORMED",
        "policy": {"commit": "c" * 40}, "github": {"repository": "p2pKit/P2pKit", "event": "workflow_dispatch",
            "workflow": workflow, "workflowSha": source["commit"], "job": "populate", "runnerOS": "Linux",
            "runnerArch": "X64", "eventBinding": {"policyMain": "c" * 40, "selection": "desktop-linux-x64",
                "expectedCommit": source["commit"], "expectedTree": source["tree"]}}}
    canonical = {"schema": 1, "root": "/offline-no-loader/repository", "expectedCommit": source["commit"],
        "tree": source["tree"], "source": {**source, "status": "", "diffSha256": N.producer.digest(b"")},
        "host": "linux-x64", "gradleHome": "/offline-no-loader/session/state/gradle-home",
        "createdUtc": "2026-09-19T00:00:00+00:00", "id": "d" * 32,
        "gradlePropertiesSha256": "e" * 64, "javaHomes": [], "preexistingOutputPaths": []}
    admitted_raw, canonical_raw = map(N.producer.encoded, (admission, canonical))
    request = N.producer.make_request(admitted_raw, canonical_raw,
                                      invocation="f" * 32, ancestor_invocations=["1" * 32])
    return N.HomeOriginals(N.producer.encoded(request), admitted_raw, canonical_raw, (7, 11))


class Clock:
    def __init__(self):
        self.value, self.values, self.hook = 10.0, [], lambda: None

    def __call__(self):
        self.hook()
        if self.values:
            self.value = self.values.pop(0)
        return self.value


class Parent:
    """Modeled stable-callable ledger, NOT the real original-call/RAW owner."""
    def __init__(self):
        self.resources, self.original, self.unknown, self.closed = [], None, False, False
        self.errors, self.closed_values = [], []
        self.end_value, self.ends = 95.0, []
        self.cancel_hook, self.acquire_hook, self.error_hook = lambda: None, lambda row: None, lambda: None
        self.cancelled = lambda: self.cancel_hook()

    def end(self):
        if self.ends:
            self.end_value = self.ends.pop(0)
        return self.end_value

    def acquire(self, label, factory):
        value = factory()
        row = {"label": label, "owner": value, "attempted": False, "closed": False}
        self.resources.append(row)
        self.acquire_hook(row)
        return value

    def close_one(self, value):
        row = next(row for row in self.resources if row["owner"] is value)
        if row["attempted"]:
            raise AssertionError("MODEL_DUPLICATE_CLOSE")
        row["attempted"] = True
        self.closed_values.append(value)
        value.close()
        row["closed"] = True

    def error(self, stage, error, *, unknown=False):
        if self.original is None:
            self.original = error
        self.errors.append((stage, error))
        self.unknown |= unknown
        self.error_hook()


class Directory:
    """No fd/real path. Native no-follow/kind checks are a supplier model seam."""
    def __init__(self, path, identity):
        self.path = path
        self.info = N.files.PosixInfo(identity, True, 0, 0o40700, 1000, 2, 100, 100)
        self.listing, self.listings = (), []
        self.verify_count, self.name_count, self.close_count = 0, 0, 0
        self.verifying, self.enumerating = lambda: None, lambda: None
        self.child, self.open_error, self.close_error = None, None, None
        self.opens, self.deadlines, self.closed = [], [], False

    def verify(self):
        if self.closed:
            raise AssertionError("MODEL_USE_AFTER_CLOSE")
        self.verify_count += 1
        self.verifying()
        return self.info

    def names(self, *, max_names, deadline):
        self.name_count += 1
        self.deadlines.append((max_names, deadline))
        self.enumerating()
        return self.listings.pop(0) if self.listings else self.listing

    def open_directory(self, name, *, deadline):
        self.opens.append((name, deadline))
        if self.open_error is not None:
            raise self.open_error
        if name != "init.d" or self.child is None:
            raise AssertionError("MODEL_UNSELECTED_DIRECTORY")
        return self.child

    def close(self):
        self.close_count += 1
        if self.closed or self.close_count != 1:
            raise AssertionError("MODEL_DUPLICATE_DIRECTORY_CLOSE")
        if self.close_error is not None:
            raise self.close_error
        self.closed = True

    def open_file(self, *args, **kwargs):
        raise AssertionError("MODEL_FORBIDS_FILE_CONTENT_READ")


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class MemoryCase(unittest.TestCase):
    def setUp(self):
        self.originals = originals()
        self.parent, self.clock, self.roots = Parent(), Clock(), []
        self.home = Directory(Path("/offline-no-loader/session/state/gradle-home"), (7, 11))
        self.init = Directory(self.home.path / "init.d", (7, 12))
        self.home.child = self.init
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(N.files, "PosixSourceDirectory", Directory))
        self.stack.enter_context(patch.object(N.files, "public_root", self.open_home))
        self.stack.enter_context(patch.object(N.time, "monotonic", self.clock))

    def open_home(self, path):
        self.roots.append(path)
        self.assertEqual(path, self.home.path)
        return self.home

    def with_init(self):
        self.home.listing = ("init.d",)

    def observe(self):
        return N.observe_absence(self.parent, self.originals)

    def refusal(self, text, kind=Exception):
        with self.assertRaisesRegex(kind, text) as caught:
            self.observe()
        return caught.exception

    def record(self):
        return N.producer.parse(self.observe().raw)


class InitialModels(MemoryCase):
    def test_missing_init_is_two_listings_not_uninstall(self):
        result = self.record()
        self.assertEqual(result["initDirectory"], "ABSENT_IN_HOME_LISTINGS")
        self.assertEqual(len(result["listings"]), 2)
        self.assertEqual(self.home.name_count, 2)
        self.assertEqual(self.home.close_count, 1)
        self.assertEqual(self.init.close_count, 0)
        self.assertFalse(self.parent.closed)
        self.assertEqual(self.roots, [self.home.path])

    def test_empty_init_has_four_listings_and_reverse_close(self):
        self.with_init()
        result = self.record()
        self.assertEqual(result["initDirectory"], "OBSERVED_DIRECTORY")
        self.assertEqual(len(result["listings"]), 4)
        self.assertEqual(self.parent.closed_values, [self.init, self.home])
        self.assertEqual(self.home.opens, [("init.d", 95.0)])

    def test_other_names_counted_without_opening_contents(self):
        self.with_init()
        self.home.listing = (".private", "gradle.properties", "init.d")
        self.init.listing = (".hidden", "other-init.gradle")
        result = self.record()
        self.assertEqual([row["names"] for row in result["listings"]], [3, 2, 2, 3])
        self.assertEqual(self.init.opens, [])
        self.assertNotIn("other-init.gradle", N.producer.encoded(result).decode())

    def test_child_open_uses_shrink_inside_acquisition(self):
        self.with_init()
        def after_listing():
            if self.home.verify_count == 2:
                # Final listing check85, R1's pre-acquire check85, acquire check70.
                # The native supplier must receive the current70, not saved85.
                self.parent.ends = [85.0, 85.0, 70.0]
        self.home.verifying = after_listing
        self.observe()
        self.assertEqual(self.home.opens, [("init.d", 70.0)])


class InputModels(MemoryCase):
    def test_wrong_record_kind_before_open(self):
        self.originals = object()
        self.refusal("INPUT_KIND")
        self.assertEqual(self.roots, [])

    def test_nonbytes_and_oversize_metadata_before_open(self):
        valid = self.originals
        for raw in (bytearray(b"{}"), b"", b"x" * (4 * 1024 * 1024 + 1)):
            with self.subTest(kind=type(raw).__name__, size=len(raw)):
                self.originals = replace(valid, request_raw=raw)
                self.refusal("METADATA_BYTES")
        self.assertEqual(self.roots, [])

    def test_invalid_home_identity_before_open(self):
        valid = self.originals
        for identity in ([7, 11], (True, 11), (7, 0), (7, 11, 13), (7, "0" * 32)):
            with self.subTest(identity=identity):
                self.originals = replace(valid, home_identity=identity)
                self.refusal("HOME_IDENTITY")
        self.assertEqual(self.roots, [])

    def test_native_identity_kind_mismatch(self):
        self.originals = replace(self.originals, home_identity=(7, "a" * 32))
        self.refusal("PLATFORM")
        self.assertEqual(self.roots, [])

    def test_ordinary_request_cannot_be_bootstrap(self):
        self.originals = replace(self.originals, admitted_raw=N.producer.encoded({"profile": "desktop"}))
        self.refusal("PRODUCER_ADMISSION")
        self.assertEqual(self.roots, [])

    def test_reencoded_or_changed_request_refused(self):
        valid = self.originals
        changed = N.producer.parse(valid.request_raw)
        changed["gradleHome"] = "/offline-no-loader/other/gradle-home"
        for raw in (valid.request_raw + b" ", N.producer.encoded(changed)):
            with self.subTest(size=len(raw)):
                self.originals = replace(valid, request_raw=raw)
                self.refusal("REQUEST_CHANGED")
        self.assertEqual(self.roots, [])

    def test_changed_source_canonical_refused(self):
        canonical = N.producer.parse(self.originals.canonical_raw)
        canonical["tree"] = "0" * 40
        self.originals = replace(self.originals, canonical_raw=N.producer.encoded(canonical))
        self.refusal("SOURCE_OR_HOST")
        self.assertEqual(self.roots, [])

    def test_input_mutation_in_callback_refused_and_known_close(self):
        self.home.enumerating = lambda: object.__setattr__(self.originals, "request_raw", b"{}")
        error = self.refusal("INPUT_CHANGED")
        self.assertEqual(error.bootstrap_no_loader_result["leafHandleClose"], "KNOWN")
        self.assertEqual(self.home.close_count, 1)


class ListingModels(MemoryCase):
    def test_present_target_is_failure_not_removal(self):
        self.with_init()
        self.init.listing = (N.LOADER,)
        error = self.refusal("TARGET_PRESENT")
        self.assertFalse(error.bootstrap_no_loader_result["deletionPerformed"])
        self.assertEqual(self.init.listing, (N.LOADER,))
        self.assertEqual(self.parent.closed_values, [self.init, self.home])

    def test_selected_root_aliases_refused(self):
        for name in ("INIT.D", "init.d.", "init.d "):
            with self.subTest(name=name):
                self.assertRaisesRegex(N.NoLoaderError, "SELECTED_ALIAS", N._Observation.selected,
                                       None, (name,), N.INIT_DIRECTORY)

    def test_selected_target_aliases_refused(self):
        self.with_init()
        self.init.listing = (N.LOADER.upper(),)
        self.refusal("SELECTED_ALIAS")

    def test_selected_trailing_dot_alias_refused(self):
        self.with_init()
        self.init.listing = (N.LOADER + ". ",)
        self.refusal("SELECTED_ALIAS")

    def test_present_init_file_or_symlink_supplier_refusal(self):
        self.with_init()
        error = RuntimeError("MODELED_NOFOLLOW_DIRECTORY_REFUSAL")
        self.home.open_error = error
        self.assertIs(self.refusal("MODELED_NOFOLLOW"), error)
        self.assertEqual(self.home.close_count, 1)
        self.assertEqual(self.init.close_count, 0)

    def test_wrong_directory_path_refused(self):
        self.with_init()
        self.init.path = self.home.path / "other"
        self.refusal("DIRECTORY_KIND_OR_PATH")

    def test_home_replacement_refused(self):
        self.home.info = replace(self.home.info, identity=(7, 99))
        self.refusal("HOME_REPLACED")

    def test_wrong_root_path_refused_by_leaf(self):
        wrong = Directory(self.home.path.parent / "other", self.home.info.identity)
        with patch.object(N.files, "public_root", lambda path: wrong):
            self.refusal("DIRECTORY_KIND_OR_PATH")
        self.assertEqual(wrong.close_count, 1)

    def test_child_info_nondirectory_refused(self):
        self.with_init()
        self.init.info = replace(self.init.info, is_directory=False)
        self.refusal("FILE_INFO")

    def test_child_different_volume_refused(self):
        self.with_init()
        self.init.info = replace(self.init.info, identity=(8, 12))
        self.refusal("HOME_REPLACED")

    def test_child_alias_of_home_refused(self):
        self.with_init()
        self.init.info = replace(self.init.info, identity=self.home.info.identity)
        self.refusal("FILE_ALIAS")

    def test_changed_directory_stamp_during_listing_refused(self):
        self.home.enumerating = lambda: setattr(self.home, "info", replace(self.home.info, mtime_ns=101))
        self.refusal("DIRECTORY_CHANGED")

    def test_changed_home_membership_between_listings_refused(self):
        self.home.listings = [(), ("init.d",)]
        self.refusal("HOME_CHANGED")

    def test_changed_init_membership_between_listings_refused(self):
        self.with_init()
        self.init.listings = [("one.gradle",), ("two.gradle",)]
        self.refusal("INIT_CHANGED")

    def test_changed_child_stamp_between_listings_refused(self):
        self.with_init()
        def change():
            if self.init.verify_count == 3:
                self.init.info = replace(self.init.info, ctime_ns=101)
        self.init.verifying = change
        self.refusal("INIT_CHANGED")

    def test_target_appears_second_listing_refused(self):
        self.with_init()
        self.init.listings = [(), (N.LOADER,)]
        self.refusal("TARGET_PRESENT")

    def test_unsorted_listing_refused(self):
        self.home.listing = ("z", "a")
        self.refusal("NAME_ORDER_OR_ALIAS")

    def test_duplicate_casefold_names_refused(self):
        self.home.listing = ("A", "a")
        self.refusal("NAME_ORDER_OR_ALIAS")

    def test_malformed_listing_refused(self):
        self.home.listing = ["init.d"]
        self.refusal("NO_LOADER_NAMES")

    def test_unsafe_names_refused(self):
        inputs = N._Inputs(self.originals)
        observer = N._Observation(self.parent, inputs, 10.0)
        for names in ((1,), ("",), ("..",), (".",), ("a/b",), ("a\0b",), ("x" * 256,)):
            with self.subTest(names=names):
                self.home.listing = names
                self.assertRaisesRegex(N.NoLoaderError, "NO_LOADER_NAMES", observer.listing, self.home, ())

    def test_listing_member_bound_refused(self):
        self.home.listing = tuple(f"x{index:04d}" for index in range(N.NAMES + 1))
        self.refusal("NO_LOADER_NAMES")

    def test_exact_listing_member_bound_allowed_without_content_reads(self):
        self.home.listing = tuple(f"x{index:04d}" for index in range(N.NAMES))
        result = self.record()
        self.assertEqual([row["names"] for row in result["listings"]], [N.NAMES, N.NAMES])
        self.assertEqual(self.home.opens, [])


class LifetimeModels(MemoryCase):
    def test_local90_not_inherited120_reaches_native_names(self):
        self.parent.end_value = 200.0
        result = self.record()
        self.assertEqual(self.home.deadlines, [(N.NAMES, 100.0)] * 2)
        self.assertEqual(result["localWindow"]["end"], 100.0)

    def test_caller_ceiling_cannot_be_renewed(self):
        self.parent.ends = [80.0, 95.0, 110.0]
        self.observe()
        self.assertTrue(all(end == 80.0 for _count, end in self.home.deadlines))

    def test_equal_local90_expires_before_acquisition(self):
        self.clock.values = [10.0, 100.0]
        self.refusal("LOCAL_EXPIRED")
        self.assertEqual(self.roots, [])

    def test_equal_caller_end_expires_before_acquisition(self):
        self.parent.end_value = 10.0
        self.refusal("CALLER_EXPIRED")
        self.assertEqual(self.roots, [])

    def test_nonfinite_clock_refused(self):
        self.clock.value = float("nan")
        self.refusal("LOCAL_CLOCK")
        self.assertEqual(self.roots, [])

    def test_backward_clock_refused(self):
        self.clock.values = [10.0, 9.0]
        self.refusal("LOCAL_BACKWARDS")
        self.assertEqual(self.roots, [])

    def test_cancel_preserves_original_and_closes_known_handle(self):
        original = KeyboardInterrupt("MODEL_CANCEL")
        def cancel():
            if self.home.name_count:
                raise original
        self.parent.cancel_hook = cancel
        self.assertIs(self.refusal("MODEL_CANCEL", BaseException), original)
        self.assertEqual(self.home.close_count, 1)

    def test_known_expiry_closes_once_without_claiming_success(self):
        self.home.enumerating = lambda: setattr(self.clock, "value", 100.0)
        error = self.refusal("LOCAL_EXPIRED")
        result = error.bootstrap_no_loader_result
        self.assertFalse(result["completed"])
        self.assertEqual(result["leafHandleClose"], "KNOWN")
        self.assertEqual(self.home.close_count, 1)

    def test_unknown_quarantines_without_closes(self):
        self.with_init()
        self.init.enumerating = lambda: setattr(self.parent, "unknown", True)
        error = self.refusal("PARENT_NOT_LIVE")
        self.assertEqual(error.bootstrap_no_loader_result["observationState"], "UNKNOWN")
        self.assertEqual(self.parent.closed_values, [])
        self.assertEqual(len(error.bootstrap_no_loader_resources), 2)

    def test_close_uncertainty_stops_new_close_and_preserves_resources(self):
        self.with_init()
        original = RuntimeError("MODEL_CLOSE_UNKNOWN")
        self.init.close_error = original
        error = self.refusal("MODEL_CLOSE_UNKNOWN")
        self.assertIs(error, original)
        self.assertEqual(self.parent.closed_values, [self.init])
        self.assertEqual(self.home.close_count, 0)
        self.assertEqual(error.bootstrap_no_loader_result["leafHandleClose"], "UNKNOWN")
        self.assertEqual(len(error.bootstrap_no_loader_resources), 2)

    def test_post_factory_error_keeps_returned_handle_for_close(self):
        original = FalseyFailure("MODEL_AFTER_FACTORY")
        def fail(row):
            raise original
        self.parent.acquire_hook = fail
        error = self.refusal("MODEL_AFTER_FACTORY")
        self.assertIs(error, original)
        self.assertEqual(self.home.close_count, 1)
        self.assertIs(error.bootstrap_no_loader_resources[0].value, self.home)

    def test_falsey_first_error_survives_secondary_close_failure(self):
        original = FalseyFailure("MODEL_FIRST_FALSEY")
        def fail():
            raise original
        self.home.enumerating = fail
        self.home.close_error = RuntimeError("MODEL_SECONDARY_CLOSE")
        error = self.refusal("MODEL_FIRST_FALSEY")
        self.assertIs(error, original)
        self.assertEqual(self.home.close_count, 1)
        self.assertEqual(error.bootstrap_no_loader_result["leafHandleClose"], "UNKNOWN")

    def test_erased_registration_is_unknown_not_lost_reference(self):
        original = FalseyFailure("MODEL_ERASED_ROW")
        def erase(row):
            self.parent.resources.remove(row)
            raise original
        self.parent.acquire_hook = erase
        error = self.refusal("MODEL_ERASED_ROW")
        self.assertIs(error, original)
        self.assertEqual(error.bootstrap_no_loader_result["leafHandleClose"], "UNKNOWN")
        self.assertIs(error.bootstrap_no_loader_resources[0].value, self.home)
        self.assertEqual(self.home.close_count, 0)

    def test_final_encoding_expiry_cannot_publish_success(self):
        encode = N.files.encoded
        def late(value):
            raw = encode(value)
            if type(value) is dict and value.get("scope") == N.SCOPE:
                self.clock.value = 100.0
            return raw
        with patch.object(N.files, "encoded", late):
            error = self.refusal("LOCAL_EXPIRED")
        self.assertFalse(error.bootstrap_no_loader_result["completed"])
        self.assertEqual(self.home.close_count, 1)


class ScopeModels(MemoryCase):
    def test_result_cannot_claim_history_tests_retirement_or_export(self):
        result = self.record()
        expected = {"scope": "BOOTSTRAP_EXACT_CUSTODY_LOADER_ABSENCE_LEAF_V1", "completed": True,
            "inputProvenance": "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL", "leafHandleClose": "KNOWN",
            "enclosingOwnerRetirement": "NOT_OBSERVED_HERE", "producerAndCollectionReturn": "NOT_OBSERVED_HERE",
            "historicalLoaderExecution": "NOT_OBSERVED", "otherInitializerContents": "NOT_INSPECTED",
            "deletionPerformed": False, "fileContentsRead": False, "dependencyPopulation": "NOT_ATTESTED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "nextPhaseAuthority": False, "exportSaveAuthority": False}
        self.assertEqual({key: result[key] for key in expected}, expected)
        self.assertEqual(result["binding"]["target"], "init.d/p2pkit-test-transcript-custody.gradle")
        self.assertEqual(result["binding"]["requestSha256"], N.files.digest(self.originals.request_raw))
        self.assertEqual(result["observationBoundary"],
                         "PINNED_LISTINGS_AND_SAME_HANDLE_VERIFY_NOT_ATOMIC_OR_HISTORICAL_ABSENCE")


if __name__ == "__main__":
    unittest.main()
