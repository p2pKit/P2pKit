#!/usr/bin/env python3
"""Narrow offline recipe tripwires; NOT compiler, Windows-token or runtime qualification."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent


def body(source, marker):
    """Read the one braced source block after an exact reviewed marker (not a C parser)."""
    if source.count(marker) != 1:
        raise ValueError("Missing/ambiguous fixed admission marker")
    start = source.index("{", source.index(marker))
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1:index]
    raise ValueError("Unterminated admission block")


def verify(source):
    # Comments excluded so a missing operation cannot be replaced by a claim in a comment.
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    for forbidden in ("AdjustTokenPrivileges", "LsaAddAccountRights", "AssignProcessToJobObject",
                      "CreateProcessWithTokenW", "CreateProcessWithLogonW", "LoadUserProfile",
                      "LoadLibrary", "pwp_win_"):
        if forbidden in source:
            raise ValueError("Unexpected mutation/fallback/profile operation: " + forbidden)
    if source.count("CreateProcessW(") != 1 or source.count("CreateProcessAsUserW(") != 1:
        raise ValueError("Expected exactly two independently selected launch APIs")
    # These are the two explicit selection blocks, not a retry based on GetLastError.
    sections = re.findall(r"if \(environment_kind == EXISTING_STANDARD_USER\) \{", source)
    if len(sections) != 2:
        raise ValueError("Expected explicit admission and launch selection")
    account_marker = "if (environment_kind == EXISTING_STANDARD_USER) {"
    first = source.index(account_marker)
    second = source.index(account_marker, first + len(account_marker))
    standard = body(source[first:second], account_marker)
    if "OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token.value)" not in standard:
        raise ValueError("Existing standard session must query its own token only")
    if any(value in standard for value in ("credentials(", "NetUser", "LogonUser", "ordinary_group")):
        raise ValueError("Existing standard session must not provision or switch users")
    for required in ("GetTokenInformation(token.value, TokenElevation, &elevation, sizeof(elevation), &elevation_size)",
                     "elevation_size != sizeof(elevation)",
                     "if (elevation.TokenIsElevated) { result = 3; stage = 10; goto done; }"):
        if required not in standard:
            raise ValueError("Elevated refusal must be positively observed, not an unavailable query")
    launch = body(source[second:], account_marker)
    for required in ("CreateProcessW(executable, command, NULL, NULL, FALSE,",
                     "CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW",
                     "error = GetLastError(); goto done;"):
        if required not in launch:
            raise ValueError("Missing fail-closed same-token launch boundary")
    if "CreateProcessAsUserW" in launch:
        raise ValueError("No cross-token fallback in same-token lane")
    if not first < source.index("standard_token(token.value)", first) < second:
        raise ValueError("Standard token must be admitted before launch")
    job = source.index("PROC_THREAD_ATTRIBUTE_JOB_LIST")
    verify_job = source.index("IsProcessInJob(process.value, job.value")
    verify_sid = source.index("!EqualSid(expected_sid, observed_sid)")
    resume = source.index("ResumeThread(thread.value)")
    if not job < second < verify_job < verify_sid < resume:
        raise ValueError("Precreation job binding and original-token verification must precede resume")
    for required in ("info.ActiveProcesses != 0", "if (account_created)", "NetUserSetInfo",
                     'L"--existing-disposable-standard-user-probe"', "run_probe(EXISTING_STANDARD_USER)",
                     'L"--disposable-account-admission-probe"', "run_probe(FRESH_CREDENTIALED_ACCOUNT)",
                     '"EXISTING_STANDARD_USER_ADMISSION_NOT_SMOKE_OR_RELEASE"',
                     '"ACCOUNT_ADMISSION_FEASIBILITY_NOT_SMOKE_OR_RELEASE"'):
        if required not in source:
            raise ValueError("Missing retained ownership/scope contract")


class StandardEnvironmentSourceTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "profile_account_probe.c").read_text()

    def test_maintained_source_separates_explicit_modes(self):
        verify(self.source)

    def test_forbidden_privilege_and_launch_substitutions_are_detected(self):
        for api in ("AdjustTokenPrivileges", "LsaAddAccountRights", "AssignProcessToJobObject",
                    "CreateProcessWithTokenW", "CreateProcessWithLogonW", "LoadUserProfile", "LoadLibrary"):
            with self.subTest(api=api), self.assertRaises(ValueError):
                verify(self.source + "\n" + api + "();\n")

    def test_missing_same_token_contracts_are_detected(self):
        for original, replacement in (
            ("OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token.value)", "OpenWrongToken()"),
            ("PROC_THREAD_ATTRIBUTE_JOB_LIST", "NO_JOB_LIST"),
            ("CREATE_SUSPENDED |", "0 |"),
            ("FALSE,\n            CREATE_SUSPENDED", "TRUE,\n            CREATE_SUSPENDED"),
            ("info.ActiveProcesses != 0", "FALSE"),
            ("!EqualSid(expected_sid, observed_sid)", "FALSE"),
            ("EXISTING_STANDARD_USER_ADMISSION_NOT_SMOKE_OR_RELEASE", "PASS"),
            ("run_probe(EXISTING_STANDARD_USER)", "run_probe(FRESH_CREDENTIALED_ACCOUNT)"),
        ):
            self.assertIn(original, self.source)
            with self.subTest(mutation=original), self.assertRaises(ValueError):
                verify(self.source.replace(original, replacement))

    def test_admission_cannot_be_only_a_comment(self):
        original = "OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token.value)"
        with self.assertRaises(ValueError):
            verify(self.source.replace(original, "/* " + original + " */ false"))

    def test_missing_explicit_elevation_observation_is_detected(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("elevation.TokenIsElevated", "1"))

    def test_hosted_refusal_wrapper_retains_fixed_negative_only_contract(self):
        source = (ROOT / "check-hosted-standard-user-refusal.ps1").read_text()
        for forbidden in ("--disposable-account-admission-probe", "--disposable-custody-smoke",
                          "AdjustTokenPrivileges", "NetUserAdd", "Set-LocalUser", "LoadUserProfile"):
            self.assertNotIn(forbidden, source)
        for required in ("-not $IsWindows", "$env:ImageOS -cne 'win22'",
                         "$env:GITHUB_REF -cne 'refs/heads/work/rpc-windows-validation-20261012'",
                         "$env:GITHUB_JOB -cne 'rpc-windows'", "$env:RUNNER_ENVIRONMENT -cne 'github-hosted'",
                         "$build.source -cne $head[0]", "$build.tree -cne $tree[0]",
                         "$build.nativeBuild -cne 'PASS'", "$build.run -cne $env:GITHUB_RUN_ID",
                         "$build.attempt -cne $env:GITHUB_RUN_ATTEMPT",
                         "[IO.FileMode]::CreateNew", "Invoke-PolicyCommand $probe",
                         "'--existing-disposable-standard-user-probe' $output 'probe' 10000",
                         "$record.stage -ne 10", "$record.systemCode -ne 0", "$Run.exitCode -ne 3",
                         "$record.accountCreated -or $record.created", "$record.resumed -or",
                         "-not $record.cleanupObserved", "$record.nativeStorageExecuted",
                         "-not $Run.finalizationCompleted", "$Run.elapsedMs -ge 10000",
                         "standardUserPositiveExecution = 'NOT_PERFORMED'",
                         "smokeSupervisorQualification = 'NOT_PERFORMED'", "accountMutation = 'NOT_PERFORMED'"):
            self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
