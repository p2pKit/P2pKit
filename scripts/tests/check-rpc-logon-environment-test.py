#!/usr/bin/env python3
"""Offline source tripwires, not a C compiler or Windows/runtime qualification."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/windows"


def verify(source):
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    for forbidden in ("AdjustTokenPrivileges", "LsaAddAccountRights", "LOGON_NETCREDENTIALS_ONLY",
                      "LOGON_WITH_PROFILE", "BREAKAWAY", "LoadLibrary", "pwp_win_", "SetNamedSecurityInfo",
                      "CreateProcessAsUserW", "CreateProcessWithTokenW", "LoadUserProfile"):
        if forbidden in source:
            raise ValueError(forbidden)
    for required in ('#include "profile_account_probe.c"', "CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT",
                     "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE", "standard_token(child_token.value)",
                     "!EqualSid(expected, actual)", "!await_empty_job(job.value, &watch)", "UF_ACCOUNTDISABLE",
                     "run_probe(EXISTING_STANDARD_USER)", "child_exit != 0", "NetUserSetInfo",
                     "if (!cleanup) result = 8;", "SecureZeroMemory(password, sizeof(password))",
                     'L"--disposable-logon-environment-probe"', 'L"--same-token-environment-child"'):
        if required not in source:
            raise ValueError(required)
    if source.count("CreateProcessWithLogonW(") != 1 or "CreateProcessWithLogonW(name, L\".\", password, 0," not in source:
        raise ValueError("Expected one separately selected no-profile logon")
    positions = [source.index(x) for x in ("CreateProcessWithLogonW(", "AssignProcessToJobObject(",
                 "IsProcessInJob(", "standard_token(child_token.value)", "ResumeThread(")]
    if positions != sorted(positions):
        raise ValueError("Wrong suspended bootstrap admission order")
    for field in ('bootstrapAtomicJobAdmission', 'profileRequested', 'nativeStorageExecuted'):
        if f'\\"{field}\\":false' not in source:
            raise ValueError("Incorrect scope claim")
    # The only accepted child is the compiled-in same-token probe, never a caller-selected payload.
    if 'argv[2]' in source or 'argc != 2' not in source:
        raise ValueError("Arbitrary payload selector")


class LogonEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.source = (NATIVE / "profile_logon_environment_probe.c").read_text()

    def test_fixed_no_storage_program(self):
        verify(self.source)

    def test_privilege_profile_and_payload_changes_fail(self):
        for api in ("AdjustTokenPrivileges", "LsaAddAccountRights", "LOGON_WITH_PROFILE", "LoadLibrary",
                    "LOGON_NETCREDENTIALS_ONLY", "LoadUserProfile", "CreateProcessWithTokenW"):
            with self.subTest(api=api), self.assertRaises(ValueError):
                verify(self.source + "\n" + api + "();")

    def test_missing_admission_or_cleanup_fails(self):
        for value in ("standard_token(child_token.value)", "!EqualSid(expected, actual)",
                      "!await_empty_job(job.value, &watch)", "UF_ACCOUNTDISABLE", "if (!cleanup) result = 8;",
                      "child_exit != 0", "CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT"):
            self.assertIn(value, self.source)
            with self.subTest(value=value), self.assertRaises(ValueError):
                verify(self.source.replace(value, "REMOVED"))

    def test_unqualified_claims_cannot_be_promoted(self):
        for field in ('bootstrapAtomicJobAdmission', 'profileRequested', 'nativeStorageExecuted'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(self.source.replace(f'\\"{field}\\":false', f'\\"{field}\\":true'))

    def test_arguments_cannot_select_arbitrary_payload(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace('argc != 2', 'argc < 2'))

    def test_job_empty_check_follows_child_reference_retirement(self):
        def order(source):
            start = source.index("done:")
            cleanup = source[start:]
            query = cleanup.index("await_empty_job(job.value")
            for owner in ("child_token", "thread", "process"):
                close = f"if (!close_once(&{owner})) cleanup = 0;"
                if cleanup.count(close) != 1 or cleanup.index(close) >= query:
                    raise ValueError("Child reference must retire once before empty-job query")
            if cleanup.index("WaitForSingleObject(process.value, 0)") >= cleanup.index("close_once(&process)"):
                raise ValueError("Exact process exit must be observed before releasing its handle")
        for file in ("profile_account_probe.c", "profile_logon_environment_probe.c"):
            source = (NATIVE / file).read_text()
            # The original account probe has an earlier child() cleanup block.
            if file == "profile_account_probe.c":
                source = source[source.index("static int run_probe("):]
            order(source)
            for owner in ("child_token", "thread", "process"):
                close = f"    if (!close_once(&{owner})) cleanup = 0;"
                bad = source.replace(close, "")
                point = "    if (!close_once(&job)) cleanup = 0;"
                bad = bad.replace(point, close + "\n" + point)
                with self.subTest(file=file, owner=owner), self.assertRaises(ValueError):
                    order(bad)

    def test_retirement_requires_zero_with_same_deadline_and_no_query_error_retry(self):
        source = (NATIVE / "profile_account_probe.c").read_text()
        body = source.split("static int await_empty_job(", 1)[1].split("static int native_x64", 1)[0]
        self.assertEqual(body.count("remaining(watch)"), 2)
        self.assertIn("&info, sizeof(info), NULL)) return 0;", body)
        self.assertIn("if (info.ActiveProcesses != 0)", body)
        self.assertIn("continue;", body)
        self.assertNotIn("start_watchdog", body)
        self.assertNotIn("Terminate", body)
        self.assertNotIn("CloseHandle", body)
        self.assertIn("#define PROBE_MS 60000u", source)

    def test_documented_residual_is_retained(self):
        self.assertIn('NOT the protected-payload supervisor', self.source)
        self.assertIn('NOT atomically assigned at creation', self.source)

    def test_wrapper_is_exact_source_bound(self):
        source = (NATIVE / "check-hosted-logon-environment.ps1").read_text()
        for value in ("$env:GITHUB_JOB -cne 'rpc-windows-environment'", "[IO.FileMode]::CreateNew",
                      "$head -cne $env:GITHUB_SHA", "Assert-ElevatedStandardUserRefusal $run $negativeText",
                      "'status', '--porcelain'", "profileRuntime = 'NOT_PERFORMED'",
                      "jniRuntime = 'NOT_PERFORMED'", "protectedSupervisor = 'NOT_QUALIFIED'",
                      "$record.bootstrapAtomicJobAdmission", "$record.profileRequested", "$record.nativeStorageExecuted",
                      "$record.stage -ne 8", "$record.sameTokenProbeExit -ne 0", "sourceHashes = $hashes"):
            self.assertIn(value, source)
        self.assertNotIn('Start-Process -Credential', source)

    def test_workflow_uses_existing_test_branch_only(self):
        source = (ROOT / '.github/workflows/desktop-cross-host.yml').read_text().split('  rpc-windows-environment:\n')[1]
        for value in ("github.event_name == 'workflow_dispatch'", "inputs.scope == 'rpc-windows-environment'",
                      "github.ref == 'refs/heads/work/rpc-windows-validation-20261012'",
                      'os: [windows-2022, windows-latest]', 'persist-credentials: false',
                      'timeout-minutes: 5', 'if-no-files-found: error', 'environment-result.json'):
            self.assertIn(value, source)
        for value in ('continue-on-error', 'secrets.', 'publish', 'p2pkit-logon-environment/*'):
            self.assertNotIn(value, source)


if __name__ == '__main__':
    unittest.main()
