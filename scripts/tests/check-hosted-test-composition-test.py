#!/usr/bin/env python3
"""AST-only composition mutations. No supplier imports, children or build tools."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ordinary_composition_policy", ROOT / "scripts/check-hosted-test-composition.py")
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


class CompositionPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = POLICY.read_sources(ROOT)

    def mutate(self, path, before, after):
        original = self.sources[path]
        self.assertIn(before, original, "mutation must target real executable source")
        changed = dict(self.sources)
        changed[path] = original.replace(before, after, 1)
        with self.assertRaisesRegex(ValueError, "ordinary executable composition changed: " + path):
            POLICY.check_sources(changed)

    def test_reviewed_programs_match(self):
        POLICY.check_sources(self.sources)

    def test_missing_program_cannot_pass(self):
        for path in self.sources:
            with self.subTest(path=path):
                changed = dict(self.sources)
                del changed[path]
                with self.assertRaisesRegex(ValueError, "input roster differs"):
                    POLICY.check_sources(changed)

    def test_comment_or_echo_cannot_replace_real_full_dispatch(self):
        path = "scripts/run-hosted-test-custody.py"
        self.mutate(path, b'return "command", ["python3", "scripts/run-platform-tests.py", "full"]',
                    b'return "command", ["echo", "python3 scripts/run-platform-tests.py full"]')
        self.mutate(path, b'controller.full.run()', b'pass # controller.full.run()')

    def test_required_module_selector_is_not_root_check_or_subset(self):
        self.mutate("scripts/run-platform-tests.py", b'"full": ["check"]', b'"full": [":check"]')
        self.mutate("scripts/run-platform-tests.py", b'process = subprocess.Popen(command, cwd=ROOT, start_new_session=True)',
                    b'process = subprocess.Popen(["echo", *command], cwd=ROOT, start_new_session=True)')

    def test_all_ordinary_desktop_tasks_remain_selected(self):
        for before in (b'":p2p-sample-desktop:check"', b'":p2p-sample-desktop-ui:test"',
                       b'":p2p-sample-android:assembleDebug"', b'":p2p-sample-desktop-ui:packageMsi"'):
            with self.subTest(task=before):
                self.mutate("scripts/run-hosted-test-custody.py", before, b'":p2p-sample-desktop:classes"')

    def test_eight_abi_roles_and_three_android_comparisons_remain_required(self):
        path = "scripts/hosted_primary_abi.py"
        for before, after in ((b'"androidAbi/p2p-core.api"', b'"androidAbi/copied-baseline.api"'),
                              (b'"checkAndroidAbi"', b'"checkKotlinAbi"'),
                              (b'"abi/p2p-core.klib.api"', b'"abi/omitted.api"'),
                              (b'"abi/p2p-transport-lan.klib.api"', b'"abi/omitted.api"')):
            with self.subTest(role=before):
                self.mutate(path, before, after)

    def test_additive_aggregate_must_not_be_replaced_with_equal_baseline(self):
        self.mutate("scripts/hosted_primary_abi.py", b'def additive(raw):', b'def ignored_additive(raw):')

    def test_all_eleven_supplements_and_unflagged_graph_are_reachable(self):
        path = "scripts/hosted_full_supplements.py"
        self.mutate(path, b'("command", ["bash", "scripts/check-android-abi-guard.sh"])',
                    b'("command", ["bash", "scripts/check-android-abi-guard.sh", "--static-only"])')
        for name in (b'"lock-policy"', b'"ios-project-generation"', b'"dokka-sbom"', b'"sbom"',
                     b'"published-consumers"', b'"publication-shape"', b'"xcframework-build"',
                     b'"xcframework-minimum-os"', b'"swift-ui"', b'"central-bundle"'):
            with self.subTest(scope=name):
                self.mutate(path, name, b'"omitted"')

    def test_retention_order_sidecars_and_same_home_stop_cannot_be_suppressed(self):
        self.mutate("scripts/run-hosted-test-custody.py", b'controller.retain_primary_abi(mode="productive")', b'pass')
        self.mutate("scripts/hosted_full_supplements.py", b'"BUILD_ARTIFACTS_SHA256.txt"', b'"lost.txt"')
        self.mutate("scripts/hosted_full_supplements.py", b'def verify_swift(', b'def ignored_verify_swift(')
        self.mutate("scripts/hosted_full_supplements.py", b'def verify_central_screen(', b'def ignored_verify_central_screen(')
        self.mutate("scripts/run-platform-tests.py", b'stop_code = stop_gradle()', b'stop_code = 0')

    def test_success_labels_and_separate_seal_do_not_replace_real_outcomes(self):
        self.mutate("scripts/run-hosted-test-custody.py", b'passed = profile_passed(result)', b'passed = True')
        self.mutate("scripts/run-hosted-test-custody.py", b'guarded_operation(validate_public, args.profile)', b'print("PASS")')
        self.mutate("scripts/run-hosted-test-custody.py", b'guarded_operation(upload_guard, args.phase, args.profile)',
                    b'print("PASS")')

    def test_consume_packaging_and_original_clock_edges_remain_reachable(self):
        path = "scripts/run-hosted-test-custody.py"
        self.mutate(path, b'adopt_preparation(self)', b'pass')
        self.mutate(path, b'controller.package_samples()', b'pass')
        self.mutate(path, b'frozen_consume_packet(owner, private, end, check_crypto)', b'None')
        self.mutate(path, b'timing = original_clock(budget, self.last_raw)', b'timing = original_clock(budget)')

    def test_cache_stop_and_resource_boundaries_are_not_relaxed(self):
        self.mutate("scripts/run-audit-command.py", b'"org.gradle.workers.max=2"', b'"org.gradle.workers.max=8"')
        self.mutate("scripts/run-audit-command.py", b'"--no-build-cache"', b'"--build-cache"')
        self.mutate("scripts/hosted_dependency_seed_files.py", b'def seed_home(', b'def unverified_seed_home(')

    def test_shared_helper_is_an_additional_required_program_not_a_replacement(self):
        self.assertEqual(set(POLICY.EXPECTED), {
            "scripts/run-hosted-test-custody.py", "scripts/hosted_full_supplements.py",
            "scripts/hosted_primary_abi.py", "scripts/run-platform-tests.py",
            "scripts/run-audit-command.py", "scripts/hosted_dependency_seed_files.py",
            "scripts/hosted_canonical_python.py",
        })

    def test_shared_argv_and_isolated_two_supplier_loader_cannot_change(self):
        path = "scripts/hosted_canonical_python.py"
        for before, after in (
            (b'"-I", "-B", "-S", "-c"', b'"-B", "-S", "-c"'),
            (b'CANONICAL_NAMES = ("audit_processes.py", "run-audit-command.py")',
             b'CANONICAL_NAMES = ("audit_processes.py", "run-audit-command.py", "foreign.py")'),
            (b'sys.flags.isolated == 1', b'sys.flags.isolated == 0'),
            (b'hashlib.sha256(raw).hexdigest() == bindings[name]', b'True'),
            (b'compile(raw, str(path), "exec", dont_inherit=True)',
             b'compile(path.read_bytes(), str(path), "exec", dont_inherit=True)'),
        ):
            with self.subTest(before=before):
                self.mutate(path, before, after)

    def test_ordinary_capture_hash_guard_and_seed_provenance_cannot_be_removed(self):
        path = "scripts/run-hosted-test-custody.py"
        self.mutate(path, b'hashlib.sha256(raw).hexdigest() == _CANONICAL_HELPER_SHA256', b'True')
        self.mutate(path, b'_CANONICAL_HELPER = _load_canonical_helper()', b'_CANONICAL_HELPER = {}')
        self.mutate(path, b'exec(compile(raw, str(path), "exec", dont_inherit=True), namespace)',
                    b'exec(compile(path.read_bytes(), str(path), "exec", dont_inherit=True), namespace)')
        self.mutate("scripts/hosted_dependency_seed_files.py", b', "scripts/hosted_canonical_python.py"', b'')

    def test_late_shared_helper_shadowing_is_rejected(self):
        changed = dict(self.sources)
        path = "scripts/hosted_canonical_python.py"
        changed[path] += b'\nassemble = lambda *args: ["unbound-python", "foreign.py"]\n'
        with self.assertRaisesRegex(ValueError, "ordinary executable composition changed: " + path):
            POLICY.check_sources(changed)

    def test_late_program_shadowing_is_rejected(self):
        changed = dict(self.sources)
        path = "scripts/run-hosted-test-custody.py"
        changed[path] += b'\nprofile_passed = lambda value: True\n'
        with self.assertRaisesRegex(ValueError, "ordinary executable composition changed: " + path):
            POLICY.check_sources(changed)

    def test_comments_locations_line_endings_do_not_claim_semantic_changes(self):
        changed = {name: b'# comment only\n\n' + raw.replace(b'\n', b'\r\n') for name, raw in self.sources.items()}
        POLICY.check_sources(changed)

    def test_python39_and_python312_empty_type_parameter_fields_match(self):
        old = ast.parse('def a(x):\n    return x\n')
        new = ast.parse('def a(x):\n    return x\n')
        fn = new.body[0]
        if "type_params" not in fn._fields:
            fn._fields = (*fn._fields, "type_params")
        fn.type_params = []
        self.assertEqual(POLICY.structure(old), POLICY.structure(new))
        fn.type_params = [ast.Name(id="Added", ctx=ast.Load())]
        self.assertNotEqual(POLICY.structure(old), POLICY.structure(new))

    def test_missing_oversized_and_malformed_source_is_rejected(self):
        path = "scripts/run-hosted-test-custody.py"
        for raw in (b'', b'x' * (POLICY.LIMIT + 1), b'def broken(', b'\xff'):
            with self.subTest(size=len(raw)):
                changed = dict(self.sources)
                changed[path] = raw
                with self.assertRaises((ValueError, SyntaxError)):
                    POLICY.check_sources(changed)


if __name__ == "__main__":
    unittest.main()
