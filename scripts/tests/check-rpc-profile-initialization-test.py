#!/usr/bin/env python3
"""Fail-closed source tripwires; not compiler, Windows execution, or protected-profile evidence."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / 'samples/p2p-sample-rpc/native/windows-profile/tests/windows'


def verify(source):
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.DOTALL)
    for forbidden in ('AdjustTokenPrivileges', 'LsaAddAccountRights', 'LoadUserProfile',
                      'CreateProcessAsUserW', 'CreateProcessWithTokenW', 'LoadLibrary',
                      'KF_FLAG_CREATE', 'SetNamedSecurityInfo', 'DeleteProfile', 'pwp_win_',
                      'SetEnvironmentVariable', 'SetSecurityInfo', 'CREATE_ALWAYS'):
        if forbidden in source:
            raise ValueError(forbidden)
    for required in ('LOGON_WITH_PROFILE, executable', 'GetUserProfileDirectoryW',
                     'SHGetKnownFolderPath(&FOLDERID_Profile, KF_FLAG_DEFAULT',
                     'SHGetKnownFolderPath(&FOLDERID_LocalAppData, KF_FLAG_DEFAULT',
                     'GetVolumeInformationByHandleW', 'FILE_FLAG_OPEN_REPARSE_POINT',
                     'wcscmp(filesystem, L"NTFS")', 'GetDriveTypeW(volume) != DRIVE_FIXED',
                     'if (admission != CHILD_EXIT) return admission;',
                     '!standard_token(child_token.value)', '!EqualSid(expected, actual)',
                     'hive_absent_before = 1;', 'hive_loaded = 1;', 'p2pkit_hive_namespace_await_absent(sid_text, hive_original_remaining,',
                     'hive_close_error == ERROR_SUCCESS', 'UF_ACCOUNTDISABLE',
                     'if (!cleanup) result = 8;', 'SecureZeroMemory(password, sizeof(password))'):
        if required not in source:
            raise ValueError(required)
    for field, value in [('bootstrapAtomicJobAdmission', 'false'), ('nativeStorageExecuted', 'false'),
                         ('profileRequested', 'true')]:
        if f'\\"{field}\\":{value}' not in source:
            raise ValueError('Scope claim')
    order = [source.index(x) for x in ['hive_absent_before = 1;', 'CreateProcessWithLogonW(',
             'AssignProcessToJobObject(', 'hive_loaded = 1;', 'ResumeThread(',
             'p2pkit_hive_namespace_await_absent(sid_text, hive_original_remaining,']]
    if order != sorted(order) or source.count('CreateProcessWithLogonW(') != 1:
        raise ValueError('Setup order or repeated launch')
    main = source.split('int wmain(', 1)[1]
    if 'argc != 2' not in main or 'argv[2]' in main or main.count('wcscmp(') != 2:
        raise ValueError('Arbitrary payload')


class ProfileInitialization(unittest.TestCase):
    def setUp(self):
        self.source = (NATIVE / 'profile_initialization_environment_probe.c').read_text()

    def test_fixed_no_storage_profile_recipe(self):
        verify(self.source)

    def test_security_shortcuts_refused(self):
        for api in ('AdjustTokenPrivileges', 'LsaAddAccountRights', 'LoadUserProfile', 'LoadLibrary',
                    'KF_FLAG_CREATE', 'SetNamedSecurityInfo', 'DeleteProfile', 'SetEnvironmentVariable'):
            with self.subTest(api=api), self.assertRaises(ValueError):
                verify(self.source + '\n' + api + '();')

    def test_admission_and_cleanup_cannot_be_removed(self):
        for required in ('!standard_token(child_token.value)', '!EqualSid(expected, actual)',
                         'hive_close_error == ERROR_SUCCESS', 'UF_ACCOUNTDISABLE',
                         'GetVolumeInformationByHandleW', 'if (!cleanup) result = 8;'):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, 'REMOVED'))

    def test_child_cleanup_failure_not_mislabeled_as_elevation_rejection(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace('if (admission != CHILD_EXIT) return admission;',
                                       'if (admission != CHILD_EXIT) return 3;'))

    def test_scope_cannot_be_promoted(self):
        for field in ('bootstrapAtomicJobAdmission', 'nativeStorageExecuted'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(self.source.replace(f'\\"{field}\\":false', f'\\"{field}\\":true'))

    def test_parent_observer_preserves_original_budget_and_errors(self):
        body = (NATIVE / 'profile_hive_namespace_observer.h').read_text()
        for required in ('NtOpenKey(&parent, KEY_ENUMERATE_SUB_KEYS | KEY_NOTIFY',
                         'REG_NOTIFY_CHANGE_NAME | REG_NOTIFY_THREAD_AGNOSTIC',
                         'owner->notification_pending = 1;', 'owner->notification_pending = 0;',
                         'if (!present && exhausted && owner->wait_result == WAIT_TIMEOUT)',
                         'if (!p2pkit_hive_namespace_retire(owner, remaining, context)) return 0;',
                         'P2PKIT_HIVE_MAXIMUM_NAMES 1024u'):
            self.assertIn(required, body)
        self.assertNotIn('RegOpenKeyEx', re.sub(r'/\*.*?\*/', '', body, flags=re.DOTALL))
        self.assertNotIn('ERROR_KEY_DELETED', body)
        self.assertIn('return remaining((const watchdog *)context);', self.source)
        self.assertIn('if (created && sid_text && hive_absent_before)', self.source)
        self.assertNotIn('start_watchdog', body)

    def test_wrapper_keeps_profile_and_jni_unqualified(self):
        source = (NATIVE / 'check-hosted-profile-initialization.ps1').read_text()
        for required in ("$env:GITHUB_JOB -cne 'rpc-windows-environment'", "$head -cne $env:GITHUB_SHA",
                         "profileRuntime = 'NOT_PERFORMED'", "jniRuntime = 'NOT_PERFORMED'",
                         "protectedSupervisor = 'NOT_QUALIFIED'", '[IO.FileMode]::CreateNew',
                         '-not $record.hiveAbsentBefore', '-not $record.hiveLoadedBeforeResume',
                         '-not $record.hiveUnloadedAfterExit', '$record.profileProbeExit -ne 0',
                         '-not $record.namespaceAbsenceObserved', '-not $record.namespaceRetired',
                         '$record.namespaceEnumerationStatus -ne 259', '$record.namespaceSystemError -ne 0',
                         '$record.bootstrapAtomicJobAdmission', '$record.nativeStorageExecuted'):
            self.assertIn(required, source)
        self.assertNotIn('Start-Process -Credential', source)

    def test_gui_fixture_does_not_change_profile_acceptance(self):
        wrapper = (NATIVE / 'check-hosted-profile-initialization.ps1').read_text()
        self.assertEqual(wrapper.count('/SUBSYSTEM:WINDOWS /ENTRY:wmainCRTStartup'), 1)
        self.assertIn('$result.fixtureImage = Assert-EnvironmentFixtureImage $exe', wrapper)
        self.assertIn("$fixtureFunctions.Count -ne 1", wrapper)
        self.assertIn("'check-hosted-job-inheritance-environment.ps1')", wrapper)
        self.assertIn("'probe' 70000", wrapper)
        self.assertIn('-not $record.hiveUnloadedAfterExit', wrapper)
        self.assertIn('-not $record.namespaceRetired', wrapper)
        self.assertIn("protectedSupervisor = 'NOT_QUALIFIED'", wrapper)

    def test_snapshot_is_one_shot_diagnostic_not_acceptance(self):
        body = (NATIVE / 'profile_hive_namespace_observer.h').read_text()
        split = body.split('int diagnostic_split =', 1)[1].split(
            'if (owner->wait_result == WAIT_OBJECT_0)', 1)[0]
        for required in ('present && !owner->diagnostic_wait_attempted',
                         'if (wait_budget > 1000u) wait_budget = 1000u;',
                         'diagnostic_split && owner->wait_result == WAIT_TIMEOUT',
                         'owner->snapshot_state == 3',
                         'WaitForSingleObject(owner->event, remaining(context))'):
            self.assertIn(required, split)
        for forbidden in ('absence_observed =', 'notification_pending =', 'RegNotifyChangeKeyValue',
                          'ResetEvent', 'start_watchdog'):
            self.assertNotIn(forbidden, split)
        snapshot = body.split('static DWORD p2pkit_hive_namespace_snapshot(', 1)[1].split(
            '/* Exactly one retirement attempt', 1)[0]
        for required in ('index <= P2PKIT_HIVE_MAXIMUM_NAMES',
                         'RegEnumKeyExW(parent, index, child, &length',
                         'SecureZeroMemory(child, sizeof(child))'):
            self.assertIn(required, snapshot)
        for forbidden in ('RegOpenKey', 'NtOpenKey', 'CreateEvent', 'RegNotifyChangeKeyValue'):
            self.assertNotIn(forbidden, snapshot)
        wrapper = (NATIVE / 'check-hosted-profile-initialization.ps1').read_text()
        self.assertIn("$snapshots.Count -gt 1", wrapper)
        self.assertIn('ONE_PARENT_ENUMERATION_NOT_STABILIZED_ABSENCE_OR_ACCEPTANCE', wrapper)
        self.assertIn("'probe' 70000", wrapper)
        self.assertIn('-not $record.hiveUnloadedAfterExit', wrapper)
        self.assertIn('-not $record.namespaceRetired', wrapper)

    def test_compile_time_cancellation_diagnostic_cannot_establish_absence(self):
        self.assertEqual(self.source.count('#define P2PKIT_HIVE_OBSERVER_DIAGNOSTIC_RETIRE_ON_MISS 1'), 1)
        self.assertIn('DIAGNOSTIC_CANCELLATION_ONLY_NOT_PROFILE_ACCEPTANCE', self.source)
        body = (NATIVE / 'profile_hive_namespace_observer.h').read_text()
        diagnostic = body.split('#ifdef P2PKIT_HIVE_OBSERVER_DIAGNOSTIC_RETIRE_ON_MISS', 1)[1].split('#endif', 1)[0]
        for required in ('owner->snapshot_state == 2 && P2PKIT_HIVE_OBSERVER_DIAGNOSTIC_RETIRE_ON_MISS',
                         'owner->diagnostic_retirement_requested = 1;', 'goto done;'):
            self.assertIn(required, diagnostic)
        for forbidden in ('absence_observed =', 'notification_pending =', 'return 1', 'RegNotifyChangeKeyValue',
                          'ResetEvent', 'start_watchdog'):
            self.assertNotIn(forbidden, diagnostic)
        self.assertIn('if (!hive_unloaded) cleanup = 0;', self.source)
        self.assertIn('if (!cleanup) result = 8;', self.source)
        wrapper = (NATIVE / 'check-hosted-profile-initialization.ps1').read_text()
        self.assertEqual(wrapper.count('$diagnosticRetireOnMiss = $true'), 1)
        self.assertIn('$diagnosticRetireOnMiss -and $null -ne $result.hiveObserverSnapshot', wrapper)
        self.assertIn("$result.hiveObserverSnapshot.state -eq 2) { throw", wrapper)

    def test_only_allowlisted_evidence_uploaded(self):
        source = (ROOT / '.github/workflows/desktop-cross-host.yml').read_text()
        section = source.split('name: rpc-profile-environment-', 1)[1].split('      - name:', 1)[0]
        self.assertIn('p2pkit-profile-initialization/environment-result.json', section)
        self.assertNotIn('*', section)
        self.assertNotIn('profile/', section)
        self.assertIn('if-no-files-found: error', section)


if __name__ == '__main__':
    unittest.main()
