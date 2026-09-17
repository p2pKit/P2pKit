#!/usr/bin/env python3
"""Pure provider declarations and tiny owned files, NOT hosted cache qualification.

No Gradle, action, network, dependency archive, GPG, subprocess or native Windows
provider is executed. Reuse the maintained seed fixture rather than a fake seed
context or a second copier. Its unchanged 33 methods are run separately once.
"""
import copy
from dataclasses import replace
import hashlib
import importlib.util
import os
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


class SaveSet(unittest.TestCase):
    """Tiny real private files; provider and native Windows execution forbidden."""
    def setUp(self):
        self.cache = DependencyCache()
        self.cache.setUp()
        self.fixture = self.cache.fixture

    def tearDown(self):
        self.cache.tearDown()

    def exported(self, rows=None, *, names=None, now=None):
        f = self.fixture
        if rows is not None:
            f.rows = rows
            self.cache.prepare()
        # The actual allocator writes this original beside S, not inside it.
        (f.container / "staging.json").write_bytes(f.staging_raw)
        (f.container / "staging.json").chmod(0o600)
        for name in f.rows if names is None else names:
            self.cache.candidate(name)
        self.exported_value = self.cache.export(now=now)
        self.export_raw = S.encoded(self.exported_value)
        return self.exported_value

    def save(self, *, frozen_raw=None, check=lambda: None, now=None, interval=None):
        f, c = self.fixture, self.cache
        clock = now or time.monotonic_ns
        began = clock()
        self.save_interval = interval or S.window(began, began + 120 * 10**9, began + 90 * 10**9,
                                                  raw=False, job_budget=None)
        return K.save_set(f.owner, c.plan, self.export_raw, f.staging_raw, c.seed_raw, f.context_raw,
                          f.canonical_raw, f.admitted_raw, f.compiled, end=time.monotonic() + 120,
                          check=check, now=clock, interval=self.save_interval, frozen_raw=frozen_raw)

    def validate(self, value, frozen_raw=None):
        f, c = self.fixture, self.cache
        return K.validate_save_set_receipt(value, c.plan, self.export_raw, f.staging_raw, c.seed_raw,
                                           f.context_raw, f.canonical_raw, f.admitted_raw, f.compiled,
                                           frozen_raw=frozen_raw)

    def target(self):
        return self.fixture.source / self.exported_value["admitted"][0]["path"]

    def test_positive_freeze_recheck_is_read_only_and_all_owners_close(self):
        exported = self.exported()
        f = self.fixture
        before = {str(p): (p.read_bytes(), S._info(p.stat())) for p in f.source.rglob("*") if p.is_file()}
        with patch.object(S.PosixPrivateDirectory, "create_file", side_effect=AssertionError("NO_WRITE")), \
                patch.object(S.PosixPrivateDirectory, "create_directory", side_effect=AssertionError("NO_WRITE")), \
                patch.object(S.windows, "Snapshot", side_effect=AssertionError("NO_AGGREGATE_SNAPSHOT")):
            frozen = self.save()
            frozen_raw = S.encoded(frozen)
            checked = self.save(frozen_raw=frozen_raw)
        self.validate(frozen)
        self.validate(checked, frozen_raw)
        self.assertEqual((frozen["status"], checked["status"]), ("KNOWN_FROZEN", "KNOWN_UNCHANGED"))
        self.assertEqual(checked["beforeSaveSha256"], S.digest(frozen_raw))
        self.assertEqual(frozen["counts"], {"hashedBytes": exported["counts"]["outputBytes"],
                                          "verifiedFiles": 1, "members": 8})
        self.assertEqual(before, {str(p): (p.read_bytes(), S._info(p.stat()))
                                  for p in f.source.rglob("*") if p.is_file()})
        self.assertNotEqual(exported["admitted"][0]["source"], exported["admitted"][0]["destination"])
        f.assert_known_closed()

    def test_positive_partial_export_freezes_only_its_complete_admitted_subset(self):
        exported = self.exported({"A": b"one", "B": b"two"}, names=["A"])
        self.assertEqual(exported["status"], "KNOWN_PARTIAL")
        frozen = self.save()
        self.validate(frozen)
        self.assertEqual(frozen["counts"]["verifiedFiles"], 1)
        self.assertEqual(frozen["files"], [exported["admitted"][0]["path"]])

    def test_empty_export_refuses_before_opening_any_live_input(self):
        self.exported(names=[])
        with patch.object(S, "private_root", side_effect=AssertionError("NO_OPEN")):
            with self.assertRaisesRegex(S.SeedError, "POSITIVE_EXPORT_REQUIRED"):
                self.save()

    def test_zero_byte_admitted_export_is_not_positive_save_authority(self):
        self.exported({"FastInfoset": b""})
        with self.assertRaisesRegex(S.SeedError, "POSITIVE_EXPORT_REQUIRED"):
            self.save()

    def test_original_receipt_still_validates_but_changed_live_bytes_refuse(self):
        self.exported()
        self.target().write_bytes(b"x" * self.target().stat().st_size)
        self.cache.validate(self.exported_value)  # Semantics are deliberately not live authority.
        with self.assertRaisesRegex(S.SeedError, "STAMP_CHANGED") as caught:
            self.save()
        self.assertFalse(caught.exception.cache_save_set_result["completed"])
        self.fixture.assert_known_closed()

    def test_equal_byte_inode_replacement_refuses(self):
        self.exported()
        target = self.target()
        raw, identity = target.read_bytes(), target.stat().st_ino
        target.rename(self.fixture.path / "original-file")
        target.write_bytes(raw)
        target.chmod(0o600)
        self.assertNotEqual(identity, target.stat().st_ino)
        with self.assertRaisesRegex(S.SeedError, "STAMP_CHANGED"):
            self.save()

    def test_same_inode_metadata_change_refuses(self):
        self.exported()
        self.target().chmod(0o400)
        with self.assertRaisesRegex(S.SeedError, "STAMP_CHANGED"):
            self.save()

    def test_extra_file_is_rejected_without_opening_it(self):
        self.exported()
        (self.fixture.source / "foreign.log").write_bytes(b"DO NOT READ")
        original, opened = S._PosixDirectory._child, []
        def observe(view, name, **kwargs):
            opened.append(name)
            return original(view, name, **kwargs)
        with patch.object(S._PosixDirectory, "_child", observe):
            with self.assertRaisesRegex(S.SeedError, "MEMBERS_CHANGED"):
                self.save()
        self.assertNotIn("foreign.log", opened)

    def test_extra_empty_directory_at_any_admitted_depth_refuses(self):
        self.exported()
        for parent in (self.fixture.source, self.target().parent):
            unexpected = parent / "unexpected"
            unexpected.mkdir(mode=0o700)
            with self.assertRaisesRegex(S.SeedError, "MEMBERS_CHANGED"):
                self.save()
            unexpected.rmdir()
        self.fixture.assert_known_closed()

    def test_missing_exported_file_refuses(self):
        self.exported()
        self.target().unlink()
        with self.assertRaisesRegex(S.SeedError, "MEMBERS_CHANGED"):
            self.save()

    def test_renamed_exported_file_refuses(self):
        self.exported()
        self.target().rename(self.target().with_name("renamed.jar"))
        with self.assertRaisesRegex(S.SeedError, "MEMBERS_CHANGED"):
            self.save()

    def test_selected_symlink_is_not_followed(self):
        self.exported()
        target = self.target()
        target.unlink()
        target.symlink_to(self.fixture.home / self.exported_value["admitted"][0]["path"])
        with self.assertRaises((OSError, S.SeedError)):
            self.save()

    def test_selected_fifo_refuses_without_waiting_for_a_writer(self):
        self.exported()
        target = self.target()
        target.unlink()
        os.mkfifo(target, 0o600)
        with self.assertRaisesRegex(S.SeedError, "IDENTITY_OR_KIND"):
            self.save()

    def test_selected_hardlink_refuses(self):
        self.exported()
        os.link(self.target(), self.fixture.path / "second-link")
        with self.assertRaisesRegex(S.SeedError, "IDENTITY_OR_KIND"):
            self.save()

    def test_replaced_stage_root_refuses_even_at_the_same_path(self):
        self.exported()
        self.fixture.source.rename(self.fixture.path / "original-stage")
        self.fixture.source.mkdir(mode=0o700)
        with self.assertRaisesRegex(S.SeedError, "STAGE_REPLACED"):
            self.save()

    def test_same_stage_under_replaced_container_refuses(self):
        self.exported()
        f = self.fixture
        prior = self.cache.replace_root(f.container)
        (prior / "restore-home").rename(f.source)
        (prior / "staging.json").rename(f.container / "staging.json")
        with self.assertRaisesRegex(S.SeedError, "CONTAINER_REPLACED"):
            self.save()

    def test_original_staging_file_must_still_have_exact_bytes(self):
        self.exported()
        (self.fixture.container / "staging.json").write_bytes(b"x" * len(self.fixture.staging_raw))
        with self.assertRaisesRegex(S.SeedError, "BYTES_CHANGED"):
            self.save()

    def test_container_may_not_gain_a_sibling_even_outside_saved_prefix(self):
        self.exported()
        (self.fixture.container / "foreign").mkdir(mode=0o700)
        with self.assertRaisesRegex(S.SeedError, "CONTAINER_MEMBERS_CHANGED"):
            self.save()

    def test_after_save_compares_original_directory_stamps_and_members(self):
        self.exported()
        frozen_raw = S.encoded(self.save())
        # No surviving extra member is needed: replacement of an ancestor is
        # still a mutation, even when the original file inode is moved back.
        parent = self.target().parent
        prior = parent.with_name("original-bucket")
        parent.rename(prior)
        parent.mkdir(mode=0o700)
        (prior / self.target().name).rename(self.target())
        prior.rmdir()
        with self.assertRaisesRegex(S.SeedError, "DIRECTORY_STAMP_CHANGED"):
            self.save(frozen_raw=frozen_raw)

    def test_after_save_detects_changed_file_with_unchanged_directory_membership(self):
        self.exported()
        frozen_raw = S.encoded(self.save())
        self.target().write_bytes(b"x" * self.target().stat().st_size)
        with self.assertRaisesRegex(S.SeedError, "STAMP_CHANGED"):
            self.save(frozen_raw=frozen_raw)

    def test_semantically_equal_reencoded_export_is_not_the_frozen_original(self):
        self.exported()
        frozen_raw = S.encoded(self.save())
        self.export_raw = b"\n" + self.export_raw
        self.cache.validate(S.record(self.export_raw))
        with patch.object(S, "private_root", side_effect=AssertionError("NO_OPEN")):
            with self.assertRaisesRegex(S.SeedError, "ORIGINAL_BINDING_CHANGED"):
                self.save(frozen_raw=frozen_raw)

    def test_coherent_context_and_export_rebinding_cannot_replace_frozen_originals(self):
        self.exported()
        frozen_raw = S.encoded(self.save())
        f, c = self.fixture, self.cache
        f.context_raw = b"\n" + f.context_raw
        seed = S.record(c.seed_raw)
        seed["contextSha256"] = S.digest(f.context_raw)
        c.seed_raw = S.encoded(seed)
        exported = S.record(self.export_raw)
        exported["contextSha256"] = S.digest(f.context_raw)
        exported["seedManifestSha256"] = S.digest(c.seed_raw)
        self.export_raw = S.encoded(exported)
        c.validate(exported)  # Coherent replacement alone passes semantic validation.
        with self.assertRaisesRegex(S.SeedError, "ORIGINAL_BINDING_CHANGED"):
            self.save(frozen_raw=frozen_raw)

    def test_coherent_live_file_and_export_replacement_cannot_change_frozen_authority(self):
        self.exported()
        frozen_raw = S.encoded(self.save())
        target = self.target()
        raw = target.read_bytes()
        target.rename(self.fixture.path / "original-file")
        target.write_bytes(raw)
        target.chmod(0o600)
        exported = S.record(self.export_raw)
        exported["admitted"][0]["destination"] = S._info_binding(S._info(target.stat()))
        self.export_raw = S.encoded(exported)
        self.cache.validate(exported)
        with self.assertRaisesRegex(S.SeedError, "ORIGINAL_BINDING_CHANGED"):
            self.save(frozen_raw=frozen_raw)

    def test_frozen_record_requires_exact_roster_counts_and_original_hashes(self):
        self.exported()
        value = self.save()
        mutations = [lambda v: v.update(schema=True), lambda v: v.update(completed=False),
                     lambda v: v.update(retirement="UNKNOWN"), lambda v: v.update(files=[]),
                     lambda v: v["counts"].update(verifiedFiles=0),
                     lambda v: v["counts"].update(hashedBytes=True),
                     lambda v: v["directories"].pop(),
                     lambda v: v["directories"][0]["names"].append("unexpected"),
                     lambda v: v["container"].update(names=["restore-home"]),
                     lambda v: v.update(beforeSaveSha256="a" * 64)]
        mutations += [lambda v, key=key: v["originalsSha256"].update({key: "f" * 64})
                      for key in value["originalsSha256"]]
        for mutate in mutations:
            changed = copy.deepcopy(value)
            mutate(changed)
            with self.assertRaises(S.SeedError):
                self.validate(changed)

    def test_after_result_cannot_be_reused_as_a_new_before_record(self):
        self.exported()
        frozen_raw = S.encoded(self.save())
        after = self.save(frozen_raw=frozen_raw)
        with self.assertRaisesRegex(S.SeedError, "RESULT_NOT_KNOWN"):
            self.save(frozen_raw=S.encoded(after))

    def test_complete_tree_is_freshly_enumerated_on_both_calls(self):
        self.exported()
        original, seen = S._PosixDirectory.names, []
        def listing(directory, **kwargs):
            seen.append(str(directory.path))
            return original(directory, **kwargs)
        with patch.object(S._PosixDirectory, "names", listing), \
                patch.object(S._SourceLookup, "names", side_effect=AssertionError("NO_CACHED_LISTING")):
            frozen = self.save()
            first_seen = list(seen)
            seen.clear()
            self.save(frozen_raw=S.encoded(frozen))
        expected = {str(self.fixture.source / row["path"]) for row in frozen["directories"]}
        self.assertTrue(expected <= set(first_seen) and expected <= set(seen))
        self.assertTrue(all(first_seen.count(name) >= 4 and seen.count(name) >= 4 for name in expected))

    def test_mutation_after_an_early_reader_closes_is_caught_by_final_pass(self):
        self.exported({"A": b"one", "B": b"two"})
        original, changed = S._hash, [False]
        first = self.fixture.source / self.exported_value["admitted"][0]["path"]
        def hashing(reader, *args, **kwargs):
            result = original(reader, *args, **kwargs)
            if reader.path.name == "B.jar" and not changed[0]:
                changed[0] = True
                first.write_bytes(b"xxx")
            return result
        with patch.object(S, "_hash", hashing):
            with self.assertRaisesRegex(S.SeedError, "STAMP_CHANGED"):
                self.save()
        self.assertTrue(changed[0])

    def test_mutation_during_hash_never_publishes_a_partial_success(self):
        self.exported()
        original, changed = S.PosixFile.read, [False]
        def reading(reader, size):
            raw = original(reader, size)
            if reader.path.name.endswith(".jar") and raw and not changed[0]:
                changed[0] = True
                reader.path.write_bytes(b"x" * reader.initial_info.size)
            return raw
        with patch.object(S.PosixFile, "read", reading):
            with self.assertRaises(S.SeedError) as caught:
                self.save()
        self.assertFalse(caught.exception.cache_save_set_result["completed"])

    def test_first_hash_error_survives_unknown_close_and_no_further_acquisition(self):
        self.exported()
        read, close = S.PosixFile.read, S.PosixFile.close
        failure, acquired_after = OSError("synthetic first read error"), []
        def reading(reader, size):
            if reader.path.name.endswith(".jar"):
                raise failure
            return read(reader, size)
        def closing(reader):
            selected = reader.path.name.endswith(".jar") and not reader.closed
            close(reader)
            if selected:
                raise OSError("synthetic close uncertainty after actual fixture close")
        acquire = self.fixture.owner.acquire
        def acquiring(label, factory):
            if self.fixture.owner.unknown:
                acquired_after.append(label)
            return acquire(label, factory)
        with patch.object(S.PosixFile, "read", reading), patch.object(S.PosixFile, "close", closing), \
                patch.object(self.fixture.owner, "acquire", acquiring):
            with self.assertRaises(OSError) as caught:
                self.save()
        self.assertIs(caught.exception, failure)
        self.assertIs(self.fixture.owner.original, failure)
        self.assertTrue(self.fixture.owner.unknown)
        self.assertTrue(getattr(failure, "__notes__", ()))
        self.assertEqual(acquired_after, [])
        self.assertEqual(failure.cache_save_set_result["status"], "UNKNOWN")

    def test_nested_directory_error_precedes_secondary_close_in_owner_ledger(self):
        self.exported()
        target = self.target().parent
        failure = OSError("synthetic first directory enumeration error")
        secondary = OSError("synthetic close uncertainty after actual fixture close")
        names, close = S._PosixDirectory.names, S._PosixDirectory.close
        def listing(directory, **kwargs):
            if directory.path == target:
                raise failure
            return names(directory, **kwargs)
        def closing(directory):
            selected = directory.path == target and not directory.closed
            close(directory)
            if selected:
                raise secondary
        with patch.object(S._PosixDirectory, "names", listing), patch.object(S._PosixDirectory, "close", closing):
            with self.assertRaises(OSError) as caught:
                self.save()
        self.assertIs(caught.exception, failure)
        self.assertIs(self.fixture.owner.original, failure)
        self.assertTrue(self.fixture.owner.unknown)
        self.assertTrue(getattr(failure, "__notes__", ()))
        self.assertEqual(failure.cache_save_set_result["status"], "UNKNOWN")

    def test_nested_cursor_unknown_is_recorded_before_any_parent_close(self):
        self.exported()
        target = self.target().parent
        failure = OSError("synthetic directory cursor uncertainty")
        S._note(failure, "directory-cursor", OSError("synthetic uncertain cursor close"))
        names, close = S._PosixDirectory.names, self.fixture.owner.close_one
        uncertain, closes = [False], []
        def listing(directory, **kwargs):
            result = names(directory, **kwargs)
            if directory.path == target:
                uncertain[0] = True
                raise failure
            return result
        def closing(resource):
            if uncertain[0]:
                closes.append(resource.path)
            return close(resource)
        with patch.object(S._PosixDirectory, "names", listing), patch.object(self.fixture.owner, "close_one", closing):
            with self.assertRaises(OSError) as caught:
                self.save()
        self.assertIs(caught.exception, failure)
        self.assertIs(self.fixture.owner.original, failure)
        self.assertTrue(self.fixture.owner.unknown)
        self.assertEqual(closes, [], "Nested finalizers must not retire owners after cursor uncertainty")
        self.assertEqual(failure.cache_save_set_result["status"], "UNKNOWN")

    def test_backward_reading_above_start_is_still_rejected(self):
        self.exported(now=lambda: 10**9)
        clock = iter((2 * 10**9, 4 * 10**9, 3 * 10**9))
        with self.assertRaisesRegex(S.SeedError, "CLOCK_OR_HARD_DEADLINE"):
            self.save(now=lambda: next(clock))
        self.fixture.assert_known_closed()

    def test_window_cannot_precede_export_or_frozen_predecessor(self):
        self.exported(now=lambda: 10**9)
        with self.assertRaisesRegex(S.SeedError, "PRECEDES_EXPORT"):
            self.save(now=lambda: 10**9 - 1)
        frozen_raw = S.encoded(self.save(now=lambda: 3 * 10**9))
        with self.assertRaisesRegex(S.SeedError, "PRECEDES_FROZEN_OBSERVATION"):
            self.save(frozen_raw=frozen_raw, now=lambda: 2 * 10**9)

    def test_first_observation_below_admitted_start_is_rejected_before_open(self):
        self.exported(now=lambda: 10**9)
        interval = S.window(3 * 10**9, 123 * 10**9, 93 * 10**9, raw=False, job_budget=None)
        with patch.object(S, "private_root", side_effect=AssertionError("NO_OPEN")):
            with self.assertRaisesRegex(S.SeedError, "CLOCK_OR_HARD_DEADLINE"):
                self.save(now=lambda: 2 * 10**9, interval=interval)

    def test_soft_cutoff_does_not_return_a_partially_verified_save_set(self):
        self.exported({"A": b"one", "B": b"two"}, now=lambda: 10**9)
        clock, original = [2 * 10**9], S._hash
        def hashing(reader, *args, **kwargs):
            answer = original(reader, *args, **kwargs)
            if reader.path.name == "A.jar":
                clock[0] = self.save_interval["softEndNs"]
            return answer
        with patch.object(S, "_hash", hashing):
            with self.assertRaisesRegex(S.SeedError, "NEW_WORK_CUTOFF") as caught:
                self.save(now=lambda: clock[0])
        result = caught.exception.cache_save_set_result
        self.assertFalse(result["completed"])
        self.assertEqual(result["counts"]["verifiedFiles"], 1)
        self.fixture.assert_known_closed()

    def test_late_final_close_cannot_publish_success(self):
        self.exported(now=lambda: 10**9)
        clock, original = [2 * 10**9], S._Owners.close
        def closing(owners):
            original(owners)
            clock[0] = self.save_interval["hardEndNs"]
        with patch.object(S._Owners, "close", closing):
            with self.assertRaisesRegex(S.SeedError, "CLOCK_OR_HARD_DEADLINE") as caught:
                self.save(now=lambda: clock[0])
        self.assertFalse(caught.exception.cache_save_set_result["completed"])
        self.fixture.assert_known_closed()

    def test_final_validation_cannot_hide_expiry_and_retains_last_high_water(self):
        self.exported(now=lambda: 10**9)
        clock, original = [2 * 10**9], K._validate_save_set
        def validating(*args, **kwargs):
            answer = original(*args, **kwargs)
            clock[0] += 10**9
            return answer
        with patch.object(K, "_validate_save_set", validating):
            value = self.save(now=lambda: clock[0])
        self.assertEqual(value["window"]["finishedNs"], 3 * 10**9)
        def expired(*args, **kwargs):
            answer = original(*args, **kwargs)
            clock[0] = self.save_interval["hardEndNs"]
            return answer
        with patch.object(K, "_validate_save_set", expired):
            with self.assertRaisesRegex(S.SeedError, "CLOCK_OR_HARD_DEADLINE"):
                self.save(now=lambda: clock[0])

    def test_callbacks_cannot_redirect_caller_plan_or_extend_original_window(self):
        self.exported(now=lambda: 10**9)
        clock, changed = [2 * 10**9], [False]
        def mutate():
            if not changed[0]:
                changed[0] = True
                clock[0] = self.save_interval["hardEndNs"]
                self.save_interval["hardEndNs"] += 120 * 10**9
                self.save_interval["softEndNs"] = clock[0] + 60 * 10**9
                self.cache.plan["restoreHome"] = str(self.fixture.path / "unrelated")
        with patch.object(S, "private_root", side_effect=AssertionError("NO_OPEN")):
            with self.assertRaisesRegex(S.SeedError, "CLOCK_OR_HARD_DEADLINE"):
                self.save(check=mutate, now=lambda: clock[0])

    def test_plan_mutation_alone_cannot_redirect_a_live_inspection(self):
        self.exported()
        original = copy.deepcopy(self.cache.plan)
        foreign = self.fixture.path / "unrelated"
        foreign.mkdir(mode=0o700)
        def mutate():
            self.cache.plan["restoreHome"] = str(foreign)
        value = self.save(check=mutate)
        self.cache.plan = original
        self.validate(value)
        self.assertEqual(value["restoreHome"], str(self.fixture.source))
        self.assertEqual(list(foreign.iterdir()), [])

    def test_prior_unknown_cannot_acquire_any_input(self):
        self.exported()
        self.fixture.owner.unknown = True
        with patch.object(S, "private_root", side_effect=AssertionError("NO_OPEN")):
            with self.assertRaisesRegex(S.SeedError, "RETIREMENT_UNKNOWN") as caught:
                self.save()
        self.assertEqual(caught.exception.cache_save_set_result["status"], "UNKNOWN")

    def test_cancellation_preserves_first_failure_and_closes_owned_inputs(self):
        self.exported()
        failure, calls = KeyboardInterrupt("synthetic cancellation"), [0]
        def cancel():
            calls[0] += 1
            if calls[0] == 5:
                raise failure
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.save(check=cancel)
        self.assertIs(caught.exception, failure)
        self.assertFalse(failure.cache_save_set_result["completed"])
        self.fixture.assert_known_closed()

    def test_streaming_read_and_live_owner_counts_stay_bounded(self):
        self.exported({"Artifact" + str(i): b"tiny" for i in range(12)})
        original_read, original_acquire = S.PosixFile.read, self.fixture.owner.acquire
        maximum, blocks = [0], []
        def reading(reader, size):
            self.assertTrue(0 <= size <= S.BLOCK)
            blocks.append(size)
            return original_read(reader, size)
        def acquiring(label, factory):
            result = original_acquire(label, factory)
            maximum[0] = max(maximum[0], sum(not row["closed"] for row in self.fixture.owner.resources))
            return result
        with patch.object(S.PosixFile, "read", reading), patch.object(self.fixture.owner, "acquire", acquiring):
            result = self.save()
        self.assertEqual(result["counts"]["verifiedFiles"], 12)
        self.assertTrue(blocks)
        self.assertLessEqual(maximum[0], 10)
        self.fixture.assert_known_closed()

    def test_oversized_receipt_is_rejected_before_any_live_open(self):
        self.exported()
        self.export_raw += b" " * S.RECEIPT_LIMIT
        with patch.object(S, "private_root", side_effect=AssertionError("NO_OPEN")):
            with self.assertRaisesRegex(S.SeedError, "RECORD_BYTES"):
                self.save()

    def test_native_identity_stamps_use_all_metadata_but_not_access_time(self):
        # Supplier semantics only, not execution of Windows native APIs.
        info = S.windows.FileInfo((12, "a" * 32), False, 300, 1, 0, 1, 2, 3, "SID", True)
        binding = S._info_binding(info)
        self.assertNotIn("accessed", info.as_dict())
        self.assertNotEqual(binding, S._info_binding(replace(info, change_100ns=4)))
        self.assertNotEqual(binding, S._info_binding(replace(info, protected_dacl=False)))
        self.assertEqual(binding["identity"], [12, "a" * 32])

    def test_above_windows_snapshot_limit_uses_streaming_accounting_not_snapshot(self):
        # Declared-size model with real tiny owners: NO 600MiB allocation/read.
        self.exported({"A": b"one", "B": b"two"})
        exported, size = S.record(self.export_raw), 300 * S.MIB
        by_name = {}
        for row in exported["admitted"]:
            row["size"] = size
            info = replace(S._info((self.fixture.source / row["path"]).stat()), size=size)
            row["destination"] = S._info_binding(info)
            by_name[Path(row["path"]).name] = (row, info)
        exported["counts"].update(prehashBytes=2 * size, outputBytes=2 * size)
        self.export_raw = S.encoded(exported)
        original_open, original_hash = S.PosixPrivateDirectory.open_file, S._hash
        class DeclaredSizeReader:
            def __init__(self, delegate, info):
                self.delegate, self.initial_info = delegate, info
                self.path, self.identity = delegate.path, delegate.identity
            def verify(self):
                self.delegate.verify()
                return self.initial_info
            def close(self):
                self.delegate.close()
        def opening(directory, name, **kwargs):
            reader = original_open(directory, name, **kwargs)
            return DeclaredSizeReader(reader, by_name[name][1]) if name in by_name else reader
        def hashing(reader, count, check, writer=None):
            if reader.path.name not in by_name:
                return original_hash(reader, count, check, writer)
            self.assertIsNone(writer)
            self.assertEqual(count, size)
            check()
            row = by_name[reader.path.name][0]
            return row["sha256"], row["sha1"]
        with patch.object(S.PosixPrivateDirectory, "open_file", opening), patch.object(S, "_hash", hashing), \
                patch.object(S.windows, "Snapshot", side_effect=AssertionError("NO_AGGREGATE_SNAPSHOT")):
            result = self.save()
        self.assertEqual(result["counts"]["hashedBytes"], 600 * S.MIB)
        self.fixture.assert_known_closed()


if __name__ == "__main__":
    unittest.main(verbosity=2)
