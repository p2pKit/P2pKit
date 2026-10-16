#!/usr/bin/env python3
"""Fixed API-probe source and evidence tripwires; not Windows runtime or supervision acceptance."""
import importlib.util
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / 'samples/p2p-sample-rpc/native/windows-profile/tests/windows'
SPEC = importlib.util.spec_from_file_location('atomic_evidence', ROOT / 'scripts/rpc_windows_environment_evidence.py')
evidence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = evidence
SPEC.loader.exec_module(evidence)


def observation():
    value = dict.fromkeys(evidence.ATOMIC_LOGON_TRUE, True)
    value.update(dict.fromkeys(evidence.ATOMIC_LOGON_FALSE, False))
    value.update(dict.fromkeys(evidence.ATOMIC_LOGON_NUMBERS, 0))
    value.update(scope=evidence.ATOMIC_LOGON_SCOPE, launchApi='CreateProcessWithLogonW',
                 stage=10, childExit=42, jobObservations=1)
    return value


def source_check(text):
    code = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    if code.count('CreateProcessWithLogonW(') != 1:
        raise ValueError('One credentialed attempt only')
    for forbidden in ('AssignProcessToJobObject(', 'CreateProcessAsUserW(', 'CreateProcessWithTokenW(',
                      'AdjustTokenPrivileges(', 'LsaAddAccountRights(', 'OpenProcess(', 'LOGON_WITH_PROFILE',
                      'CREATE_BREAKAWAY_FROM_JOB', 'Sleep(1000)', 'System.load'):
        if forbidden in code:
            raise ValueError('Forbidden fallback, authority or scope')
    required = ('startup.StartupInfo.cb = sizeof(startup)', 'startup.lpAttributeList = attributes',
                'HANDLE jobs[] = {job.value}', 'PROC_THREAD_ATTRIBUTE_JOB_LIST',
                'CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW',
                'environment, system, &startup.StartupInfo, &pi)', 'JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE',
                'if (!member)', '!EqualSid(expected, actual)', 'previous_suspend != 1',
                'child_exit != CHILD_EXIT', 'if (!cleanup) result = 8;', 'if (!result) stage = 10;',
                'if (result != 0 && job.value)', 'if (*observations >= 65536u)',
                'WaitForSingleObject(process.value, remaining(&watch))',
                'account_disabled = atomic_disable_account(name, &account_error)',
                'info->usri1_priv == USER_PRIV_USER', 'wcscmp(info->usri1_name, name) == 0',
                'SecureZeroMemory(password, sizeof(password))', 'if (!finish_watchdog(&watch)) cleanup = 0;')
    for token in required:
        if token not in code:
            raise ValueError('Missing invariant: ' + token)
    ordered = ('UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE', 'error = NetUserAdd(', 'account_created = 1;',
               'USER_INFO_1008 enabled', 'account_enabled = 1;', 'LogonUserW(', 'CreateProcessWithLogonW(',
               'IsProcessInJob(process.value', '!EqualSid(expected, actual)', 'ResumeThread(thread.value)',
               'child_executed = 1; stage = 9; result = 0;', 'if (!close_once(&child_token))',
               'if (!close_once(&process))', 'job_empty = atomic_wait_empty(',
               'account_disabled = atomic_disable_account(name', 'if (!close_once(&job))')
    position = -1
    for token in ordered:
        position = code.find(token, position + 1)
        if position < 0:
            raise ValueError('Ownership/admission order')
    return required


class AtomicLogon(unittest.TestCase):
    def test_exact_source_and_mutated_invariants(self):
        text = (NATIVE / 'profile_atomic_logon_environment_probe.c').read_text()
        required = source_check(text)
        for token in required:
            with self.subTest(token=token), self.assertRaises(ValueError):
                source_check(text.replace(token, 'REMOVED'))
        for extra in ('AssignProcessToJobObject(job, child);', 'CreateProcessWithLogonW();',
                      'AdjustTokenPrivileges(token);', 'OpenProcess(pid);'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                source_check(text + '\n' + extra)

    def test_account_and_resume_reordering_refused(self):
        text = (NATIVE / 'profile_atomic_logon_environment_probe.c').read_text()
        for first, second in [('account_created = 1;', 'USER_INFO_1008 enabled'),
                              ('IsProcessInJob(process.value', 'ResumeThread(thread.value)'),
                              ('if (!close_once(&process))', 'job_empty = atomic_wait_empty(')]:
            bad = text.replace(first, '__SWAP__').replace(second, first).replace('__SWAP__', second)
            with self.subTest(first=first), self.assertRaises(ValueError):
                source_check(bad)

    def test_no_shadowed_cleanup_wait_local(self):
        text = (NATIVE / 'profile_atomic_logon_environment_probe.c').read_text()
        self.assertEqual(text.count('DWORD waited ='), 1)
        self.assertEqual(text.count('DWORD cleanup_waited ='), 1)
        self.assertIn('if (cleanup_waited == WAIT_TIMEOUT)', text)
        self.assertIn('else if (cleanup_waited != WAIT_OBJECT_0) cleanup = 0;', text)

    def test_wrapper_retains_failure_before_acceptance(self):
        wrapper = (NATIVE / 'check-hosted-atomic-logon-environment.ps1').read_text()
        self.assertLess(wrapper.index('$result.observation = $record'),
                        wrapper.index('Assert-AtomicLogonObservation -Record'))
        self.assertIn("$output 'probe' 70000", wrapper)
        self.assertIn("result = 'NOT_COMPLETED'", wrapper)
        self.assertIn('profileRuntime = \'NOT_PERFORMED\'', wrapper)
        self.assertNotIn('continue', wrapper)

    def test_valid_pass(self):
        evidence.validate_atomic_logon_observation(observation(), True)

    def test_every_field_required_and_no_extra_fields(self):
        for key in observation():
            bad = observation(); del bad[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                evidence.validate_atomic_logon_observation(bad, True)
        bad = observation(); bad['ready'] = True
        with self.assertRaises(ValueError):
            evidence.validate_atomic_logon_observation(bad, True)

    def test_boolean_and_numeric_mutations(self):
        for key in evidence.ATOMIC_LOGON_TRUE | evidence.ATOMIC_LOGON_FALSE:
            for value in (not observation()[key], 0, 1, 'true', None, [observation()[key]]):
                bad = observation(); bad[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    evidence.validate_atomic_logon_observation(bad, True)
        for key in evidence.ATOMIC_LOGON_NUMBERS:
            for value in (True, False, 0.0, -1, 0x100000000, '0', None):
                bad = observation(); bad[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    evidence.validate_atomic_logon_observation(bad, True)

    def test_api_failure_and_scope_escalation_refused(self):
        for key, values in {'scope': ['PROTECTED_SUPERVISION', [evidence.ATOMIC_LOGON_SCOPE]],
                            'launchApi': ['CreateProcessAsUserW', ['CreateProcessWithLogonW']],
                            'result': [5, 8], 'stage': [6, 9], 'systemCode': [87, 1314],
                            'childExit': [0, 125, 259], 'finalJobActiveProcesses': [1],
                            'jobObservations': [0, 65537]}.items():
            for value in values:
                bad = observation(); bad[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    evidence.validate_atomic_logon_observation(bad, True)

    def test_retained_failed_api_call_never_promoted(self):
        bad = observation()
        bad.update(result=5, stage=6, systemCode=87, created=False, memberBeforeResume=False,
                   tokenMatched=False, resumed=False, childExecuted=False, childExitObserved=False,
                   childExit=259, explicitFailureCleanup=True)
        receipt = dict(scope=evidence.ATOMIC_LOGON_SCOPE, result='NOT_COMPLETED')
        evidence.validate_atomic_logon_completion(receipt, bad)
        evidence.validate_atomic_logon_completion(receipt, None)
        receipt['result'] = 'PASS'
        for native in (bad, None):
            with self.assertRaises(ValueError):
                evidence.validate_atomic_logon_completion(receipt, native)

    def test_execution_is_mandatory_and_exactly_typed(self):
        execution = dict(passed=True, processExitObserved=True, finalizationCompleted=True,
                         timedOut=False, outputExceeded=False, exitCode=0, elapsedMs=100)
        receipt = dict(scope=evidence.ATOMIC_LOGON_SCOPE, result='PASS', execution=execution)
        evidence.validate_atomic_logon_completion(receipt, observation())
        for key in execution:
            bad = execution.copy(); del bad[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                evidence.validate_atomic_logon_completion(dict(receipt, execution=bad), observation())
        for key, value in [('passed', 1), ('timedOut', 0), ('exitCode', False), ('elapsedMs', 70000)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                evidence.validate_atomic_logon_completion(dict(receipt, execution=dict(execution, **{key: value})),
                                                           observation())


if __name__ == '__main__':
    unittest.main()
