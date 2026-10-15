#!/usr/bin/env python3
"""Fresh-process signal controls; no administrator dialog or native admission."""
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / 'rpc_local_signal_environment.py'
spec = importlib.util.spec_from_file_location('local_signal_test', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SignalModel:
    SIG_BLOCK, SIG_SETMASK = signal.SIG_BLOCK, signal.SIG_SETMASK
    SIGINT, SIGTERM = signal.SIGINT, signal.SIGTERM
    SIG_DFL, SIG_IGN = signal.SIG_DFL, signal.SIG_IGN
    default_int_handler = staticmethod(signal.default_int_handler)

    def __init__(self):
        self.blocked, self.pending, self.changes = set(), set(), []
        self.handlers = {self.SIGINT: self.default_int_handler, self.SIGTERM: self.SIG_DFL}
        self.wrong_previous = self.wrong_readback = False

    def pthread_sigmask(self, action, values):
        previous = set(self.blocked)
        if action == self.SIG_SETMASK:
            self.changes.append(('mask', set(values)))
            self.blocked = {self.SIGTERM} if self.wrong_readback else set(values)
            return {self.SIGINT} if self.wrong_previous else previous
        if action != self.SIG_BLOCK or values:
            raise AssertionError('Only empty-set observation or explicit empty-mask restoration')
        return previous

    def sigpending(self):
        return set(self.pending)

    def getsignal(self, number):
        return self.handlers[number]

    def signal(self, number, handler):
        self.changes.append(('handler', number))
        self.handlers[number] = handler


class Policy(unittest.TestCase):
    def setUp(self):
        self.model, self.records = SignalModel(), []
        main = object()
        self.threads = SimpleNamespace(active_count=lambda: 1, main_thread=lambda: main, current_thread=lambda: main)
        self.identity = SimpleNamespace(getuid=lambda: 501, geteuid=lambda: 501)
        for name, value in (('signal', self.model), ('threading', self.threads), ('os', self.identity)):
            patcher = patch.object(m, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_policy(self):
        return m.normalize(self.records.append)

    def test_clean_process_is_observed_not_native_admission(self):
        proof = self.run_policy()
        self.assertEqual(proof['before']['blockedSignals'], [])
        self.assertEqual(proof['after']['blockedSignals'], [])
        self.assertEqual(self.records, [proof['before']])
        self.assertFalse(proof['nativeAdmission'])
        self.assertFalse(proof['maskChanged'])
        self.assertTrue(proof['processLocalOnly'])

    def test_blocked_signals_are_recorded_then_unblocked_for_fresh_children(self):
        self.model.blocked = {signal.SIGTERM, signal.SIGINT, signal.SIGCHLD}
        proof = self.run_policy()
        self.assertEqual(proof['before']['blockedSignals'], sorted(map(int, (signal.SIGTERM, signal.SIGINT, signal.SIGCHLD))))
        self.assertTrue(proof['maskChanged'])
        self.assertEqual(proof['after']['blockedSignals'], [])

    def test_ignored_cancellation_dispositions_are_restored(self):
        self.model.handlers = {signal.SIGINT: signal.SIG_IGN, signal.SIGTERM: signal.SIG_IGN}
        proof = self.run_policy()
        self.assertEqual(proof['before']['dispositions'], {'SIGINT': 'IGNORE', 'SIGTERM': 'IGNORE'})
        self.assertEqual(proof['after']['dispositions'], {'SIGINT': 'PYTHON_DEFAULT_INTERRUPT', 'SIGTERM': 'DEFAULT'})

    def test_privileged_or_mixed_credentials_cannot_observe_or_change_signals(self):
        for uid, euid in ((0, 0), (501, 0), (0, 501), (501, 502)):
            with self.subTest(uid=uid, euid=euid):
                self.identity.getuid, self.identity.geteuid = lambda: uid, lambda: euid
                with self.assertRaises(RuntimeError):
                    self.run_policy()
                self.assertEqual(self.model.changes, [])
                self.assertEqual(self.records, [])

    def test_only_single_main_thread_may_prepare_signal_inheritance(self):
        self.threads.active_count = lambda: 2
        with self.assertRaises(RuntimeError):
            self.run_policy()
        self.threads.active_count = lambda: 1
        self.threads.current_thread = lambda: object()
        with self.assertRaises(RuntimeError):
            self.run_policy()
        self.assertEqual(self.model.changes, [])

    def test_pending_cancellation_is_preserved_not_discarded_or_delivered_early(self):
        self.model.blocked = self.model.pending = {signal.SIGTERM}
        with self.assertRaisesRegex(RuntimeError, 'Pending'):
            self.run_policy()
        self.assertEqual(self.model.changes, [])
        self.assertEqual(self.records[0]['pendingSignals'], [int(signal.SIGTERM)])

    def test_custom_handler_is_not_overwritten(self):
        self.model.handlers[signal.SIGTERM] = lambda *_: None
        with self.assertRaisesRegex(RuntimeError, 'handler'):
            self.run_policy()
        self.assertEqual(self.model.changes, [])

    def test_failed_initial_evidence_write_prevents_any_signal_change(self):
        self.model.blocked = {signal.SIGTERM}
        def refuse(_):
            raise OSError('create-only evidence refused')
        with self.assertRaises(OSError):
            m.normalize(refuse)
        self.assertEqual(self.model.changes, [])

    def test_changed_mask_during_preparation_is_not_admitted(self):
        self.model.wrong_previous = True
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            self.run_policy()

    def test_nonempty_readback_is_not_admitted(self):
        self.model.wrong_readback = True
        with self.assertRaisesRegex(RuntimeError, 'restored'):
            self.run_policy()


class PosixChild(unittest.TestCase):
    def child(self, setup, action):
        code = (
            'import importlib.util,json,os,signal,sys; sys.dont_write_bytecode=True\n'
            f'spec=importlib.util.spec_from_file_location("signal_child",{str(SOURCE)!r}); '
            'm=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n'
            + setup + '\n'
            + action + '\n')
        return subprocess.run([sys.executable, '-I', '-B', '-S', '-c', code], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4, check=False)

    def test_real_blocked_term_without_preparation_stays_pending(self):
        process = self.child('signal.pthread_sigmask(signal.SIG_BLOCK,[signal.SIGTERM])',
            'os.kill(os.getpid(),signal.SIGTERM); '
            'print(json.dumps(dict(pending=sorted(map(int,signal.sigpending())))),flush=True)')
        self.assertEqual(process.returncode, 0, process.stderr.decode())
        self.assertEqual(json.loads(process.stdout), dict(pending=[int(signal.SIGTERM)]))

    def test_real_blocked_term_is_restored_and_delivered_without_timeout(self):
        process = self.child('signal.pthread_sigmask(signal.SIG_BLOCK,[signal.SIGTERM,signal.SIGCHLD])',
            'proof=m.normalize(lambda before: None); print(json.dumps(proof),flush=True); '
            'os.kill(os.getpid(),signal.SIGTERM); raise SystemExit(97)')
        self.assertEqual(process.returncode, -signal.SIGTERM, process.stderr.decode())
        proof = json.loads(process.stdout)
        self.assertIn(signal.SIGTERM, proof['before']['blockedSignals'])
        self.assertEqual(proof['after']['blockedSignals'], [])

    def test_real_ignored_term_is_restored_and_delivered(self):
        process = self.child('signal.signal(signal.SIGTERM,signal.SIG_IGN)',
            'proof=m.normalize(lambda before: None); print(json.dumps(proof),flush=True); '
            'os.kill(os.getpid(),signal.SIGTERM); raise SystemExit(97)')
        self.assertEqual(process.returncode, -signal.SIGTERM, process.stderr.decode())
        self.assertEqual(json.loads(process.stdout)['before']['dispositions']['SIGTERM'], 'IGNORE')

    def test_real_pending_term_is_refused_without_unblocking(self):
        process = self.child(
            'signal.pthread_sigmask(signal.SIG_BLOCK,[signal.SIGTERM]); os.kill(os.getpid(),signal.SIGTERM)',
            'try:\n    m.normalize(lambda before: None)\n'
            'except RuntimeError:\n'
            '    print(json.dumps(dict(blocked=sorted(map(int,signal.pthread_sigmask(signal.SIG_BLOCK,[]))),'
            'pending=sorted(map(int,signal.sigpending())))),flush=True)\n'
            'else:\n    raise SystemExit(97)')
        self.assertEqual(process.returncode, 0, process.stderr.decode())
        self.assertEqual(json.loads(process.stdout), dict(blocked=[int(signal.SIGTERM)], pending=[int(signal.SIGTERM)]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
