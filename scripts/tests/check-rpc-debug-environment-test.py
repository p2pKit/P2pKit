#!/usr/bin/env python3
"""Offline scope/recipe mutation tripwires, NOT Windows debugging or custody qualification."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/windows/profile_debug_environment_probe.c"


def verify(source):
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    for forbidden in (
        "AdjustTokenPrivileges", "LsaAddAccountRights", "SetNamedSecurityInfo", "CreateProcessAsUser",
        "CreateProcessWithToken", "LOGON_WITH_PROFILE", "LoadUserProfile", "LoadLibrary", "pwp_win_",
        "DebugSetProcessKillOnExit(FALSE)", "OpenProcess(", "CREATE_BREAKAWAY_FROM_JOB",
    ):
        if forbidden in source:
            raise ValueError("Unauthorized capability or alternate launch: " + forbidden)
    broker = source[source.index("static int debug_broker("):source.index("static int debug_controller(")]
    controller = source[source.index("static int debug_controller("):source.index("static HANDLE parse_handle(")]
    ordered = (
        "CreateProcessWithLogonW(name, L\".\", password, 0, executable, command,",
        "DEBUG_ONLY_THIS_PROCESS | CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW",
        "DebugSetProcessKillOnExit(TRUE)",
        "!CheckRemoteDebuggerPresent(process.value, &debugger_attached) || !debugger_attached",
        "!EqualSid(expected, actual)", "if (mode != DEATH_PRE_JOB)",
        "AssignProcessToJobObject(job.value, process.value)", "!verified_member(process.value, job.value)",
        "DebugActiveProcessStop(pi.dwProcessId)",
        "!CheckRemoteDebuggerPresent(process.value, &debugger_attached) || debugger_attached",
        "DuplicateHandle(GetCurrentProcess(), process.value, controller, &borrowed,",
        "note.handle = (uintptr_t)borrowed", "WaitForSingleObject(gate, remaining(&watch))",
        "mode != TRANSFER_NORMAL || !detached", "ResumeThread(thread.value)",
    )
    cursor = 0
    for required in ordered:
        found = broker.find(required, cursor)
        if found < 0:
            raise ValueError("Missing/reordered broker boundary: " + required)
        cursor = found + len(required)
    if broker.count("ResumeThread(") != 1 or controller.count("ResumeThread(") != 1:
        raise ValueError("Exactly one checked resume at each layer")
    for required in (
        "PROC_THREAD_ATTRIBUTE_JOB_LIST", "PROC_THREAD_ATTRIBUTE_HANDLE_LIST",
        "!verified_member(process.value, job.value)",
        "if (mode == TRANSFER_NORMAL)", "TerminateProcess(process.value, 125)",
        "WaitForSingleObject(child_process.value, remaining(&watch))", "child_exit_observed = 1",
        "child_exit != CHILD_EXIT", "child_exit == CHILD_EXIT || child_exit == STILL_ACTIVE",
        "if (!close_once(&child_process))", "if (job.value && !await_empty_job(job.value, &watch))",
        "if (account_created)", "UF_ACCOUNTDISABLE", "if (!cleanup) result = 8",
        "DEBUG_BOOTSTRAP_CUSTODY_EXPERIMENT_NOT_PROTECTED_SUPERVISION",
    ):
        if required not in controller:
            raise ValueError("Missing outer contract: " + required)
    # Error recovery is distinct from the automatic-retirement observation, never a successful fallback.
    fault = controller[controller.index("if (mode == TRANSFER_NORMAL)"):controller.index("done:")]
    if "TerminateProcess(child_process" in fault:
        raise ValueError("The child must retire automatically during the actual control")
    if "WaitForSingleObject(child_process.value, remaining(&watch))" not in fault:
        raise ValueError("Automatic child retirement must be observed before cleanup")
    before_spawn = controller[:controller.index("CreateProcessW(")]
    if "PROC_THREAD_ATTRIBUTE_JOB_LIST" not in before_spawn or "PROC_THREAD_ATTRIBUTE_HANDLE_LIST" not in before_spawn:
        raise ValueError("Broker starts atomically owned with explicit handle inheritance")


class DebugEnvironmentRecipeTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text()

    def test_maintained_recipe_contract(self):
        verify(self.source)

    def test_forbidden_capabilities_are_rejected(self):
        for api in ("AdjustTokenPrivileges", "LsaAddAccountRights", "CreateProcessAsUserW", "LoadLibraryW",
                    "LOGON_WITH_PROFILE", "OpenProcess(", "DebugSetProcessKillOnExit(FALSE)"):
            with self.subTest(api=api), self.assertRaises(ValueError):
                verify(self.source + "\n" + api + ";\n")

    def test_creation_and_attachment_protection_cannot_disappear(self):
        for token in ("DEBUG_ONLY_THIS_PROCESS |", "CREATE_SUSPENDED |", "DebugSetProcessKillOnExit(TRUE)",
                      "!CheckRemoteDebuggerPresent(process.value, &debugger_attached) || !debugger_attached",
                      "!EqualSid(expected, actual)"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                verify(self.source.replace(token, "REMOVED", 1))

    def test_job_transfer_cannot_be_skipped(self):
        for token in ("AssignProcessToJobObject(job.value, process.value)", "!verified_member(process.value, job.value)",
                      "DebugActiveProcessStop(pi.dwProcessId)", "mode != TRANSFER_NORMAL || !detached"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                verify(self.source.replace(token, "REMOVED", 1))

    def test_exact_child_borrow_and_observation_are_mandatory(self):
        for token in ("DuplicateHandle(GetCurrentProcess(), process.value, controller, &borrowed,",
                      "note.handle = (uintptr_t)borrowed", "child_exit_observed = 1",
                      "WaitForSingleObject(child_process.value, remaining(&watch))"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                verify(self.source.replace(token, "REMOVED", 1))

    def test_outer_atomic_admission_and_handle_list_are_mandatory(self):
        for token in ("PROC_THREAD_ATTRIBUTE_JOB_LIST", "PROC_THREAD_ATTRIBUTE_HANDLE_LIST"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                verify(self.source.replace(token, "REMOVED", 1))

    def test_fault_control_cannot_terminate_standard_child(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("fault_injected = 1;", "fault_injected = 1; TerminateProcess(child_process.value, 125);"))

    def test_cleanup_uncertainty_remains_fatal(self):
        for token in ("if (job.value && !await_empty_job(job.value, &watch))", "if (!cleanup) result = 8"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                verify(self.source.replace(token, "REMOVED"))

    def test_explicit_selectors_include_each_transfer_boundary(self):
        for selector in ("normal", "prejob-death", "job-death", "detached-death"):
            self.assertEqual(1, self.source.count('L"--disposable-debug-' + selector + '-probe"'))

    def test_never_replaces_shared_supervisor(self):
        self.assertNotIn("audit_processes", self.source)
        self.assertIn('#include "profile_account_probe.c"', self.source)
        self.assertIn('\\"profileRequested\\":false', self.source)
        self.assertIn('\\"nativeStorageExecuted\\":false', self.source)

    def test_hosted_wrapper_binds_exact_source_and_scope(self):
        wrapper = (SOURCE.parent / "check-hosted-debug-environment.ps1").read_text()
        for required in ("$head -cne $env:GITHUB_SHA", "source = $head; tree = $tree",
                         "profileRuntime = 'NOT_PERFORMED'", "jniRuntime = 'NOT_PERFORMED'",
                         "protectedSupervisor = 'NOT_QUALIFIED'", "[IO.FileMode]::CreateNew",
                         "refs/heads/work/rpc-windows-validation-20261012"):
            self.assertIn(required, wrapper)
        self.assertNotIn("continue-on-error", wrapper)

    def test_hosted_wrapper_executes_all_four_modes_and_exact_negative_outcomes(self):
        wrapper = (SOURCE.parent / "check-hosted-debug-environment.ps1").read_text()
        self.assertIn("@('normal', 'prejob-death', 'job-death', 'detached-death')", wrapper)
        self.assertIn('"--disposable-debug-$mode-probe" $output $mode 70000', wrapper)
        for required in ("$record.mode -ne $index", "$record.stage -ne 6", "$record.systemCode -ne 0",
                         "$record.childExit -ne 42", "$record.brokerExit -ne 0",
                         "$record.childExit -in @(42, 259)", "$record.brokerExit -ne 125",
                         "-not $record.childExitObserved", "-not $record.cleanupObserved"):
            self.assertIn(required, wrapper)

    def test_hosted_workflow_retains_only_explicit_debug_experiment_evidence(self):
        workflow = (ROOT / ".github/workflows/desktop-cross-host.yml").read_text()
        scoped = workflow[workflow.index("  rpc-windows-environment:"):]
        self.assertIn("check-hosted-debug-environment.ps1", scoped)
        self.assertIn("os: [windows-2022, windows-latest]", scoped)
        selection = "(inputs.rpc_windows_environment_case == 'all' || inputs.rpc_windows_environment_case == 'debug')"
        self.assertIn("if: ${{ !cancelled() && " + selection + " }}", scoped)
        self.assertIn("if: ${{ always() && " + selection + " }}", scoped)
        self.assertIn("default: all", workflow)
        self.assertNotIn("continue-on-error", scoped)
        for selector in ("normal", "prejob-death", "job-death", "detached-death"):
            self.assertIn("p2pkit-debug-environment/" + selector + "-stdout.log", scoped)
        self.assertNotIn("p2pkit-debug-environment/*", scoped)


if __name__ == "__main__":
    unittest.main()
