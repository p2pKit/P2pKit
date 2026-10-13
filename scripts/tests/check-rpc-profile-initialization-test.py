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
                     'hive_absent_before = 1;', 'hive_loaded = 1;', 'await_hive_absent(sid_text, &watch)',
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
             'await_hive_absent(sid_text, &watch)']]
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

    def test_hive_queries_preserve_original_budget_and_errors(self):
        body = self.source.split('static int await_hive_absent(', 1)[1].split('static int bootstrap(', 1)[0]
        self.assertEqual(body.count('remaining(watch)'), 2)
        self.assertIn('if (!hive_state(sid, &present)) return 0;', body)
        self.assertIn('if (!present) return 1;', body)
        self.assertNotIn('start_watchdog', body)
        self.assertNotIn('Unload', body)
        self.assertNotIn('Delete', body)

    def test_wrapper_keeps_profile_and_jni_unqualified(self):
        source = (NATIVE / 'check-hosted-profile-initialization.ps1').read_text()
        for required in ("$env:GITHUB_JOB -cne 'rpc-windows-environment'", "$head -cne $env:GITHUB_SHA",
                         "profileRuntime = 'NOT_PERFORMED'", "jniRuntime = 'NOT_PERFORMED'",
                         "protectedSupervisor = 'NOT_QUALIFIED'", '[IO.FileMode]::CreateNew',
                         '-not $record.hiveAbsentBefore', '-not $record.hiveLoadedBeforeResume',
                         '-not $record.hiveUnloadedAfterExit', '$record.profileProbeExit -ne 0',
                         '$record.bootstrapAtomicJobAdmission', '$record.nativeStorageExecuted'):
            self.assertIn(required, source)
        self.assertNotIn('Start-Process -Credential', source)

    def test_only_allowlisted_evidence_uploaded(self):
        source = (ROOT / '.github/workflows/desktop-cross-host.yml').read_text()
        section = source.split('name: rpc-profile-environment-', 1)[1].split('      - name:', 1)[0]
        self.assertIn('p2pkit-profile-initialization/environment-result.json', section)
        self.assertNotIn('*', section)
        self.assertNotIn('profile/', section)
        self.assertIn('if-no-files-found: error', section)


if __name__ == '__main__':
    unittest.main()
