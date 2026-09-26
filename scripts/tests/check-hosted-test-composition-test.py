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

    def test_schema3_source_version_inspection_and_known_close_cannot_be_removed(self):
        path = "scripts/run-hosted-test-custody.py"
        for before, after in (
            (b'manifest["schema"] == 3', b'manifest["schema"] == 2'),
            (b'\n        sample_manifest_identity(manifest, kind, current, versions)', b'\n        pass'),
            (b'properties = seed._small_read(version_owners, version_source, "gradle.properties", end, 65536, check)',
             b'properties = b"VERSION_NAME=0.8.0-rc1\\n"'),
            (b'require(seed._small_read(version_owners, version_source, "gradle.properties", end, 65536, check) == properties,',
             b'require(True,'),
            (b'version_owners.close()', b'pass'),
            (b'sample_native_metadata(row["nativeMetadata"], platform, versions, source["commit"])', b'pass'),
            (b'sample_embedded_identity(apk["embeddedIdentity"], versions, commit)', b'pass'),
        ):
            with self.subTest(before=before):
                self.assertEqual(self.sources[path].count(before), 1, "schema3 mutation must target one executable site")
                self.mutate(path, before, after)

    def test_cache_stop_and_resource_boundaries_are_not_relaxed(self):
        self.mutate("scripts/run-audit-command.py", b'"org.gradle.workers.max=2"', b'"org.gradle.workers.max=8"')
        self.mutate("scripts/run-audit-command.py", b'"--no-build-cache"', b'"--build-cache"')
        self.mutate("scripts/hosted_dependency_seed_files.py", b'def seed_home(', b'def unverified_seed_home(')

    def test_canonical_capture_cap_read_contract_and_prefix_accounting_are_required(self):
        path = "scripts/run-audit-command.py"
        for before, after in (
            (b'MAX_STREAM_BYTES = 64 * 1024 * 1024', b'MAX_STREAM_BYTES = 128 * 1024 * 1024'),
            (b'block = self.source.read(65536)', b'block = self.source.read(min(65536, remaining))'),
            (b'type(block) is bytes and len(block) <= 65536', b'True'),
            (b'if retained < len(block) and not overflow:', b'if False:'),
            (b'remaining -= retained', b'remaining = MAX_STREAM_BYTES'),
            (b'block = block[:retained]', b'pass # retain the unbounded original instead'),
        ):
            with self.subTest(before=before):
                self.mutate(path, before, after)

    def test_canonical_capture_both_write_acknowledgements_remain_required(self):
        path = "scripts/run-audit-command.py"
        for sink in (b'Evidence', b'Product'):
            with self.subTest(sink=sink):
                before = (b'require(type(written) is int and written == len(block), "' +
                          sink + b' stream write acknowledgement differs")')
                self.mutate(path, before, b'pass # unchecked write acknowledgement')

    def test_canonical_capture_product_error_polling_keeps_stop_separate(self):
        path = "scripts/run-audit-command.py"
        for before, after in (
            (b'wait_process(scope, child, product_timeout, cancelled, check_product,',
             b'wait_process(scope, child, product_timeout, cancelled, check_cancel,'),
            (b'wait_process(scope, stop_child, stop_timeout, cancelled, check_cancel,',
             b'wait_process(scope, stop_child, stop_timeout, cancelled, check_product,'),
            (b'check_cancel()\n        require(not errors, "Product stream capture failed")',
             b'require(not errors, "Product stream capture failed")\n        check_cancel()'),
        ):
            with self.subTest(before=before):
                self.mutate(path, before, after)

    def test_canonical_capture_late_shadowing_cannot_replace_the_bounded_worker(self):
        path = "scripts/run-audit-command.py"
        for suffix in (b'\nTee._copy = lambda self, remaining: None\n',
                       b'\nMAX_STREAM_BYTES = 128 * 1024 * 1024\n'):
            with self.subTest(suffix=suffix):
                changed = dict(self.sources)
                changed[path] += suffix
                with self.assertRaisesRegex(ValueError, "ordinary executable composition changed: " + path):
                    POLICY.check_sources(changed)

    def test_canonical_deadline_numeric_admission_and_no_enlargement_are_required(self):
        path = "scripts/run-audit-command.py"
        for before, after in (
            (b'type(value) in (int, float)', b'True'),
            (b'finite = math.isfinite(value)', b'finite = True'),
            (b'require(local_deadline <= deadline,', b'require(True,'),
            (b'deadline = local_deadline', b'deadline = max(deadline, local_deadline)'),
        ):
            with self.subTest(before=before):
                self.mutate(path, before, after)

    def test_canonical_deadline_original_launch_anchors_and_admitted_budgets_are_required(self):
        path = "scripts/run-audit-command.py"
        for before, after in (
            (b'product_deadline = local_timeout_deadline(time.monotonic(), product_timeout)',
             b'product_deadline = None'),
            (b'stop_deadline = local_timeout_deadline(time.monotonic(), stop_timeout)',
             b'stop_deadline = None'),
            (b'local_deadline=product_deadline', b'local_deadline=None'),
            (b'local_deadline=stop_deadline', b'local_deadline=None'),
            (b'wait_process(scope, child, product_timeout,', b'wait_process(scope, child, args.timeout,'),
            (b'wait_process(scope, stop_child, stop_timeout,', b'wait_process(scope, stop_child, args.stop_timeout,'),
        ):
            with self.subTest(before=before):
                self.mutate(path, before, after)

    def test_canonical_deadline_strict_observation_and_high_water_cannot_be_bypassed(self):
        path = "scripts/run-audit-command.py"
        for before, after in (
            (b'require(observed < deadline, expired)', b'require(observed <= deadline, expired)'),
            (b'observed = observe()\n        require(observed < deadline, expired)',
             b'observed = high_water\n        require(observed < deadline, expired)'),
            (b'current >= high_water', b'True'),
            (b'high_water = current', b'high_water = min(high_water, current)'),
            (b'time.sleep(0.1)\n        observed = observe()',
             b'time.sleep(0.1)\n        observed = observe()\n        deadline = observed + timeout'),
        ):
            with self.subTest(before=before):
                self.mutate(path, before, after)

    def test_canonical_deadline_expired_admission_and_cancellation_precedence_are_required(self):
        path = "scripts/run-audit-command.py"
        for before, after in (
            (b'if observed >= deadline:', b'if False:'),
            (b'            check_cancel()\n            if cancelled and not stop:',
             b'            pass\n            if cancelled and not stop:'),
            (b'        if cancelled and not stop:\n            raise AuditError("Invocation cancellation requested")',
             b'        if False:\n            raise AuditError("Invocation cancellation requested")'),
            (b'            raise AuditError(expired)\n        code = child.poll()',
             b'            pass\n        code = child.poll()'),
        ):
            with self.subTest(before=before):
                self.mutate(path, before, after)

    def test_canonical_deadline_late_shadowing_cannot_replace_wait_or_end_arithmetic(self):
        path = "scripts/run-audit-command.py"
        for suffix in (b'\nwait_process = lambda *args, **kwargs: 0\n',
                       b'\nlocal_timeout_deadline = lambda started, timeout: float("inf")\n'):
            with self.subTest(suffix=suffix):
                changed = dict(self.sources)
                changed[path] += suffix
                with self.assertRaisesRegex(ValueError, "ordinary executable composition changed: " + path):
                    POLICY.check_sources(changed)

    def test_canonical_retained_parents_anchor_and_descent_are_required(self):
        POLICY.check_sources(self.sources)
        path = "scripts/run-audit-command.py"
        for before, after in (
            (b'evidence.is_absolute() and parent.is_absolute() and within(parent, evidence) and\n'
             b'            ".." not in parent.parts', b'True'),
            (b'    reject_symlinks(evidence)\n\n    def validate(path: Path)',
             b'    pass\n\n    def validate(path: Path)'),
            (b'    validate(evidence)  # Never create an absent anchor or inspect /tmp as private.',
             b'    pass  # bypass the original evidence anchor'),
            (b'        validate(current)\n\n\ndef retain_reports',
             b'        pass\n\n\ndef retain_reports'),
        ):
            with self.subTest(before=before):
                self.assertEqual(self.sources[path].count(before), 1)
                self.mutate(path, before, after)

    def test_canonical_retained_parents_type_current_owner_and_private_mode_are_required(self):
        POLICY.check_sources(self.sources)
        path = "scripts/run-audit-command.py"
        for before, after in (
            (b'require(info is not None and stat.S_ISDIR(info.st_mode) and\n'
             b'                not (getattr(info, "st_file_attributes", 0) & 0x400),',
             b'require(info is not None and True and\n'
             b'                not (getattr(info, "st_file_attributes", 0) & 0x400),'),
            (b'not (getattr(info, "st_file_attributes", 0) & 0x400),\n'
             b'                "Retained report parent is not a physical directory")',
             b'True,\n                "Retained report parent is not a physical directory")'),
            (b'if os.name == "posix":\n            require(info.st_uid == os.getuid()',
             b'if False:\n            require(info.st_uid == os.getuid()'),
            (b'require(info.st_uid == os.getuid() and not info.st_mode & 0o077,',
             b'require(True and not info.st_mode & 0o077,'),
            (b'require(info.st_uid == os.getuid() and not info.st_mode & 0o077,',
             b'require(info.st_uid == os.getuid() and True,'),
        ):
            with self.subTest(before=before):
                self.assertEqual(self.sources[path].count(before), 1)
                self.mutate(path, before, after)

    def test_canonical_retained_parents_private_creation_and_narrow_race_handling_are_required(self):
        POLICY.check_sources(self.sources)
        path = "scripts/run-audit-command.py"
        for before, after in (
            (b'current.mkdir(mode=0o700)', b'current.mkdir(mode=0o755)'),
            (b'current.mkdir(mode=0o700)', b'current.mkdir(parents=True, mode=0o700)'),
            (b'except FileExistsError:\n'
             b'            pass  # Existing/racing paths must pass the same checks before descent.',
             b'except OSError:\n'
             b'            pass  # suppress unrelated errors'),
            (b'current.mkdir(mode=0o700)',
             b'current.mkdir(mode=0o700)\n            current.chmod(0o700)'),
        ):
            with self.subTest(before=before):
                self.assertEqual(self.sources[path].count(before), 1)
                self.mutate(path, before, after)

    def test_canonical_retained_parents_actual_report_call_cannot_be_replaced(self):
        POLICY.check_sources(self.sources)
        path = "scripts/run-audit-command.py"
        before = b'retained_report_parent(evidence, destination.parent)'
        self.assertEqual(self.sources[path].count(before), 1)
        for after in (b'destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)',
                      b'pass # retained_report_parent(evidence, destination.parent)'):
            with self.subTest(after=after):
                self.mutate(path, before, after)

    def test_canonical_retained_parents_late_shadowing_cannot_replace_validation(self):
        POLICY.check_sources(self.sources)
        path = "scripts/run-audit-command.py"
        for suffix in (b'\nretained_report_parent = lambda evidence, parent: None\n',
                       b'\nretain_reports = lambda *args, **kwargs: []\n'):
            with self.subTest(suffix=suffix):
                changed = dict(self.sources)
                changed[path] += suffix
                with self.assertRaisesRegex(ValueError, "ordinary executable composition changed: " + path):
                    POLICY.check_sources(changed)


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
