#!/usr/bin/env python3
"""Pure fixed-input controls; no provider/runtime credentials or source download."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path, PureWindowsPath
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_dependency_cache as K
import hosted_dependency_seed_files as S

SPEC = importlib.util.spec_from_file_location("cohort_models",
    ROOT / "scripts/tests/hosted-cache-bootstrap-cohort-test.py")
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


class ProviderContract(unittest.TestCase):
    def setUp(self):
        # Actual pure admission/plan decisions over maintained synthetic models;
        # no earlier fixture suite or hosted identity is executed/established.
        self.fixture = F.BootstrapCohort()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.plan = self.fixture.plan()

    def contract(self, phase="save", plan=None):
        return K.bootstrap_provider_contract(self.plan if plan is None else plan, phase)

    def test_exact_descriptor_and_input_rosters_for_six_cohorts(self):
        for row in F.I.SELECTIONS:
            self.fixture.configure(row)
            plan = self.fixture.plan()
            for phase in ("save", "lookup"):
                with self.subTest(selection=row[0], phase=phase):
                    value = self.contract(phase, plan)
                    self.assertEqual(set(value), {"request", "inputs", "bundle"})
                    request = {"action": plan["provider"]["save" if phase == "save" else "restore"],
                        "path": plan["path"], "key": plan["key"], "enableCrossOsArchive": False,
                        "scope": "PRIVATE_DESCRIPTOR_NOT_EXECUTION"}
                    inputs = {"INPUT_KEY": plan["key"], "INPUT_PATH": plan["path"],
                              "INPUT_ENABLECROSSOSARCHIVE": "false"}
                    if phase == "lookup":
                        request.update(lookupOnly=True, restoreKeys=[], failOnCacheMiss=True)
                        inputs.update({"INPUT_RESTORE-KEYS": "", "INPUT_FAIL-ON-CACHE-MISS": "true",
                                       "INPUT_LOOKUP-ONLY": "true"})
                    # Independently spelled old descriptors must remain exact.
                    self.assertEqual(S.encoded(value["request"]), S.encoded(request))
                    self.assertEqual(value["inputs"], inputs)

    def test_lookup_cannot_become_restore_through_miss_or_misspelled_flags(self):
        inputs = self.contract("lookup")["inputs"]
        self.assertEqual(inputs["INPUT_LOOKUP-ONLY"], "true")
        self.assertEqual(inputs["INPUT_FAIL-ON-CACHE-MISS"], "true")
        self.assertEqual(inputs["INPUT_RESTORE-KEYS"], "")
        for key in ("INPUT_LOOKUP_ONLY", "INPUT_FAIL_ON_CACHE_MISS", "INPUT_RESTORE_KEYS",
                    "INPUT_UPLOAD-CHUNK-SIZE", "STATE_CACHE_KEY", "STATE_CACHE_RESULT"):
            self.assertNotIn(key, inputs)

    def test_only_closed_bootstrap_phases_and_mode_are_admitted(self):
        for phase in (None, True, [], "", "restore", "probe", "SAVE", "save "):
            with self.subTest(phase=phase), self.assertRaisesRegex(S.SeedError, "PROVIDER_PHASE"):
                self.contract(phase)
        plan = {**self.plan, "mode": "consume"}
        for phase in ("save", "lookup"):
            with self.assertRaisesRegex(S.SeedError, "PROVIDER_MODE"):
                self.contract(phase, plan)

    def test_pinned_bundle_metadata_is_exact_and_separate_per_phase(self):
        pin = "caa296126883cff596d87d8935842f9db880ef25"
        for phase, entry, size, digest in (
            ("save", "save-only", 3202441, "7fb63f90f06ce6a10f39d40a113f99791bffdedad5394cdad5b4dfaa644559cb"),
            ("lookup", "restore-only", 3202022, "6255afaa3956351b8cfefc1e82f026b4db418a10678a8eaddf3d6c55f81744de"),
        ):
            with self.subTest(phase=phase):
                self.assertEqual(self.contract(phase)["bundle"], {
                    "url": "https://raw.githubusercontent.com/actions/cache/" + pin + "/dist/" + entry + "/index.js",
                    "bytes": size, "sha256": digest, "basename": "provider.cjs"})

    def test_changed_action_pin_cannot_keep_old_bundle_metadata(self):
        with patch.object(K, "ACTION_PIN", "1" * 40):
            plan = copy.deepcopy(self.plan)
            plan["provider"] = K._provider()
            with self.assertRaisesRegex(S.SeedError, "BUNDLE_PIN"):
                self.contract(plan=plan)

    def test_original_plan_provider_key_and_shape_guards_remain_required(self):
        for change in ({"extra": "forbidden"}, {"key": self.plan["key"] + "\nsecond-key"},
                       {"role": "linux-arm64"}, {"schema": True}):
            with self.subTest(change=tuple(change)), self.assertRaises(S.SeedError):
                self.contract(plan={**self.plan, **change})
        for name, value in (("restoreKeys", ["fallback"]), ("enableCrossOsArchive", True),
                            ("save", "actions/cache/save@main")):
            plan = copy.deepcopy(self.plan)
            plan["provider"][name] = value
            with self.subTest(name=name), self.assertRaises(S.SeedError):
                self.contract(plan=plan)

    def test_path_and_home_must_be_exact_same_cohort_and_filestore(self):
        for name, value in (("path", self.plan["path"] + "/extra"),
                            ("path", self.plan["path"].replace("files-2.1", "files-2.2")),
                            ("restoreHome", self.plan["restoreHome"] + "-elsewhere")):
            with self.subTest(name=name), self.assertRaisesRegex(S.SeedError, "PATH_BINDING"):
                self.contract(plan={**self.plan, name: value})
        plan = copy.deepcopy(self.plan)
        for name in ("restoreHome", "path"):
            plan[name] = plan[name].replace("p2pkit-dependency-seed-desktop-", "p2pkit-dependency-seed-full-")
        with self.assertRaisesRegex(S.SeedError, "PATH_BINDING"):
            self.contract(plan=plan)

    def test_no_glob_multiline_control_nonascii_or_normalized_path_aliases(self):
        paths = ("", "relative/path", "/tmp//duplicate", "/tmp/./dot", "/tmp/../parent", "/tmp/ trailing ",
                 "/tmp/ leading/home", "/tmp/tab\t", "/tmp/new\nline", "/tmp/cr\r", "/tmp/nul\0",
                 "/tmp/\x7f", "/tmp/é", "/" + "a" * 4096,
                 *("/tmp/" + char + "/home" for char in "!*?[]{}()"))
        for name in ("restoreHome", "path"):
            for value in (*paths, None, True, [], Path("/tmp/path")):
                with self.subTest(name=name, kind=type(value).__name__), \
                        self.assertRaisesRegex(S.SeedError, "LITERAL_PATH"):
                    self.contract(plan={**self.plan, name: value})

    def test_windows_model_keeps_native_literal_spelling_without_normalization(self):
        self.fixture.runner_temp = PureWindowsPath(r"D:\a\_temp")
        row = next(row for row in F.I.SELECTIONS if row[2] == "windows-x64")
        self.fixture.configure(row)
        with patch.object(K, "Path", PureWindowsPath), patch.object(S, "Path", PureWindowsPath):
            plan = self.fixture.plan()
            value = self.contract("lookup", plan)
            self.assertEqual(value["inputs"]["INPUT_PATH"],
                r"D:\a\_temp\p2pkit-dependency-seed-desktop-windows-x64\restore-home\caches\modules-2\files-2.1")
            for replacement in (plan["path"].replace("\\", "/"), plan["path"].replace("D:", "d:"),
                                plan["path"].replace("caches", "Caches")):
                with self.subTest(replacement=replacement), self.assertRaises(S.SeedError):
                    self.contract(plan={**plan, "path": replacement})
            for replacement in (r"\\server\share\home", r"\\?\D:\home", r"D:relative", r"\relative",
                                r"D:\parent.\home", r"D:\parent:stream\home"):
                with self.subTest(replacement=replacement), self.assertRaisesRegex(S.SeedError, "LITERAL_PATH"):
                    self.contract(plan={**plan, "path": replacement})

    def test_posix_backslash_escape_cannot_change_a_coherent_plans_supplier_target(self):
        self.fixture.runner_temp = Path(r"/model/runner\q")
        self.fixture.configure(F.I.SELECTIONS[0])
        plan = self.fixture.plan()
        self.assertIn("\\", plan["path"])
        for phase in ("save", "lookup"):
            with self.subTest(phase=phase), self.assertRaisesRegex(S.SeedError, "LITERAL_PATH"):
                self.contract(phase, plan)

    def test_posix_double_root_cannot_change_a_coherent_plans_supplier_target(self):
        self.fixture.runner_temp = Path("//model/runner")
        self.fixture.configure(F.I.SELECTIONS[0])
        plan = self.fixture.plan()
        self.assertTrue(plan["path"].startswith("//"))
        for phase in ("save", "lookup"):
            with self.subTest(phase=phase), self.assertRaisesRegex(S.SeedError, "LITERAL_PATH"):
                self.contract(phase, plan)

    def test_fresh_outputs_do_not_mutate_original_or_reuse_a_modified_contract(self):
        original = copy.deepcopy(self.plan)
        first = self.contract("lookup")
        expected = copy.deepcopy(first)
        first["request"]["restoreKeys"].append("fallback")
        first["inputs"]["INPUT_LOOKUP-ONLY"] = "false"
        first["bundle"]["sha256"] = "f" * 64
        self.assertEqual(self.contract("lookup"), expected)
        self.assertEqual(self.plan, original)

    def test_no_ambient_environment_or_caller_environment_is_accepted(self):
        # Values are explicit synthetic sentinels, not credentials/runner identity.
        hostile = {name: "SYNTHETIC_DO_NOT_PROPAGATE" for name in (
            "ACTIONS_RUNTIME_TOKEN", "ACTIONS_CACHE_SERVICE_V2", "ACTIONS_RESULTS_URL", "GITHUB_TOKEN",
            "GITHUB_OUTPUT", "GITHUB_ENV", "NODE_OPTIONS", "HTTP_PROXY", "INPUT_LOOKUP-ONLY",
            "INPUT_RESTORE-KEYS", "INPUT_KEY", "INPUT_PATH", "CACHE_UPLOAD_CONCURRENCY")}
        expected = self.contract("lookup")
        with patch.dict("os.environ", hostile, clear=True):
            self.assertEqual(self.contract("lookup"), expected)
        self.assertNotIn(b"SYNTHETIC_DO_NOT_PROPAGATE", S.encoded(expected))
        with self.assertRaises(TypeError):
            K.bootstrap_provider_contract(self.plan, "lookup", environment=hostile)

    def test_no_io_or_time_supplier_is_used_by_the_contract(self):
        with patch("builtins.open", side_effect=AssertionError("no files")), \
                patch.object(K.time, "monotonic", side_effect=AssertionError("no timing authority")):
            self.contract("save")
            self.contract("lookup")


class RestoreContract(unittest.TestCase):
    """Consume plan models do not manufacture ordinary or Stage2 current."""

    def setUp(self):
        self.fixture = F.BootstrapCohort()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def plan(self, selection):
        self.fixture.configure(selection)
        ordinary = S.encoded({"source": S.record(self.fixture.raw)["source"],
                              "github": {"runId": "123", "runAttempt": "1"}})
        self.fixture.session = self.fixture.runner_temp / (
            "p2pkit-test-" + self.fixture.profile + "-123-1-" + self.fixture.role)
        return self.fixture.plan(self.fixture.stage(ordinary), ordinary, mode="consume")

    def test_six_consume_cohorts_keep_exact_restore_only_inputs_and_path(self):
        for row in F.I.SELECTIONS:
            plan = self.plan(row)
            with self.subTest(selection=row[0]):
                result = K.restore_provider_contract(plan)
                self.assertEqual(result["request"], {
                    "action": "actions/cache/restore@caa296126883cff596d87d8935842f9db880ef25",
                    "path": plan["path"], "key": plan["key"], "enableCrossOsArchive": False,
                    "scope": "PRIVATE_DESCRIPTOR_NOT_EXECUTION", "lookupOnly": False,
                    "restoreKeys": [], "failOnCacheMiss": True})
                self.assertEqual(result["inputs"], {"INPUT_KEY": plan["key"], "INPUT_PATH": plan["path"],
                    "INPUT_ENABLECROSSOSARCHIVE": "false", "INPUT_RESTORE-KEYS": "",
                    "INPUT_FAIL-ON-CACHE-MISS": "true", "INPUT_LOOKUP-ONLY": "false"})
                self.assertEqual(result, K._native_provider_contract(plan, "restore"))
                self.assertEqual(result["bundle"], {
                    "url": "https://raw.githubusercontent.com/actions/cache/" + K.ACTION_PIN +
                           "/dist/restore-only/index.js",
                    "bytes": 3202022, "sha256": "6255afaa3956351b8cfefc1e82f026b4db418a10678a8eaddf3d6c55f81744de",
                    "basename": "provider.cjs"})

    def test_fixed_routes_refuse_bootstrap_restore_and_consume_save_lookup(self):
        bootstrap = self.fixture.plan()
        with self.assertRaisesRegex(S.SeedError, "RESTORE_PROVIDER_MODE"):
            K.restore_provider_contract(bootstrap)
        consume = self.plan(F.I.SELECTIONS[0])
        for phase in ("save", "lookup"):
            with self.subTest(phase=phase), self.assertRaisesRegex(S.SeedError, "BOOTSTRAP_PROVIDER_MODE"):
                K._native_provider_contract(consume, phase)
        for phase in ("RESTORE", "restore ", None, True):
            with self.subTest(phase=phase), self.assertRaises(S.SeedError):
                K._native_provider_contract(consume, phase)

    def test_restore_reuses_exact_plan_pin_path_and_no_fallback_guards(self):
        original = self.plan(F.I.SELECTIONS[0])
        changes = (("provider", {**original["provider"], "restoreKeys": ["fallback"]}),
                   ("provider", {**original["provider"], "restore": "actions/cache/restore@main"}),
                   ("path", original["path"] + "/extra"), ("path", original["path"] + "\nother"),
                   ("extra", True))
        for name, value in changes:
            with self.subTest(name=name), self.assertRaises(S.SeedError):
                K.restore_provider_contract({**original, name: value})
        with patch.object(K, "ACTION_PIN", "1" * 40), self.assertRaises(S.SeedError):
            K.restore_provider_contract(original)

    def test_restore_is_fresh_pure_data_not_environment_clock_or_io_authority(self):
        plan = self.plan(F.I.SELECTIONS[0])
        expected = K.restore_provider_contract(plan)
        changed = K.restore_provider_contract(plan)
        changed["request"]["restoreKeys"].append("MODEL_FORBIDDEN_FALLBACK")
        changed["inputs"]["INPUT_LOOKUP-ONLY"] = "true"
        with patch.dict("os.environ", {"GITHUB_TOKEN": "MODEL_NOT_A_CREDENTIAL"}, clear=True), \
                patch("builtins.open", side_effect=AssertionError("no files")), \
                patch.object(K.time, "monotonic", side_effect=AssertionError("no clock")):
            self.assertEqual(K.restore_provider_contract(plan), expected)
        self.assertEqual(plan["mode"], "consume")


if __name__ == "__main__":
    unittest.main()
