#!/usr/bin/env python3
"""Narrow no-fallback recipe tripwires, NOT actual Windows job-inheritance qualification."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/windows/profile_job_inheritance_environment_probe.c"
PARENT_PULL = (
    "if (!DuplicateHandle(process.value, (HANDLE)note.handle, GetCurrentProcess(), &child_process.value,\n"
    "        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE | PROCESS_DUP_HANDLE | SYNCHRONIZE, FALSE, 0)) {\n"
    "        error = GetLastError(); goto done;\n"
    "    }"
)


def require_ordered(source, steps, message):
    cursor = 0
    for step in steps:
        found = source.find(step, cursor)
        if found < 0:
            raise ValueError(message + ": " + step)
        cursor = found + len(step)


def verify_compare_import(wrapper):
    # OneCore's SDK import member resolves the unchanged API through the Windows handle API-set.
    # SDK package inspection is supporting evidence, not a substitute for the actual hosted linker.
    expected = "kernel32.lib OneCore.lib advapi32.lib netapi32.lib bcrypt.lib"
    if wrapper.count(expected) != 1 or re.search(r"\bkernelbase\.lib\b", wrapper, re.IGNORECASE):
        raise ValueError("Use the supplied SDK OneCore import, not unavailable Kernelbase.lib")


def verify(source):
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    for forbidden in ("AssignProcessToJobObject", "Debug", "DEBUG_", "CreateProcessAsUser", "CreateProcessWithToken",
                      "AdjustTokenPrivileges", "LsaAddAccountRights", "LOGON_WITH_PROFILE", "LoadUserProfile",
                      "LoadLibrary", "pwp_win_", "BREAKAWAY"):
        if forbidden in source:
            raise ValueError("Forbidden alternate admission/payload: " + forbidden)
    broker = source[source.index("static int inheritance_broker("):source.index("static int inheritance_controller(")]
    controller = source[source.index("static int inheritance_controller("):source.index("static HANDLE parse_handle(")]
    diagnostic = source[source.index("static int diagnose_job("):source.index("static int inheritance_broker(")]
    handle_observer = source[source.index("static int observe_known_handle("):source.index("static int known_handle_controls(")]
    pipe_reader = source[source.index("static int read_broker_note("):source.index("enum { KNOWN_HANDLE_ERROR")]
    note_reader = source[source.index("static int read_note("):source.index("static int read_broker_note(")]
    helper_controls = source[source.index("static int known_handle_controls("):source.index("static int fresh_account_name(")]
    for required in ("if (!ReadFile(pipe, note, sizeof(*note), &read, NULL)) { *error = GetLastError(); return 0; }",
                     "*error = ERROR_INVALID_DATA; return 0"):
        if required not in note_reader:
            raise ValueError("Fixed-note failure must retain API versus malformed-data error")
    for name in ("first", "second"):
        creation = name + ".value = CreateEventW(NULL, TRUE, FALSE, NULL);"
        capture = "if (!" + name + ".value) { *error = GetLastError(); goto done; }"
        if creation + "\n    " + capture not in helper_controls:
            raise ValueError("Event creation error must be captured before another API: " + name)
    for required in ("DuplicateHandle(process, candidate, GetCurrentProcess(), &observed.value, 0, FALSE, DUPLICATE_SAME_ACCESS)",
                     "if (*error == ERROR_INVALID_HANDLE) { *error = ERROR_SUCCESS; return KNOWN_HANDLE_ABSENT; }",
                     "SetLastError(ERROR_SUCCESS)", "CompareObjectHandles(observed.value, expected)",
                     "result = KNOWN_HANDLE_LEAK",
                     "if (*error == ERROR_NOT_SAME_OBJECT) { *error = ERROR_SUCCESS; result = KNOWN_HANDLE_REUSED; }",
                     "if (!close_once(&observed)) { *error = GetLastError(); result = KNOWN_HANDLE_ERROR; }"):
        if required not in handle_observer:
            raise ValueError("Missing exact-object known-value observation: " + required)
    for required in ("PeekNamedPipe(pipe, NULL, 0, NULL, &available, NULL)",
                     "if (available >= sizeof(*note)) return read_note(pipe, note, error)",
                     "DWORD budget = remaining(watch)", "WaitForSingleObject(broker, budget < 10 ? budget : 10)",
                     "*error = waited == WAIT_FAILED ? GetLastError() : ERROR_INVALID_DATA; return 0",
                     "*error = available ? ERROR_INVALID_DATA : ERROR_BROKEN_PIPE; return 0"):
        if required not in pipe_reader:
            raise ValueError("Retained pipe comparator cannot conceal broker death: " + required)
    if pipe_reader.count("if (!PeekNamedPipe(pipe, NULL, 0, NULL, &available, NULL)) "
                         "{ *error = GetLastError(); return 0; }") != 2:
        raise ValueError("Observe complete fixed notes before blocking and after exact broker death")
    if controller.count("read_broker_note(pipe_read.value, process.value, &watch, &note, &error)") != 2:
        raise ValueError("Both pre-audit notes need exact-broker bounded observation")
    if "if (!read_note(pipe_read.value, &note, &error)) goto done;" not in controller:
        raise ValueError("Final-note read error must not be overwritten by empty note fields")
    if source.count("OpenProcess(") != 1 or diagnostic.count("OpenProcess(") != 1:
        raise ValueError("Process handles may be acquired only from the bounded original-job diagnostic")
    for required in ("INVENTORY_LIMIT = 16", "JobObjectBasicProcessIdList", "list->ProcessIdList[i]",
                     "!IsProcessInJob(original.value, job, &member)", "GetProcessTimes(original.value"):
        if required not in diagnostic:
            raise ValueError("Missing bounded job/lifetime diagnostic")
    if source.count("CreateProcessWithLogonW(") != 1 or source.count("CreateProcessW(") != 1:
        raise ValueError("One explicit broker and one credentialed child")
    if "DuplicateHandle(" in broker or "child_process.value = (HANDLE)note.handle" in controller:
        raise ValueError("Broker must not inject receiver handles or make raw values receiver-owned")
    if controller.count(PARENT_PULL) != 1:
        raise ValueError("Parent must pull one owned noninheritable handle from the original broker")
    for required in ("password, 0, executable, command", "CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW",
                     "!EqualSid(expected, actual)", "note.handle = (uintptr_t)process.value",
                     "WaitForSingleObject(gate, remaining(&watch))", "if (mode != INHERIT_NORMAL) goto done"):
        if required not in broker:
            raise ValueError("Missing broker contract: " + required)
    publication = broker.index("note.handle = (uintptr_t)process.value")
    gate = broker.index("if (WaitForSingleObject(gate, remaining(&watch))")
    if not broker.index("!EqualSid(expected, actual)") < publication < gate or \
            "close_once(&process)" in broker[:gate]:
        raise ValueError("Broker must retain its token-checked exact source handle until parent gate")
    if "NetUserSetInfo(" in broker or broker.count("WaitForSingleObject(gate, remaining(&watch))") != 2:
        raise ValueError("Only controller enables acknowledged account; two distinct broker gate waits required")
    require_ordered(broker, (
        "account.usri1_flags = UF_SCRIPT | UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE",
        "error = NetUserAdd(NULL, 1, (LPBYTE)&account, &parameter)",
        "if (error != NERR_Success) goto done",
        "note.kind = NOTE_ACCOUNT; memcpy(note.account, name, sizeof(name))",
        "if (!write_note(pipe, &note)) goto done",
        "DWORD account_wait = WaitForSingleObject(gate, remaining(&watch))",
        "if (account_wait != WAIT_OBJECT_0)",
        "error = account_wait == WAIT_FAILED ? GetLastError() : ERROR_INVALID_DATA; goto done",
        "error = ordinary_group(name)", "LogonUserW(name,", "CreateProcessWithLogonW(name,",
        "note.kind = NOTE_CHILD; note.handle = (uintptr_t)process.value",
        "if (!write_note(pipe, &note)) goto done",
        "if (WaitForSingleObject(gate, remaining(&watch)) != WAIT_OBJECT_0) goto done",
        "ResumeThread(thread.value)",
    ), "Disabled account and two-phase gate order must remain explicit")
    before_create = controller[:controller.index("CreateProcessW(")]
    for required in ("PROC_THREAD_ATTRIBUTE_JOB_LIST", "PROC_THREAD_ATTRIBUTE_HANDLE_LIST",
                     "handles[] = {self.value, pipe_write.value, gate.value}",
                     "gate.value = CreateEventW(&security, FALSE, FALSE, NULL)",
                     "&self.value,\n            PROCESS_QUERY_LIMITED_INFORMATION, TRUE, 0",
                     "&pipe_comparator.value,\n            0, FALSE, DUPLICATE_SAME_ACCESS"):
        if required not in before_create:
            raise ValueError("Missing atomic admission/strict handle list")
    if "job.value" in before_create[before_create.index("handles[]"):before_create.index("handles[]") + 60]:
        raise ValueError("Job handle must not be inherited")
    enable = "error = NetUserSetInfo(NULL, account, 1008, (LPBYTE)&enabled, &parameter)"
    signal = "if (!SetEvent(gate.value)) { error = GetLastError(); goto done; }"
    if controller.count(enable) != 1 or controller.count(signal) != 2:
        raise ValueError("One owned-account enable and exactly two controller phase signals")
    boundary = controller[controller.index("stage = 3;"):controller.index("done:")]
    ordered = ("if (note.kind != NOTE_ACCOUNT || !fresh_account_name(note.account)) goto done",
               "account_created = 1; memcpy(account, note.account, sizeof(account))",
               "USER_INFO_1008 enabled = {UF_SCRIPT | UF_NORMAL_ACCOUNT}", enable,
               "if (error != NERR_Success) goto done", signal,
               "if (!read_broker_note(pipe_read.value, process.value, &watch, &note, &error)) goto done",
               "if (note.kind != NOTE_CHILD || !note.handle || note.handle == (uintptr_t)INVALID_HANDLE_VALUE) goto done",
               PARENT_PULL, "child_observed = 1; stage = 4", "GetProcessId(child_process.value)",
               "IsProcessInJob(child_process.value, job.value, &member)", "inherited_member = member != FALSE",
               "if (!inherited_member) goto done", "HANDLE expected[] = {self.value, pipe_comparator.value, gate.value}",
               "for (DWORD i = 0; i < 3; ++i)",
               "observe_known_handle(child_process.value, handles[i], expected[i], &known_error)",
               "if (observation == KNOWN_HANDLE_ERROR) { error = known_error; goto done; }",
               "if (known_checked != 3 || known_leaked || known_absent + known_reused != 3)",
               "known_handles_passed = 1", "if (!close_once(&pipe_comparator)) goto done",
               "if (mode == INHERIT_NORMAL)", "SetEvent(gate.value)",
               "accounting.ActiveProcesses != 2", "exact_two_before_close = 1", "if (!close_once(&job))",
               "fault_injected = 1", "WaitForSingleObject(child_process.value, remaining(&watch))",
               "child_exit_observed = 1", "WaitForSingleObject(process.value, remaining(&watch))")
    cursor = 0
    for required in ordered:
        found = boundary.find(required, cursor)
        if found < 0:
            raise ValueError("Missing/reordered exact observation: " + required)
        cursor = found + len(required)
    if "TerminateProcess" in boundary or "TerminateJobObject" in boundary:
        raise ValueError("Successful observation cannot substitute explicit process termination")
    cleanup = controller[controller.index("done:"):]
    retirement = "if (result != 0 && !TerminateJobObject(job.value, 125))"
    if source.count("TerminateJobObject(") != 1 or retirement not in cleanup:
        raise ValueError("Retire unobserved child only through the original owned job on failure")
    if not cleanup.index("if (job.value) {") < cleanup.index(retirement) < cleanup.index("await_empty_job("):
        raise ValueError("Retire possibly unobserved child before awaiting empty original job")
    if "DWORD retirement_error = GetLastError(); cleanup = 0;" not in cleanup or \
            "if (!error) error = retirement_error;" not in cleanup or re.search(r"result\s*=\s*0\b", cleanup):
        raise ValueError("Explicit error cleanup must retain failure and retirement uncertainty")
    for required in ("if (job.value) {", "empty_job_observed = await_empty_job(job.value, &watch)",
                     "UF_ACCOUNTDISABLE", "if (!cleanup) result = 8",
                     "if (!close_once(&pipe_comparator)) cleanup = 0",
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

    def test_original_count_refusal_cannot_be_replaced_by_diagnostics(self):
        for required in ("if (!pre_close_query_succeeded || accounting.ActiveProcesses != 2)",
                         "if (!diagnose_job(job.value, process.value, child_process.value)) cleanup = 0;"):
            self.assertIn(required, self.source)
        with self.assertRaises(ValueError):
            verify(self.source + "\nOpenProcess();")

    def test_gui_fixture_prevents_console_helper_instead_of_relaxing_count(self):
        broker = self.source[self.source.index("static int inheritance_broker("):
                             self.source.index("static int inheritance_controller(")]
        broker = re.sub(r"/\*.*?\*/|//[^\n]*", "", broker, flags=re.DOTALL)
        self.assertIn("CREATE_NO_WINDOW", broker)
        self.assertNotIn("CREATE_NEW_CONSOLE", broker)
        self.assertNotIn("SW_HIDE", broker)
        self.assertNotIn("DETACHED_PROCESS", broker)
        self.assertIn("accounting.ActiveProcesses != 2", self.source)
        wrapper = (SOURCE.parent / "check-hosted-job-inheritance-environment.ps1").read_text()
        self.assertIn("/SUBSYSTEM:WINDOWS /ENTRY:wmainCRTStartup", wrapper)
        self.assertIn("$result.fixtureImage = Assert-EnvironmentFixtureImage $exe", wrapper)
        self.assertIn("[BitConverter]::ToUInt16($header, 92) -ne 2", wrapper)
        self.assertIn("ENVIRONMENT_TEST_FIXTURE_NOT_APPLICATION_LAUNCHER", wrapper)
        with self.assertRaises(ValueError):
            verify(self.source.replace("CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW",
                                       "CREATE_UNICODE_ENVIRONMENT | DETACHED_PROCESS"))

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

    def test_handle_inspection_is_parent_side_and_noninheritable(self):
        for required in (
            "PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE | PROCESS_DUP_HANDLE | SYNCHRONIZE, FALSE, 0",
            "DuplicateHandle(process, candidate, GetCurrentProcess(), &observed.value, 0, FALSE, DUPLICATE_SAME_ACCESS)",
        ):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))

    def test_broker_cannot_inject_a_receiver_handle_before_announcing_it(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("note.handle = (uintptr_t)process.value",
                                       "DuplicateHandle(); note.handle = (uintptr_t)process.value"))
        with self.assertRaises(ValueError):
            verify(self.source.replace("note.handle = (uintptr_t)process.value", "note.handle = (uintptr_t)borrowed"))
        with self.assertRaises(ValueError):
            verify(self.source.replace(PARENT_PULL, "child_process.value = (HANDLE)note.handle;"))

    def test_parent_pull_requires_original_broker_and_exact_noninherited_rights(self):
        for replacement in (
            PARENT_PULL.replace("DuplicateHandle(process.value,", "DuplicateHandle(GetCurrentProcess(),"),
            PARENT_PULL.replace("FALSE, 0", "TRUE, 0"),
            PARENT_PULL.replace("FALSE, 0", "FALSE, DUPLICATE_SAME_ACCESS"),
            PARENT_PULL.replace("&child_process.value", "&borrowed"),
            PARENT_PULL.replace("error = GetLastError();", "error = 0;"),
        ):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                verify(self.source.replace(PARENT_PULL, replacement))

    def test_parent_pull_cannot_precede_note_validation_or_follow_broker_release(self):
        removed = self.source.replace(PARENT_PULL, "")
        self.assertNotEqual(removed, self.source)
        before_note = "stage = 3;\n    if (!read_broker_note"
        after_release = "if (!SetEvent(gate.value)) { error = GetLastError(); goto done; }"
        after_release_index = removed.rindex(after_release) + len(after_release)
        for changed in (removed.replace(before_note, PARENT_PULL + "\n    " + before_note, 1),
                        removed[:after_release_index] + "\n    " + PARENT_PULL + removed[after_release_index:]):
            self.assertNotEqual(removed, changed)
            with self.assertRaises(ValueError):
                verify(changed)

    def test_broker_retains_original_handle_until_parent_observation_gate(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("note.handle = (uintptr_t)process.value",
                                       "close_once(&process); note.handle = (uintptr_t)process.value"))
        with self.assertRaises(ValueError):
            verify(self.source.replace("&self.value,\n            PROCESS_QUERY_LIMITED_INFORMATION, TRUE, 0",
                                       "&self.value,\n            PROCESS_DUP_HANDLE | PROCESS_QUERY_LIMITED_INFORMATION, TRUE, 0"))

    def test_unannounced_fresh_account_cannot_start_enabled(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("account.usri1_flags = UF_SCRIPT | UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE",
                                       "account.usri1_flags = UF_SCRIPT | UF_NORMAL_ACCOUNT"))
        with self.assertRaises(ValueError):
            verify(self.source.replace("note.kind = NOTE_ACCOUNT;", "NetUserSetInfo(); note.kind = NOTE_ACCOUNT;"))

    def test_broker_cannot_create_child_or_logon_before_account_acknowledgment(self):
        for required in ("DWORD account_wait = WaitForSingleObject(gate, remaining(&watch))",
                         "if (account_wait != WAIT_OBJECT_0)",
                         "error = account_wait == WAIT_FAILED ? GetLastError() : ERROR_INVALID_DATA; goto done"):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))

    def test_controller_must_own_exact_successful_account_before_enabling(self):
        for required in ("if (note.kind != NOTE_ACCOUNT || !fresh_account_name(note.account)) goto done",
                         "account_created = 1; memcpy(account, note.account, sizeof(account))",
                         "error = NetUserSetInfo(NULL, account, 1008, (LPBYTE)&enabled, &parameter)"):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))
        ownership = "account_created = 1; memcpy(account, note.account, sizeof(account));"
        initialization = "USER_INFO_1008 enabled = {UF_SCRIPT | UF_NORMAL_ACCOUNT};"
        with self.assertRaises(ValueError):
            verify(self.source.replace(ownership, "").replace(initialization, initialization + " " + ownership))

    def test_account_enable_failure_cannot_signal_broker(self):
        enable = "error = NetUserSetInfo(NULL, account, 1008, (LPBYTE)&enabled, &parameter);"
        refusal = "if (error != NERR_Success) goto done;"
        signal = "if (!SetEvent(gate.value)) { error = GetLastError(); goto done; }"
        original = enable + "\n    " + refusal + "\n    " + signal
        self.assertIn(original, self.source)
        with self.assertRaises(ValueError):
            verify(self.source.replace(original, enable + "\n    " + signal))
        with self.assertRaises(ValueError):
            verify(self.source.replace(original, signal + "\n    " + enable + "\n    " + refusal))

    def test_account_signal_is_consumed_before_independent_child_resume_signal(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("gate.value = CreateEventW(&security, FALSE, FALSE, NULL)",
                                       "gate.value = CreateEventW(&security, TRUE, FALSE, NULL)"))
        with self.assertRaises(ValueError):
            verify(self.source.replace("if (WaitForSingleObject(gate, remaining(&watch)) != WAIT_OBJECT_0) goto done;", ""))

    def test_account_receipt_limits_are_documented_without_runtime_claim(self):
        readme = (SOURCE.parent / "README.md").read_text()
        for required in ("false` does not prove no account was created", "untracked",
                         "**disabled** fixture account", "not a complete", "account inventory",
                         "not yet Windows execution evidence for this revision", "Controller death"):
            self.assertIn(required, readme)
        self.assertIn("containment, not complete account inventory", self.source)

    def test_handle_api_uncertainty_cannot_be_classified_as_absent_or_reused(self):
        for required in ("*error == ERROR_INVALID_HANDLE", "*error == ERROR_NOT_SAME_OBJECT",
                         "CompareObjectHandles(observed.value, expected)",
                         "if (observation == KNOWN_HANDLE_ERROR) { error = known_error; goto done; }"):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))

    def test_inspection_checks_only_known_values_and_refuses_actual_leaks(self):
        for required in ("HANDLE expected[] = {self.value, pipe_comparator.value, gate.value}",
                         "for (DWORD i = 0; i < 3; ++i)",
                         "if (known_checked != 3 || known_leaked || known_absent + known_reused != 3)"):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))

    def test_pipe_comparator_stays_until_inspection_and_closes_before_gate(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("if (!close_once(&pipe_comparator)) goto done;", ""))
        with self.assertRaises(ValueError):
            verify(self.source.replace("if (!close_once(&pipe_comparator)) cleanup = 0;", ""))
        with self.assertRaises(ValueError):
            verify(self.source.replace("0, FALSE, DUPLICATE_SAME_ACCESS) ||", "0, TRUE, DUPLICATE_SAME_ACCESS) ||", 1))

    def test_retained_writer_does_not_turn_early_broker_death_into_blocking_read(self):
        for required in ("read_broker_note(pipe_read.value, process.value, &watch, &note, &error)",
                         "PeekNamedPipe(pipe, NULL, 0, NULL, &available, NULL)",
                         "WaitForSingleObject(broker, budget < 10 ? budget : 10)"):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))

    def test_creation_errors_are_captured_before_another_api_runs(self):
        for required in ("if (!first.value) { *error = GetLastError(); goto done; }",
                         "if (!second.value) { *error = GetLastError(); goto done; }"):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))

    def test_pipe_errors_and_broker_death_are_not_replaced_by_success_codes(self):
        for required in ("if (!ReadFile(pipe, note, sizeof(*note), &read, NULL)) { *error = GetLastError(); return 0; }",
                         "*error = waited == WAIT_FAILED ? GetLastError() : ERROR_INVALID_DATA; return 0",
                         "*error = available ? ERROR_INVALID_DATA : ERROR_BROKEN_PIPE; return 0",
                         "if (!read_note(pipe_read.value, &note, &error)) goto done;"):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))

    def test_missing_child_note_failure_retires_owned_job_before_waiting_for_zero(self):
        for required in ("if (result != 0 && !TerminateJobObject(job.value, 125))",
                         "DWORD retirement_error = GetLastError(); cleanup = 0;",
                         "if (!error) error = retirement_error;"):
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify(self.source.replace(required, "REMOVED", 1))
        with self.assertRaises(ValueError):
            verify(self.source.replace("if (result != 0 && !TerminateJobObject(job.value, 125))",
                                       "if (!TerminateJobObject(job.value, 125))"))
        with self.assertRaises(ValueError):
            verify(self.source.replace("empty_job_observed = await_empty_job(job.value, &watch);",
                                       "result = 0; empty_job_observed = await_empty_job(job.value, &watch);"))

    def test_success_path_cannot_substitute_explicit_whole_job_retirement(self):
        with self.assertRaises(ValueError):
            verify(self.source.replace("fault_injected = 1;", "fault_injected = 1; TerminateJobObject(job.value, 125);"))

    def test_native_helper_controls_cover_absent_same_reused_cross_type_and_errors(self):
        helper = self.source[self.source.index("static int known_handle_controls("):
                             self.source.index("static int fresh_account_name(")]
        self.assertEqual(6, helper.count("++*passed;"))
        for required in ("first.value, first.value, error) != KNOWN_HANDLE_LEAK",
                         "NULL, first.value, error) != KNOWN_HANDLE_ABSENT",
                         "first.value, second.value, error) != KNOWN_HANDLE_REUSED",
                         "first.value, GetCurrentProcess(), error) != KNOWN_HANDLE_REUSED",
                         "*error != ERROR_ACCESS_DENIED", "*error != ERROR_INVALID_HANDLE"):
            self.assertIn(required, helper)
        self.assertIn("!known_handle_controls(&helper_passed, &known_error)", self.source)

    def test_wrapper_demands_exact_known_value_audit_but_no_exhaustive_claim(self):
        wrapper = (SOURCE.parent / "check-hosted-job-inheritance-environment.ps1").read_text()
        verify_compare_import(wrapper)
        for required in ("'knownHandleAuditPassed'", "-not $record.knownHandleAuditPassed",
                         "$record.knownHandleChecked -ne 3", "$record.knownHandleLeaked -ne 0",
                         "$record.knownHandleError -ne 0", "$record.knownHandleHelperControlsPassed -ne 6",
                         "$record.knownHandleAbsent + $record.knownHandleReused -ne 3",
                         "THREE_BROKER_VALUES_ONLY_NOT_EXHAUSTIVE"):
            self.assertIn(required, wrapper)
        self.assertIn("THREE_BROKER_VALUES_ONLY_NOT_EXHAUSTIVE", self.source)

    def test_supplied_sdk_compare_import_cannot_be_omitted_or_replaced(self):
        wrapper = (SOURCE.parent / "check-hosted-job-inheritance-environment.ps1").read_text()
        for replacement in ("", "kernelbase.lib", "Kernelbase.lib", "OneCore.lib OneCore.lib"):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                verify_compare_import(wrapper.replace("OneCore.lib", replacement))
        with self.assertRaises(ValueError):
            verify_compare_import(wrapper + "\nkernelbase.lib")


if __name__ == "__main__":
    unittest.main()
