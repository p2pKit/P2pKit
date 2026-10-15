#!/usr/bin/env python3
"""Offline controls only: fixed privileged commands are mocked, never executed."""
import copy
import contextlib
import io
import json
import importlib.util
import os
from pathlib import Path
import plistlib
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('intel_advertising', ROOT / 'scripts/with-intel-bonjour-advertising.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
b = m.b
SOURCE = {'commit': 'a' * 40, 'tree': 'b' * 40}
BEFORE = {b.KEY: True, 'OtherPrivatePreference': 'never export this'}
POLICY = (0, 0, 0o644)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve() / m.NAME
        self.env = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
                        GITHUB_REPOSITORY='p2pKit/P2pKit', GITHUB_WORKFLOW='Intel iOS simulator tests',
                        GITHUB_JOB='ios-x64', RUNNER_OS='macOS', RUNNER_ARCH='X64',
                        GITHUB_REF='refs/heads/work/rpc-test', GITHUB_EVENT_NAME='workflow_dispatch',
                        GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', GITHUB_SHA=SOURCE['commit'],
                        GITHUB_WORKSPACE=str(ROOT), RUNNER_TEMP=str(self.parent.parent))
        self.workflow_ref()
        self.values = copy.deepcopy(BEFORE)
        self.calls = []
        self.fail = None
        self.timeout = None
        self.signal = None
        for context in (patch.object(b.private, 'source_snapshot', return_value=SOURCE),
                        patch.object(b, 'read_service_configuration', return_value='c' * 64),
                        patch.object(b, 'read_preference', side_effect=self.snapshot),
                        patch.object(b.subprocess, 'run', side_effect=self.run_command)):
            context.start()
            self.addCleanup(context.stop)

    def workflow_ref(self):
        self.env['GITHUB_WORKFLOW_REF'] = 'p2pKit/P2pKit/.github/workflows/ios-x64-tests.yml@' + self.env['GITHUB_REF']

    def snapshot(self):
        return copy.deepcopy(self.values), POLICY, plistlib.dumps(self.values)

    def run_command(self, argv, **kwargs):
        label = next(key for key, value in b.COMMANDS.items() if value == argv)
        # reload and restore-reload intentionally have identical fixed argv.
        if label == 'reload' and 'restore' in self.calls:
            label = 'restore-reload'
        self.calls.append(label)
        directory = self.parent / 'bonjour-advertising'
        self.assertTrue((directory / ('intent-' + label + '.json')).is_file())
        if label == 'apply':
            intent = m.read(directory / 'intent-apply.json')
            self.assertEqual(intent['policy'], list(POLICY))
            self.assertEqual(intent['originalSha256'], b.digest(plistlib.dumps(BEFORE)))
            self.values[b.KEY] = False
        elif label == 'restore':
            self.values[b.KEY] = True
        if label == self.timeout:
            raise b.subprocess.TimeoutExpired(argv, 30)
        return SimpleNamespace(returncode=1 if label == self.fail else -9 if label == self.signal else 0)

    def prepare(self):
        tx = m.Transaction(self.env, self.parent, SOURCE)
        tx.prepare()
        return tx

    def resume(self, env=None):
        return m.Transaction.resume(env or self.env, self.parent)

    def test_round_trip_reuses_transaction_and_preserves_typed_snapshot_and_policy(self):
        tx = self.prepare()
        self.assertFalse(self.values[b.KEY])
        resumed = self.resume()
        self.assertIsNot(tx, resumed)
        resumed.finish()
        self.assertEqual(self.values, BEFORE)
        self.assertEqual(self.calls, ['inspect', 'apply', 'reload', 'restore', 'restore-reload'])
        b.validate(resumed.proof, SOURCE)
        self.assertNotIn('OtherPrivatePreference', (resumed.directory / 'result.json').read_text())

    def test_prepare_records_original_intent_before_actual_mutation(self):
        self.prepare()  # Mock command checks on-disk intent before changing bytes.
        self.assertEqual(self.calls[:2], ['inspect', 'apply'])

    def test_known_failed_partial_apply_restores_original_without_product_or_false_pass(self):
        self.fail = 'apply'
        with self.assertRaises(b.PreparationFailure):
            self.prepare()
        resumed = self.resume()
        with self.assertRaises(RuntimeError):
            resumed.finish()
        self.assertEqual(self.values, BEFORE)
        self.assertEqual(self.calls, ['inspect', 'apply', 'restore'])
        self.assertEqual(resumed.proof['failure'], 'COMMAND_FAILED')

    def test_known_denied_reload_restores_disk_but_does_not_retry_service_or_pass(self):
        self.fail = 'reload'
        with self.assertRaises(b.PreparationFailure):
            self.prepare()
        resumed = self.resume()
        with self.assertRaises(RuntimeError):
            resumed.finish()
        self.assertEqual(self.calls, ['inspect', 'apply', 'reload', 'restore'])
        self.assertEqual(self.values, BEFORE)
        self.assertFalse(resumed.proof['restoreReloadSucceeded'])

    def test_known_success_receipt_before_flag_assignment_still_restores_reload(self):
        tx = self.prepare()
        self.assertTrue(tx.should_restore_reload())
        tx.proof['reloadSucceeded'] = False
        self.assertTrue(tx.should_restore_reload())

    def test_timed_out_mutator_refuses_restoration_not_descendant_closure(self):
        self.timeout = 'apply'
        with self.assertRaises(b.PreparationFailure):
            self.prepare()
        previous = list(self.calls)
        with self.assertRaisesRegex(RuntimeError, 'Incomplete command'):
            self.resume()
        self.assertEqual(self.calls, previous)

    def test_signaled_reload_refuses_restoration(self):
        self.signal = 'reload'
        with self.assertRaises(b.PreparationFailure):
            self.prepare()
        with self.assertRaisesRegex(RuntimeError, 'Incomplete command'):
            self.resume()
        self.assertEqual(self.calls, ['inspect', 'apply', 'reload'])

    def test_missing_completion_after_successful_mutation_is_unknown_never_replayed(self):
        tx = self.prepare()
        (tx.directory / 'complete-reload.json').unlink()
        with self.assertRaisesRegex(RuntimeError, 'Incomplete command'):
            self.resume()
        self.assertEqual(self.calls, ['inspect', 'apply', 'reload'])

    def test_interruption_without_prepared_record_is_not_silently_recovered(self):
        tx = self.prepare()
        (tx.directory / 'prepared.json').unlink()
        with self.assertRaises(FileNotFoundError):
            self.resume()
        self.assertFalse((tx.directory / 'restore-started.json').exists())

    def test_missing_state_is_not_recreated(self):
        with self.assertRaises(FileNotFoundError):
            self.resume()
        self.assertFalse(self.parent.exists())

    def test_one_attempt_only_even_after_success(self):
        tx = self.prepare()
        with self.assertRaises(FileExistsError):
            tx.command('apply')
        resumed = self.resume()
        resumed.finish()
        with self.assertRaises(RuntimeError):
            self.resume()
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(self.calls.count('apply'), 1)
        self.assertEqual(self.calls.count('restore'), 1)

    def test_source_dirtiness_does_not_prevent_restore_but_never_qualifies(self):
        self.prepare()
        with patch.object(b.private, 'source_snapshot', side_effect=RuntimeError('dirty source')):
            resumed = self.resume()
            with self.assertRaises(RuntimeError):
                resumed.finish()
        self.assertEqual(self.values, BEFORE)
        self.assertFalse(resumed.proof['sourceUnchanged'])

    def test_cross_run_attempt_source_ref_job_and_uid_rejected_before_mutation(self):
        self.prepare()
        for field in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA', 'GITHUB_REF', 'GITHUB_JOB'):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                self.resume({**self.env, field: 'changed'})
        with patch.object(m.os, 'getuid', return_value=os.getuid() + 1), self.assertRaises(RuntimeError):
            self.resume()
        self.assertEqual(self.calls, ['inspect', 'apply', 'reload'])

    def test_replaced_directory_refused_despite_same_content(self):
        tx = self.prepare()
        moved = tx.directory.with_name('old')
        tx.directory.rename(moved)
        tx.directory.mkdir(mode=0o700)
        import shutil
        for item in moved.iterdir():
            shutil.copy2(item, tx.directory / item.name)
        with self.assertRaisesRegex(RuntimeError, 'directory changed'):
            self.resume()

    def test_modified_original_bytes_refused_before_restore(self):
        tx = self.prepare()
        (tx.directory / 'original.plist').write_bytes(plistlib.dumps({**BEFORE, b.KEY: False}))
        with self.assertRaisesRegex(RuntimeError, 'bytes changed'):
            self.resume()

    def test_changed_original_policy_in_prepared_record_refused(self):
        tx = self.prepare()
        record = m.read(tx.directory / 'prepared.json')
        record['policy'][2] = 0o600
        (tx.directory / 'prepared.json').unlink()
        m.write(tx.directory / 'prepared.json', record)
        with self.assertRaisesRegex(RuntimeError, 'precede mutation'):
            self.resume()

    def test_symlink_and_hardlinked_state_refused(self):
        tx = self.prepare()
        path = tx.directory / 'prepared.json'
        backup = tx.directory / 'backup.json'
        path.rename(backup)
        path.symlink_to(backup)
        with self.assertRaises(RuntimeError):
            self.resume()
        path.unlink()
        os.link(backup, path)
        with self.assertRaisesRegex(RuntimeError, 'Hardlinked'):
            self.resume()

    def test_restoration_failure_preserved_and_no_second_attempt(self):
        self.prepare()
        self.fail = 'restore'
        resumed = self.resume()
        with self.assertRaises(RuntimeError):
            resumed.finish()
        with self.assertRaises(RuntimeError):
            self.resume()
        self.assertEqual(resumed.proof['restoreFailure'], 'COMMAND_FAILED')
        self.assertEqual(self.calls.count('restore'), 1)

    def test_unrelated_preference_change_is_not_overwritten_or_passed(self):
        self.prepare()
        self.values['OtherPrivatePreference'] = 'changed externally'
        resumed = self.resume()
        with self.assertRaises(RuntimeError):
            resumed.finish()
        self.assertTrue(self.values[b.KEY])
        self.assertEqual(self.values['OtherPrivatePreference'], 'changed externally')
        self.assertEqual(resumed.proof['restoreFailure'], 'RESTORATION')

    def test_snapshot_failure_before_mutation_retains_failure_without_restoration(self):
        with patch.object(b, 'read_preference', side_effect=b.PreparationFailure('PREFERENCE_MISSING')):
            with self.assertRaises(b.PreparationFailure):
                self.prepare()
        resumed = self.resume()
        with self.assertRaises(RuntimeError):
            resumed.finish()
        self.assertEqual(self.calls, ['inspect'])
        self.assertFalse(resumed.proof['changeAttempted'])

    def test_intent_durability_failure_prevents_privileged_mutation(self):
        actual_write = m.write
        def fail_intent(path, value):
            if path.name == 'intent-apply.json':
                raise OSError('cannot make intent durable')
            actual_write(path, value)
        with patch.object(m, 'write', side_effect=fail_intent), self.assertRaises(OSError):
            self.prepare()
        self.assertEqual(self.calls, ['inspect'])
        self.assertEqual(self.values, BEFORE)

    def test_missing_original_snapshot_refused_before_restore(self):
        tx = self.prepare()
        (tx.directory / 'original.plist').unlink()
        with self.assertRaises(FileNotFoundError):
            self.resume()
        self.assertEqual(self.calls, ['inspect', 'apply', 'reload'])

    def test_cli_exports_only_closed_configuration_proof_and_never_product_qualification(self):
        with patch.object(m, 'admit', return_value=self.parent), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.execute('prepare', self.env), 0)
            self.assertEqual(m.execute('restore', self.env), 0)
        raw = (self.parent.parent / m.REPORT).read_text()
        report = json.loads(raw)
        self.assertTrue(report['successfulConfigurationRoundTrip'])
        self.assertEqual(report['qualification'], 'NOT_PERFORMED')
        self.assertEqual(report['uncertainty'], 'NONE')
        self.assertIsNone(report['failurePhase'])
        self.assertEqual(report['proof']['source'], SOURCE)
        for private in ('OtherPrivatePreference', 'never export this', str(self.parent), 'originalSha256', 'uid'):
            self.assertNotIn(private, raw)

    def test_cli_preserves_unknown_command_as_failure_without_further_mutation(self):
        tx = self.prepare()
        (tx.directory / 'complete-reload.json').unlink()
        with patch.object(m, 'admit', return_value=self.parent), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.execute('restore', self.env), 1)
        report = json.loads((self.parent.parent / m.REPORT).read_text())
        self.assertFalse(report['successfulConfigurationRoundTrip'])
        self.assertEqual(report['failurePhase'], 'REHYDRATION_OR_COMMAND_COMPLETION')
        self.assertEqual(report['uncertainty'], 'NO_SUCCESSFUL_RESTORATION_CLAIM')
        self.assertEqual(self.calls, ['inspect', 'apply', 'reload'])

    def test_admission_native_ordinary_default_and_schedule_truth_table(self):
        real_stat = Path.stat
        console_uid = [501]
        def path_stat(path, *args, **kwargs):
            if str(path) == '/dev/console':
                return SimpleNamespace(st_mode=stat.S_IFCHR, st_uid=console_uid[0])
            result = real_stat(path, *args, **kwargs)
            if path == self.parent.parent:
                return SimpleNamespace(st_mode=result.st_mode, st_uid=501)
            return result
        with patch.object(m.platform, 'system', return_value='Darwin'), \
                patch.object(m.platform, 'machine', return_value='x86_64'), \
                patch.object(m, 'host_role', return_value='macos-x64'), patch.object(Path, 'stat', path_stat), \
                patch.object(m.os, 'getuid', return_value=501), patch.object(m.os, 'geteuid', return_value=501), \
                patch.object(m.os, 'getgid', return_value=20), patch.object(m.os, 'getegid', return_value=20):
            for ref, event, passed in (('refs/heads/work/rpc-test', 'workflow_dispatch', True),
                                      ('refs/heads/main', 'workflow_dispatch', True),
                                      ('refs/heads/main', 'schedule', True),
                                      ('refs/heads/work/rpc-test', 'schedule', False),
                                      ('refs/heads/work/foundation', 'workflow_dispatch', False)):
                self.env.update(GITHUB_REF=ref, GITHUB_EVENT_NAME=event)
                self.workflow_ref()
                if passed:
                    self.assertEqual(m.admit(self.env), self.parent)
                else:
                    with self.assertRaises(RuntimeError):
                        m.admit(self.env)
            self.env.update(GITHUB_REF='refs/heads/main', GITHUB_EVENT_NAME='workflow_dispatch')
            self.workflow_ref()
            for key, value in (('GITHUB_JOB', 'intel-environment-diagnostics'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
                               ('GITHUB_WORKFLOW_REF', 'other'), ('RPC_APPLE_TERMINAL_CONTEXT', 'true'),
                               ('RPC_APPLE_AUDIT_CONTEXT', 'true'), ('GITHUB_RUN_ATTEMPT', '0')):
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    m.admit({**self.env, key: value})
            for context in (patch.object(m.os, 'getuid', return_value=0),
                            patch.object(m.os, 'geteuid', return_value=0),
                            patch.object(m.platform, 'machine', return_value='arm64'),
                            patch.object(m, 'host_role', return_value='macos-arm64')):
                with context, self.assertRaises(RuntimeError):
                    m.admit(self.env)
            console_uid[0] = 502
            with self.assertRaises(RuntimeError):
                m.admit(self.env)


if __name__ == '__main__':
    unittest.main(verbosity=2)
