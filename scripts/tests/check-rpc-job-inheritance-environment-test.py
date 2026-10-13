#!/usr/bin/env python3
"""Narrow no-fallback recipe tripwires, NOT actual Windows job-inheritance qualification."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/windows/profile_job_inheritance_environment_probe.c"


def verify(source):
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    for forbidden in ("AssignProcessToJobObject", "Debug", "DEBUG_", "CreateProcessAsUser", "CreateProcessWithToken",
                      "AdjustTokenPrivileges", "LsaAddAccountRights", "LOGON_WITH_PROFILE", "LoadUserProfile",
                      "LoadLibrary", "pwp_win_", "BREAKAWAY", "OpenProcess("):
        if forbidden in source:
            raise ValueError("Forbidden alternate admission/payload: " + forbidden)
    broker = source[source.index("static int inheritance_broker("):source.index("static int inheritance_controller(")]
    controller = source[source.index("static int inheritance_controller("):source.index("static HANDLE parse_handle(")]
    if source.count("CreateProcessWithLogonW(") != 1 or source.count("CreateProcessW(") != 1:
        raise ValueError("One explicit broker and one credentialed child")
    for required in ("password, 0, executable, command", "CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW",
                     "!EqualSid(expected, actual)", "note.handle = (uintptr_t)borrowed",
                     "WaitForSingleObject(gate, remaining(&watch))", "if (mode != INHERIT_NORMAL) goto done"):
        if required not in broker:
            raise ValueError("Missing broker contract: " + required)
    before_create = controller[:controller.index("CreateProcessW(")]
    for required in ("PROC_THREAD_ATTRIBUTE_JOB_LIST", "PROC_THREAD_ATTRIBUTE_HANDLE_LIST",
                     "handles[] = {self.value, pipe_write.value, gate.value}"):
        if required not in before_create:
            raise ValueError("Missing atomic admission/strict handle list")
    if "job.value" in before_create[before_create.index("handles[]"):before_create.index("handles[]") + 60]:
        raise ValueError("Job handle must not be inherited")
    boundary = controller[controller.index("BOOL member = FALSE;"):controller.index("done:")]
    ordered = ("IsProcessInJob(child_process.value, job.value, &member)", "inherited_member = member != FALSE",
               "if (!inherited_member) goto done", "if (mode == INHERIT_NORMAL)", "SetEvent(gate.value)",
               "accounting.ActiveProcesses != 2", "exact_two_before_close = 1", "if (!close_once(&job))",
               "fault_injected = 1", "WaitForSingleObject(child_process.value, remaining(&watch))",
               "child_exit_observed = 1", "WaitForSingleObject(process.value, remaining(&watch))")
    cursor = 0
    for required in ordered:
        found = boundary.find(required, cursor)
        if found < 0:
            raise ValueError("Missing/reordered exact observation: " + required)
        cursor = found + len(required)
    if "TerminateProcess" in boundary:
        raise ValueError("Successful observation cannot substitute explicit process termination")
    for required in ("if (job.value) {", "empty_job_observed = await_empty_job(job.value, &watch)",
                     "UF_ACCOUNTDISABLE", "if (!cleanup) result = 8",
                     "LOGON_JOB_INHERITANCE_EXPERIMENT_NOT_PROTECTED_SUPERVISION"):
        if required not in controller:
            raise ValueError("Missing bounded cleanup/scope: " + required)


class InheritanceRecipeTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text()

    def test_maintained_source(self):
        verify(self.source)

    def test_no_post_create_assignment_debugger_privilege_or_storage_substitute(self):
        for api in ("AssignProcessToJobObject", "DebugActiveProcess", "CreateProcessWithTokenW",
                    "AdjustTokenPrivileges", "LoadLibraryW", "LOGON_WITH_PROFILE"):
            with self.subTest(api=api), self.assertRaises(ValueError):
                verify(self.source + "\n" + api + "();")

    def test_actual_membership_observation_cannot_be_omitted(self):
        for required in ("IsProcessInJob(child_process.value, job.value, &member)",
                         "if (!inherited_member) goto done", "inherited_member = member != FALSE"):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))

    def test_gate_remains_after_membership_and_before_any_resume(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("WaitForSingleObject(gate, remaining(&watch))", "WAIT_OBJECT_0"))

    def test_owner_close_requires_exact_two_known_gated_processes(self):
        for required in ("accounting.ActiveProcesses != 2", "exact_two_before_close = 1",
                         "WaitForSingleObject(child_process.value, remaining(&watch))"):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))

    def test_job_handle_never_inherited(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("handles[] = {self.value,", "handles[] = {job.value, self.value,"))

    def test_success_cannot_explicitly_terminate_standard_child(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("fault_injected = 1;", "fault_injected = 1; TerminateProcess(child_process.value, 125);"))

    def test_no_false_profile_or_release_claim(self):
        for required in ('\\"profileRequested\\":false', '\\"nativeStorageExecuted\\":false'):
            self.assertIn(required, self.source)
        self.assertNotIn("audit_processes", self.source)
        self.assertNotIn("--disposable-debug-", self.source)

    def test_wrapper_keeps_normal_job_zero_distinct_from_last_handle_close(self):
        wrapper = (SOURCE.parent / "check-hosted-job-inheritance-environment.ps1").read_text()
        for required in ("$modes = @('normal', 'owner-close')", "$record.mode -ne $index",
                         "-not $record.inheritedMember", "-not $record.emptyJobObserved",
                         "-not $record.lastJobHandleClosed", "-not $record.exactTwoBeforeClose",
                         "$record.emptyJobObserved -or $record.childExit -in @(42, 259)",
                         "$record.brokerExit -eq 259", "$record.brokerExit -ne 0"):
            self.assertIn(required, wrapper)

    def test_wrapper_exact_source_and_no_protected_payload_claim(self):
        wrapper = (SOURCE.parent / "check-hosted-job-inheritance-environment.ps1").read_text()
        for required in ("source = $head; tree = $tree", "$head -cne $env:GITHUB_SHA",
                         "profileRuntime = 'NOT_PERFORMED'", "jniRuntime = 'NOT_PERFORMED'",
                         "protectedSupervisor = 'NOT_QUALIFIED'", "[IO.FileMode]::CreateNew"):
            self.assertIn(required, wrapper)

    def test_workflow_explicit_selection_preserves_failed_debugger_controls(self):
        workflow = (ROOT / ".github/workflows/desktop-cross-host.yml").read_text()
        self.assertIn("default: all", workflow)
        for selector in ("inheritance", "debug"):
            condition = "(inputs.rpc_windows_environment_case == 'all' || inputs.rpc_windows_environment_case == '" + selector + "')"
            self.assertIn("!cancelled() && " + condition, workflow)
            self.assertIn("always() && " + condition, workflow)
        self.assertNotIn("p2pkit-inheritance-environment/*", workflow)


if __name__ == "__main__":
    unittest.main()
