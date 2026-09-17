#!/usr/bin/env python3
"""Pure provider declarations and tiny owned files, NOT hosted cache qualification.

No Gradle, action, network, dependency archive, GPG, subprocess or native Windows
provider is executed. Reuse the maintained seed fixture rather than a fake seed
context or a second copier. Its unchanged 33 methods are run separately once.
"""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_dependency_cache as K
import hosted_dependency_seed_files as S

SPEC = importlib.util.spec_from_file_location("cache_seed_fixtures", ROOT / "scripts/tests/hosted-dependency-seed-files-test.py")
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


class DependencyCache(unittest.TestCase):
    def setUp(self):
        self.fixture = F.SeedFiles()
        self.fixture.setUp()
        # The real staging allocator creates private S. Seed's public-source
        # fixture intentionally uses0755; make this fixture match the allocator.
        self.fixture.source.chmod(0o700)
        self.prepare()

    def tearDown(self):
        self.fixture.tearDown()

    def prepare(self):
        f = self.fixture
        f.bind()
        self.seed_raw = S.encoded(f.seed())
        self.plan = K.make_plan(f.admitted_raw, f.staging_raw, f.compiled, f.inputs, session=f.session,
                                profile="desktop", role="macos-arm64", mode="bootstrap")

    def plan_for(self, mode="bootstrap", *, admitted_raw=None, inputs=None):
        f = self.fixture
        admitted_raw, inputs = admitted_raw or f.admitted_raw, inputs or f.inputs
        staging = S.stage_record(admitted_raw, "desktop", "macos-arm64", f.container,
                                 S._info(f.container.stat()), S._info(f.source.stat()), inputs)
        return K.make_plan(admitted_raw, S.encoded(staging), f.compiled, inputs, session=f.session,
                            profile="desktop", role="macos-arm64", mode=mode)

    def candidate(self, name="FastInfoset", *, data=None, bucket=None):
        f = self.fixture
        raw = f.rows[name] if data is None else data
        bucket = hashlib.sha1(raw).hexdigest() if bucket is None else bucket
        path = f.home.joinpath(*S.PREFIX, "org.fixture", name, "1.0", bucket, name + ".jar")
        path.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o644)
        return path

    def export(self, *, now=None, check=lambda: None):
        f = self.fixture
        clock = now or (lambda: int(time.monotonic() * 10**9))
        began = clock()
        self.interval = S.window(began, began + S.HARD_SECONDS * 10**9, began + S.SOFT_SECONDS * 10**9,
                                 raw=False, job_budget=None)
        return K.export_snapshot(f.owner, self.plan, f.staging_raw, self.seed_raw, f.context_raw,
                                  f.canonical_raw, f.admitted_raw, f.compiled, end=time.monotonic() + 120,
                                  check=check, now=clock, interval=self.interval)

    def validate(self, result):
        f = self.fixture
        return K.validate_export_receipt(result, self.plan, f.staging_raw, self.seed_raw, f.context_raw,
                                         f.canonical_raw, f.admitted_raw, f.compiled)

    def outputs(self, plan, **changes):
        values = {"cache-primary-key": plan["key"], "cache-matched-key": plan["key"], "cache-hit": "true"}
        values.update(changes)
        return values

    def test_key_reuses_semantics_without_reusing_source_run_or_mode_authority(self):
        f = self.fixture
        consume = self.plan_for("consume")
        raw = S.record(f.admitted_raw)
        raw["source"]["commit"] = "c" * 40
        raw["github"]["runAttempt"] = "2"
        changed = self.plan_for("consume", admitted_raw=S.encoded(raw))
        self.assertEqual(self.plan["key"], consume["key"])
        self.assertEqual(consume["key"], changed["key"])
        self.assertNotEqual(S.digest(S.encoded(consume)), S.digest(S.encoded(changed)))
        old = K.provider_observation(consume, "restore", original_outcome="success", outputs=self.outputs(consume))
        with self.assertRaisesRegex(S.SeedError, "REPLAYED"):
            K.validate_provider_observation(old, changed, "restore")

    def test_key_separates_role_profile_allowlist_and_wrapper(self):
        original = K.cache_key("desktop", "macos-arm64", "a" * 64, "b" * 64)
        for args in (("desktop", "macos-x64", "a" * 64, "b" * 64),
                     ("full", "macos-arm64", "a" * 64, "b" * 64),
                     ("desktop", "macos-arm64", "c" * 64, "b" * 64),
                     ("desktop", "macos-arm64", "a" * 64, "c" * 64)):
            self.assertNotEqual(original, K.cache_key(*args))
        for args in (("full", "windows-x64", "a" * 64, "b" * 64),
                     ("desktop", "rosetta", "a" * 64, "b" * 64),
                     ("desktop", "macos-arm64", "A" * 64, "b" * 64)):
            with self.assertRaises(S.SeedError):
                K.cache_key(*args)

    def test_raw_xml_format_changes_do_not_change_semantic_cache_key(self):
        f = self.fixture
        original = self.plan["key"]
        f.xml = f.xml.replace(b"><", b">\n<")
        f.compiled = S.authority.parse_allowlist(f.xml)
        changed = copy.deepcopy(f.inputs)
        changed["files"][S.INPUTS[0]] = f.compiled.source_sha256
        self.assertNotEqual(changed["files"][S.INPUTS[0]], f.inputs["files"][S.INPUTS[0]])
        self.assertEqual(self.plan_for(inputs=changed)["key"], original)

    def test_explicit_mode_and_exact_original_plan_are_required(self):
        f = self.fixture
        for mode in (None, "", "cold-fallback", True):
            with self.assertRaises(S.SeedError):
                self.plan_for(mode)
        mutations = [lambda p: p.update(schema=True), lambda p: p.update(extra=True),
                     lambda p: p.update(mode="consume"), lambda p: p.update(key=p["key"].upper()),
                     lambda p: p["source"].update(commit="d" * 40),
                     lambda p: p["github"].update(runAttempt="2"),
                     lambda p: p["provider"].update(restoreKeys=["fallback-"]),
                     lambda p: p["provider"].update(enableCrossOsArchive=True),
                     lambda p: p.update(stagingSha256="e" * 64)]
        for mutate in mutations:
            changed = copy.deepcopy(self.plan)
            mutate(changed)
            with self.assertRaises(S.SeedError):
                K.validate_plan(changed, f.admitted_raw, f.staging_raw, f.compiled, f.inputs,
                                 session=f.session, profile="desktop", role="macos-arm64", mode="bootstrap")

    def test_restore_requires_original_success_and_three_byte_exact_outputs(self):
        plan = self.plan_for("consume")
        exact = K.provider_observation(plan, "restore", original_outcome="success", outputs=self.outputs(plan))
        self.assertEqual(exact["status"], "REPORTED_EXACT_HIT")
        self.assertEqual(K.validate_provider_observation(exact, plan, "restore"), exact)
        for outcome in ("failure", "cancelled", "skipped", ""):
            observed = K.provider_observation(plan, "restore", original_outcome=outcome, outputs=self.outputs(plan))
            self.assertEqual(observed["status"], "STEP_NOT_SUCCESSFUL")
        for changes in ({"cache-hit": "false"}, {"cache-hit": ""},
                        {"cache-primary-key": ""}, {"cache-matched-key": ""},
                        {"cache-matched-key": plan["key"].upper()}, {"cache-primary-key": "different"}):
            observed = K.provider_observation(plan, "restore", original_outcome="success",
                                              outputs=self.outputs(plan, **changes))
            self.assertEqual(observed["status"], "NO_QUALIFIED_EXACT_HIT")

    def test_empty_false_and_inexact_outputs_are_not_proven_backend_misses(self):
        plan = self.plan_for("consume")
        for outputs in ({"cache-primary-key": plan["key"], "cache-matched-key": "", "cache-hit": ""},
                        {"cache-primary-key": "", "cache-matched-key": "", "cache-hit": "false"},
                        {"cache-primary-key": "", "cache-matched-key": "", "cache-hit": ""},
                        self.outputs(plan, **{"cache-matched-key": "prefix-match", "cache-hit": "false"})):
            result = K.provider_observation(plan, "restore", original_outcome="success", outputs=outputs)
            self.assertEqual(result["status"], "NO_QUALIFIED_EXACT_HIT")
            self.assertEqual(plan["mode"], "consume")  # No implicit bootstrap.

    def test_bootstrap_has_no_restore_and_consume_has_no_writeback(self):
        for mode, phase in (("bootstrap", "restore"), ("consume", "save"), ("consume", "lookup")):
            with self.assertRaisesRegex(S.SeedError, "PHASE_FORBIDDEN"):
                K.provider_observation(self.plan_for(mode), phase, original_outcome="success", outputs={})

    def test_save_has_no_outputs_and_success_never_claims_population(self):
        result = K.provider_observation(self.plan, "save", original_outcome="success", outputs={})
        self.assertEqual(result["status"], "SAVE_SUCCEEDED_STORAGE_UNPROVEN")
        with self.assertRaisesRegex(S.SeedError, "OUTPUT_ROSTER"):
            K.provider_observation(self.plan, "save", original_outcome="success", outputs={"cache-id": "1"})
        lookup = K.provider_observation(self.plan, "lookup", original_outcome="success", outputs=self.outputs(self.plan))
        self.assertEqual(lookup["status"], "REPORTED_EXACT_HIT")
        empty = self.export()
        self.assertEqual(empty["status"], "KNOWN_EMPTY")
        self.assertFalse(K.nonempty_snapshot(empty))  # Even with declared green save/lookup.

    def test_provider_record_cannot_be_relabelled_or_replayed(self):
        plan = self.plan_for("consume")
        original = K.provider_observation(plan, "restore", original_outcome="failure", outputs=self.outputs(plan))
        for changes in ({"schema": True}, {"status": "REPORTED_EXACT_HIT"}, {"planSha256": "f" * 64},
                        {"phase": "lookup"}, {"extra": "ignored"}):
            changed = {**original, **changes}
            with self.assertRaises(S.SeedError):
                K.validate_provider_observation(changed, plan, "restore")
        for outputs in ({}, self.outputs(plan, **{"cache-hit": True}),
                        self.outputs(plan, **{"cache-hit": "TRUE"}),
                        self.outputs(plan, **{"cache-primary-key": "x" * 513}),
                        self.outputs(plan, **{"cache-matched-key": "key\nextra"})):
            with self.assertRaises(S.SeedError):
                K.provider_observation(plan, "restore", original_outcome="success", outputs=outputs)

    def test_export_uses_original_empty_stage_and_shared_verified_copy(self):
        f = self.fixture
        candidate = self.candidate()
        identities = (f.home.stat().st_ino, f.source.stat().st_ino)
        result = self.export()
        self.validate(result)
        self.assertEqual(result["status"], "KNOWN_EXPORTED")
        self.assertTrue(K.nonempty_snapshot(result))
        destination = f.source / result["admitted"][0]["path"]
        self.assertEqual(destination.read_bytes(), candidate.read_bytes())
        self.assertNotEqual(destination.stat().st_ino, candidate.stat().st_ino)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(identities, (f.home.stat().st_ino, f.source.stat().st_ino))
        self.assertFalse((f.source / "gradle.properties").exists())
        self.assertEqual((f.home / "gradle.properties").read_bytes(), f.properties)
        f.assert_known_closed()

    def test_export_never_opens_or_copies_unselected_private_or_executable_state(self):
        f = self.fixture
        self.candidate()
        forbidden = ("init.d/private.gradle", "wrapper/gradle/bin/gradle", "caches/metadata-2/resource.bin",
                     "caches/build-cache/entry", "logs/daemon.log", "credentials/key")
        for name in forbidden:
            path = f.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"SYNTHETIC PRIVATE DO NOT EXPORT")
        opened, original = [], S._PosixDirectory._child
        def observed(view, name, **kwargs):
            opened.append(str(view.path / name))
            return original(view, name, **kwargs)
        with patch.object(S._PosixDirectory, "_child", observed):
            result = self.export()
        self.assertEqual(result["status"], "KNOWN_EXPORTED")
        self.assertFalse(any(str(f.home / name) in opened for name in forbidden))
        self.assertEqual({p.relative_to(f.source).as_posix() for p in f.source.rglob("*") if p.is_file()},
                         {result["admitted"][0]["path"]})

    def test_nonempty_stage_is_not_cleared_adopted_or_overwritten(self):
        f = self.fixture
        self.candidate()
        other = f.source / "gradle.properties"
        other.write_bytes(b"foreign")
        with self.assertRaisesRegex(S.SeedError, "STAGE_NOT_EMPTY") as caught:
            self.export()
        self.assertEqual(other.read_bytes(), b"foreign")
        self.assertFalse(caught.exception.cache_export_result["completed"])
        self.assertEqual({p.name for p in f.source.iterdir()}, {"gradle.properties"})

    def replace_root(self, path):
        prior = path.with_name(path.name + "-original")
        path.rename(prior)
        path.mkdir(mode=0o700)
        return prior

    def test_replaced_stage_root_is_rejected_before_copy(self):
        self.candidate()
        self.replace_root(self.fixture.source)
        with self.assertRaisesRegex(S.SeedError, "ORIGINAL_ROOT_REPLACED"):
            self.export()
        self.assertEqual(list(self.fixture.source.iterdir()), [])

    def test_replaced_home_is_rejected_instead_of_rebinding_current_path(self):
        self.candidate()
        self.replace_root(self.fixture.home)
        with self.assertRaisesRegex(S.SeedError, "ORIGINAL_ROOT_REPLACED"):
            self.export()
        self.assertEqual(list(self.fixture.source.iterdir()), [])

    def test_same_stage_under_replaced_container_is_rejected(self):
        f = self.fixture
        self.candidate()
        prior = self.replace_root(f.container)
        (prior / "restore-home").rename(f.source)
        with self.assertRaisesRegex(S.SeedError, "CONTAINER_REPLACED"):
            self.export()
        self.assertEqual(list(f.source.iterdir()), [])

    def test_changed_properties_never_become_export_input(self):
        f = self.fixture
        self.candidate()
        (f.home / "gradle.properties").write_bytes(b"changed")
        with self.assertRaisesRegex(S.SeedError, "PROPERTIES_CHANGED"):
            self.export()
        self.assertEqual(list(f.source.iterdir()), [])

    def test_existing_seeded_restore_cannot_be_reinterpreted_as_bootstrap(self):
        f = self.fixture
        original = f.candidate()
        self.seed_raw = S.encoded(f.seed())
        with self.assertRaisesRegex(S.SeedError, "EMPTY_ORIGINAL_SEED"):
            self.export()
        self.assertEqual(original.read_bytes(), f.rows["FastInfoset"])

    def test_export_hash_mismatch_is_known_empty_not_population(self):
        self.candidate(data=b"wrong")
        result = self.export()
        self.validate(result)
        self.assertEqual(result["status"], "KNOWN_EMPTY")
        self.assertEqual(result["misses"][0]["reason"], "SHA256_REJECTED")
        self.assertFalse(K.nonempty_snapshot(result))
        self.fixture.assert_known_closed()

    def test_zero_length_admitted_artifact_still_cannot_claim_nonempty_population(self):
        self.fixture.rows = {"FastInfoset": b""}
        self.prepare()
        self.candidate()
        result = self.export()
        self.assertEqual(result["status"], "KNOWN_EXPORTED")
        self.assertEqual(result["counts"]["outputBytes"], 0)
        self.assertFalse(K.nonempty_snapshot(result))

    def test_partial_byte_budget_preserves_original_bounds_and_closed_files(self):
        f = self.fixture
        f.rows = {"A": b"123", "B": b"456"}
        with patch.object(S, "TOTAL_LIMIT", 5):
            self.prepare()
            self.candidate("A")
            self.candidate("B")
            result = self.export()
            self.validate(result)
        self.assertEqual(result["status"], "KNOWN_PARTIAL")
        self.assertEqual(result["counts"]["outputBytes"], 3)
        self.assertEqual(result["misses"][0]["reason"], "BYTE_BUDGET")
        f.assert_known_closed()

    def test_receipt_budget_stops_before_creating_a_destination(self):
        with patch.object(S, "RECEIPT_LIMIT", 16000):
            self.prepare()
            self.candidate()
            result = self.export()
            self.validate(result)
        self.assertEqual(result["status"], "KNOWN_EMPTY")
        self.assertEqual(result["misses"][0]["reason"], "BYTE_OR_RECEIPT_BUDGET")
        self.assertFalse((self.fixture.source / "caches").exists())

    def test_soft_stop_and_hard_expiry_do_not_renew_original_window(self):
        self.candidate()
        clock = [10**9]
        def soft():
            clock[0] = self.interval["softEndNs"]
        result = self.export(now=lambda: clock[0], check=soft)
        self.assertEqual(result["status"], "KNOWN_EMPTY")
        self.assertEqual(result["misses"][0]["reason"], "BUDGET_NOT_STARTED")
        clock[0] = 10**9
        def hard():
            clock[0] = self.interval["hardEndNs"]
        with self.assertRaisesRegex(S.SeedError, "ORIGINAL_HARD_DEADLINE") as caught:
            self.export(now=lambda: clock[0], check=hard)
        self.assertFalse(caught.exception.cache_export_result["completed"])

    def test_mutating_callers_window_cannot_start_work_after_original_cutoff(self):
        self.candidate()
        clock, changed = [10**9], [False]
        def mutate():
            if not changed[0]:
                changed[0] = True
                clock[0] = self.interval["hardEndNs"]
                self.interval["hardEndNs"] += 120 * 10**9
                self.interval["softEndNs"] = clock[0] + 60 * 10**9
        with self.assertRaises(S.SeedError):
            self.export(now=lambda: clock[0], check=mutate)
        self.assertEqual(list(self.fixture.source.iterdir()), [], "No copy may start after the original cutoff")

    def test_mutating_callers_plan_cannot_redirect_original_snapshot_paths(self):
        self.candidate()
        original_plan = copy.deepcopy(self.plan)
        foreign = self.fixture.path / "unrelated-stage"
        foreign.mkdir(mode=0o700)
        def mutate():
            self.plan["restoreHome"] = str(foreign)
        result = self.export(check=mutate)
        self.plan = original_plan
        self.validate(result)
        self.assertEqual(result["restoreHome"], str(self.fixture.source))
        self.assertEqual(list(foreign.iterdir()), [])

    def test_late_final_close_cannot_publish_a_completed_snapshot(self):
        self.candidate()
        clock = [10**9]
        original = S._Owners.close
        def late(owners):
            original(owners)
            clock[0] = self.interval["hardEndNs"]
        with patch.object(S._Owners, "close", late):
            with self.assertRaisesRegex(S.SeedError, "ORIGINAL_HARD_DEADLINE") as caught:
                self.export(now=lambda: clock[0])
        self.assertFalse(caught.exception.cache_export_result["completed"])
        self.assertEqual(caught.exception.cache_export_result["status"], "FAILED")
        self.fixture.assert_known_closed()

    def test_first_copy_failure_and_secondary_close_keep_sticky_unknown(self):
        self.candidate()
        original, failure = S.PosixFile.close, OSError("synthetic primary sync failure")
        def fail_close(stream):
            selected = stream.writable and not stream.closed
            original(stream)
            if selected:
                raise OSError("synthetic close uncertainty after actual fixture close")
        with patch.object(S.PosixFile, "sync", side_effect=failure), patch.object(S.PosixFile, "close", fail_close):
            with self.assertRaises(OSError) as caught:
                self.export()
        self.assertIs(caught.exception, failure)
        self.assertIs(self.fixture.owner.original, failure)
        self.assertTrue(self.fixture.owner.unknown)
        result = failure.cache_export_result
        self.assertEqual((result["status"], result["retirement"], result["completed"]), ("UNKNOWN", "UNKNOWN", False))
        self.assertEqual(result["admitted"], [])
        self.assertTrue(getattr(failure, "__notes__", ()))

    def test_readback_corruption_never_admits_exported_bytes(self):
        self.candidate()
        original = S.PosixFile.close
        def corrupt(stream):
            selected = stream.writable and not stream.closed
            original(stream)
            if selected:
                stream.path.write_bytes(b"x" * stream.path.stat().st_size)
        with patch.object(S.PosixFile, "close", corrupt):
            with self.assertRaises(S.SeedError) as caught:
                self.export()
        self.assertEqual(caught.exception.cache_export_result["admitted"], [])
        self.assertFalse(caught.exception.cache_export_result["completed"])

    def test_retained_receipt_rejects_wrong_roots_source_counts_and_status(self):
        self.candidate()
        result = self.export()
        mutations = [lambda v: v.update(schema=True), lambda v: v.update(scope="DEPENDENCY_SEED_FILE_CUSTODY_V1"),
                     lambda v: v.update(planSha256="0" * 64), lambda v: v.update(seedManifestSha256="0" * 64),
                     lambda v: v.update(sourceIdentity=v["destinationIdentity"]),
                     lambda v: v.update(destinationIdentity=v["sourceIdentity"]),
                     lambda v: v.update(completed=False), lambda v: v.update(retirement="UNKNOWN"),
                     lambda v: v.update(status="KNOWN_EMPTY"), lambda v: v["counts"].update(outputBytes=0),
                     lambda v: v["counts"].update(destinationMembers=0),
                     lambda v: v["admitted"][0].update(path="credentials/key"),
                     lambda v: v["window"].update(finishedNs=v["window"]["hardEndNs"])]
        for mutate in mutations:
            changed = copy.deepcopy(result)
            mutate(changed)
            with self.assertRaises(S.SeedError):
                self.validate(changed)

    def test_receipt_validation_is_not_a_later_live_cache_content_check(self):
        self.candidate()
        result = self.export()
        (self.fixture.source / result["admitted"][0]["path"]).write_bytes(b"later change")
        self.assertEqual(self.validate(result), result)
        # Provider integration must separately reopen the frozen snapshot before
        # save. Original receipt semantics cannot authorize changed live bytes.

    def test_full_export_interval_retains_original_raw_cutoff(self):
        context = {"profile": "full", "jobBudgetSha256": "a" * 64,
                   "primaryAbiAccounting": {"productiveCutoffRawNs": 30 * 10**9}}
        interval = S.window(10**9, 30 * 10**9, 20 * 10**9, raw=True, job_budget="a" * 64)
        K._interval(interval, context, finished=False)
        for changes in ({"hardEndNs": 31 * 10**9}, {"jobBudgetSha256": "b" * 64},
                        {"clock": "process-monotonic-ns"}, {"finishedNs": 20 * 10**9}):
            with self.assertRaises(S.SeedError):
                K._interval({**interval, **changes}, context, finished=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
