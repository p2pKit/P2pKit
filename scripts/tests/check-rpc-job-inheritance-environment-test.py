#!/usr/bin/env python3
"""Narrow no-fallback recipe tripwires, NOT actual Windows job-inheritance qualification."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/windows/profile_job_inheritance_environment_probe.c"
DEATH_SOURCE = SOURCE.parent / "profile_controller_death_observer.h"
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


def verify_death(source, helper):
    """Source-shape tripwires for the reviewed recipe, not a C proof or Windows execution."""
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    helper = re.sub(r"/\*.*?\*/|//[^\n]*", "", helper, flags=re.DOTALL)
    broker = source[source.index("static int inheritance_broker("):source.index("static int inheritance_controller(")]
    controller = source[source.index("static int inheritance_controller("):source.index("static HANDLE parse_handle(")]
    watch = helper[helper.index("static int inheritance_watchdog("):helper.index("static int write_death_note(")]
    account_ack = helper[helper.index("static int death_account_ack("):
                         helper.index("static __declspec(noreturn) void death_abort_current(")]
    abort = helper[helper.index("static __declspec(noreturn) void death_abort_current("):
                   helper.index("static __declspec(noreturn) void death_broker_published_wait(")]
    broker_wait = helper[helper.index("static __declspec(noreturn) void death_broker_published_wait("):
                         helper.index("static void death_ready_wait(")]
    ready_wait = helper[helper.index("static void death_ready_wait("):helper.index("static int read_death_note(")]
    note_reader = helper[helper.index("static int read_death_note("):helper.index("static int death_live_process(")]
    exit_reader = helper[helper.index("static int death_exit_process("):helper.index("static int death_disable_account(")]
    disable = helper[helper.index("static int death_disable_account("):helper.index("static int death_owner_main(")]
    owner = helper[helper.index("static int death_owner_main("):helper.index("static int death_observer(")]
    observer = helper[helper.index("static int death_observer("):]
    success, cleanup = observer.split("done:", 1)

    for forbidden in ("OpenProcess(", "OpenJobObject", "AssignProcessToJobObject", "CreateProcessAsUser",
                      "CreateProcessWithToken", "CreateProcessWithLogon", "AdjustTokenPrivileges",
                      "LsaAddAccountRights", "BREAKAWAY", "LoadLibrary", "LOGON_WITH_PROFILE"):
        if forbidden in helper:
            raise ValueError("Observer cannot add another admission/payload path: " + forbidden)
    if helper.count("CreateProcessW(") != 1 or helper.count("DuplicateHandle(") != 2:
        raise ValueError("One atomic owner launch and exactly two process-only parent pulls")
    if "OpenProcess(" in controller or re.search(r"DuplicateHandle\([^;]*\bjob\.value", controller):
        raise ValueError("Controller cannot reacquire a PID or duplicate its private last-owner job")
    if "#include \"profile_controller_death_observer.h\"" not in source or \
            "return death_observer();" not in source:
        raise ValueError("The reviewed death observer must be connected to the maintained fixture")
    require_ordered(watch, (
        "if (!link) return start_watchdog(watch)", "link->deadline < PROBE_MS || link->deadline <= now",
        "link->deadline - now > PROBE_MS", "watch->start = link->deadline - PROBE_MS",
        "CreateThread(NULL, 0, watchdog_thread, watch, 0, NULL)", "(void)remaining(watch)",
    ), "Owner must inherit the original absolute deadline before watchdog startup")
    if watch.count("start_watchdog(") != 1 or re.search(r"watch->start\s*=\s*(?:GetTickCount64|now)", watch):
        raise ValueError("Death-owner budget cannot restart")
    require_ordered(owner, (
        "report_candidate == gate_candidate", "owned_handle report = {report_candidate, 0}, gate = {gate_candidate, 0}",
        "deadline > (UINT64_MAX - (unsigned)(*p - L'0')) / 10",
        "controller_death_link link = {report.value, gate.value, deadline}",
        "inheritance_controller(INHERIT_CONTROLLER_DEATH, &link)",
        "if (!close_once(&gate)) result = 8", "if (!close_once(&report)) result = 8",
    ), "Inherited owner arguments and handles need bounded parsing and independent close")
    require_ordered(controller, (
        "!inheritance_watchdog(&watch, link)",
        "account_created = 1; memcpy(account, note.account, sizeof(account))",
        "if (link && !death_account_ack(link, account, &watch, &error)) goto done",
        "error = NetUserSetInfo(NULL, account, 1008, (LPBYTE)&enabled, &parameter)",
        "if (error != NERR_Success) goto done", "SetEvent(gate.value)",
        "known_handles_passed = 1", "accounting.ActiveProcesses != 2", "exact_two_before_close = 1",
        "if (mode == INHERIT_CONTROLLER_DEATH)",
        "death_ready_wait(link, process.value, child_process.value, known_absent, known_reused, &watch, &error)",
        "goto done", "if (!close_once(&job)) goto done",
    ), "Death gate follows exact account custody and existing child audits")
    death_branch = controller[controller.index("if (mode == INHERIT_CONTROLLER_DEATH)"):
                              controller.index("if (!close_once(&job)) goto done")]
    if any(word in death_branch for word in ("SetEvent(", "ResumeThread(", "result = 0", "close_once(", "DuplicateHandle(")):
        raise ValueError("Controller-death branch cannot release the gate or close/transfer its private job")
    require_ordered(account_ack, (
        "note.kind = DEATH_ACCOUNT", "memcpy(note.account, account, sizeof(note.account))",
        "write_death_note(link->report, &note, error)", "if (!written) return 0",
        "WaitForSingleObject(link->gate, remaining(watch))", "if (waited != WAIT_OBJECT_0)",
        "(void)remaining(watch)", "return 1",
    ), "Account delegation must wait for the independent observer's acknowledgment")
    require_ordered(ready_wait, (
        "note.kind = DEATH_READY; note.exact_members = 2", "note.broker = (uintptr_t)broker",
        "note.child_process = (uintptr_t)child_process", "write_death_note(link->report, &note, error)",
        "WaitForSingleObject(link->gate, remaining(watch))",
        "death_abort_current(CONTROLLER_READY_ABORT_EXIT)",
    ), "Ready is a fixed audited gate, not permission to continue")
    if any(word in ready_wait for word in ("SetEvent(", "ResumeThread(", "return 0", "ERROR_SUCCESS")):
        raise ValueError("No successful second ready acknowledgment exists")
    published = ready_wait[ready_wait.index("if (!write_death_note(link->report, &note, error)) return;") +
                           len("if (!write_death_note(link->report, &note, error)) return;"):]
    if any(word in published for word in ("return", "goto", "close_once(", "TerminateProcess(")):
        raise ValueError("After DEATH_READY publication the controller cannot return to explicit descendant cleanup")
    require_ordered(broker, (
        "note.kind = NOTE_CHILD; note.handle = (uintptr_t)process.value",
        "if (!write_note(pipe, &note)) goto done",
        "if (mode == INHERIT_CONTROLLER_DEATH) death_broker_published_wait(gate, &watch)",
        "if (WaitForSingleObject(gate, remaining(&watch)) != WAIT_OBJECT_0) goto done",
    ), "Published mode2 broker must not reach ordinary gate-failure descendant cleanup")
    require_ordered(broker_wait, (
        "(void)WaitForSingleObject(gate, remaining(watch))", "death_abort_current(BROKER_GATE_ABORT_EXIT)",
    ), "Broker gate failures must terminate only the broker with an explicitly rejected code")
    # The declaration contains 'noreturn'; inspect only the function body for return statements.
    body = broker_wait[broker_wait.index("{") + 1:]
    if any(word in body for word in ("return", "goto", "close_once(", "TerminateProcess(")):
        raise ValueError("Published broker cannot fall through to ordinary explicit child cleanup")
    require_ordered(abort, (
        "(void)TerminateProcess(GetCurrentProcess(), exit_code)", "__fastfail(FAST_FAIL_FATAL_APP_EXIT)",
    ), "Published terminal fallback must terminate self only and never return")
    if "return" in abort[abort.index("{") + 1:] or abort.count("TerminateProcess(") != 1:
        raise ValueError("Terminal self-abort cannot return to explicit descendant cleanup")
    for constant in ("#define CONTROLLER_READY_ABORT_EXIT 127u", "#define BROKER_GATE_ABORT_EXIT 124u"):
        if constant not in helper:
            raise ValueError("Keep gate-abort exits distinct from injected controller death")
    if helper.count("SetEvent(") != 1 or observer.count("SetEvent(") != 1 or "SetEvent(" in cleanup:
        raise ValueError("Observer may send exactly one account acknowledgment, never a second gate release")
    for required in (
        "if (!PeekNamedPipe(pipe, NULL, 0, NULL, &available, NULL)) { *error = GetLastError(); return 0; }",
        "WaitForSingleObject(controller, budget < 10 ? budget : 10)",
        "*error = available ? ERROR_INVALID_DATA : ERROR_BROKEN_PIPE; return 0",
        "if (!ReadFile(pipe, note, sizeof(*note), &read, NULL)) { *error = GetLastError(); return 0; }",
        "read != sizeof(*note) || note->magic != DEATH_NOTE_MAGIC",
        "(note->kind != DEATH_ACCOUNT && note->kind != DEATH_READY)",
    ):
        if required not in note_reader:
            raise ValueError("Death-note reader must retain bounded exact-controller/error observations")
    require_ordered(success, (
        "if (!kill_job(&containment))", "gate.value = CreateEventW(&security, FALSE, FALSE, NULL)",
        "(unsigned long long)(watch.start + PROBE_MS)",
        "HANDLE jobs[] = {containment.value}, handles[] = {pipe_write.value, gate.value}",
        "PROC_THREAD_ATTRIBUTE_JOB_LIST", "PROC_THREAD_ATTRIBUTE_HANDLE_LIST", "CreateProcessW(",
        "CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW",
        "controller.value = pi.hProcess; controller_thread.value = pi.hThread", "verified_member(controller.value, containment.value)",
        "atomic_admission = 1", "ResumeThread(controller_thread.value)",
        "note.kind != DEATH_ACCOUNT || !fresh_account_name(note.account) || note.exact_members",
        "memcpy(account, note.account, sizeof(account)); account_acknowledged = 1", "SetEvent(gate.value)",
        "note.kind != DEATH_READY || note.exact_members != 2", "note.known_absent + note.known_reused != 3",
        "memcmp(note.account, empty_account, sizeof(empty_account))", "note.broker == note.child_process",
    ), "Outer containment/account/gate admission must precede resource transfer")
    for value, destination in (("broker", "broker"), ("child_process", "child_process")):
        pull = (f"DuplicateHandle(controller.value, (HANDLE)note.{value}, GetCurrentProcess(), &{destination}.value,\n"
                "        PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, FALSE, 0)")
        if success.count(pull) != 1:
            raise ValueError("Pull only a noninheritable query/synchronize handle from the exact controller")
    require_ordered(success, (
        "note.broker == note.child_process", "DuplicateHandle(controller.value, (HANDLE)note.broker",
        "DuplicateHandle(controller.value, (HANDLE)note.child_process", "death_live_process(controller.value, &error)",
        "death_live_process(broker.value, &error)", "death_live_process(child_process.value, &error)",
        "controller_id == broker_id || controller_id == child_id", "broker_id == child_id",
        "verified_member(broker.value, containment.value)", "verified_member(child_process.value, containment.value)",
        "audit_ready = 1", "TerminateProcess(controller.value, CONTROLLER_FAULT_EXIT)", "injected = 1",
        "if (!death_exit_process(controller.value, &watch, &controller_exit, &error)) goto done",
        "controller_exit_observed = 1", "if (controller_exit != CONTROLLER_FAULT_EXIT)",
        "if (!death_exit_process(broker.value, &watch, &broker_exit, &error)) goto done", "broker_exit_observed = 1",
        "if (broker_exit == BROKER_GATE_ABORT_EXIT || broker_exit == 125u || broker_exit == 0xc0000409u)",
        "error = ERROR_INVALID_DATA; goto done",
        "if (!death_exit_process(child_process.value, &watch, &child_exit, &error)) goto done", "child_exit_observed = 1",
        "if (child_exit == CHILD_EXIT)", "outer_open_during_observation = 1; stage = 5; result = 0",
    ), "Pass requires exact controller death then both original descendants, while outer job stays open")
    if success.count("TerminateProcess(") != 1 or "TerminateJobObject(" in success or \
            "close_once(&containment)" in success or "CloseHandle(containment.value)" in success:
        raise ValueError("Outer containment and explicit descendant termination cannot establish success")
    if any(term in success for term in ("TerminateProcess(broker", "TerminateProcess(child_process")):
        raise ValueError("Observer must see automatic descendant exit")
    require_ordered(exit_reader, (
        "WaitForSingleObject(process, remaining(watch))", "if (waited != WAIT_OBJECT_0)",
        "GetExitCodeProcess(process, exit_code)", "if (*exit_code == STILL_ACTIVE)", "return 1",
    ), "Missing exact process exit cannot be replaced by a receipt or timeout")
    require_ordered(cleanup, (
        "if (result != 0 && containment.value)", "explicit_failure_termination = 1",
        "if (!TerminateJobObject(containment.value, 125))", "death_exit_process(controller.value, &watch, &ignored, &wait_error)",
        "death_exit_process(broker.value, &watch, &ignored, &wait_error)",
        "death_exit_process(child_process.value, &watch, &ignored, &wait_error)",
        "if (!close_once(&child_process)) cleanup = 0", "if (!close_once(&broker)) cleanup = 0",
        "if (!close_once(&controller_thread)) cleanup = 0", "if (!close_once(&controller)) cleanup = 0",
        "containment_empty = await_empty_job(containment.value, &watch)", "if (!containment_empty) cleanup = 0",
        "if (account_acknowledged)", "account_disabled = death_disable_account(account, &account_error)",
        "if (!account_disabled)", "if (!close_once(&containment)) cleanup = 0",
        "if (!finish_watchdog(&watch)) cleanup = 0", "if (!cleanup) result = 8",
    ), "Failure containment and every original resource retirement remain fail-closed")
    if re.search(r"\bresult\s*=\s*0\b", cleanup) or helper.count("TerminateJobObject(") != 1:
        raise ValueError("Failure containment must never produce PASS")
    require_ordered(disable, (
        "UF_ACCOUNTDISABLE", "NetUserSetInfo(NULL, account, 1008, (LPBYTE)&disabled, &parameter)",
        "if (status != NERR_Success)", "NetUserGetInfo(NULL, account, 1, &bytes)",
        "info->usri1_flags & UF_ACCOUNTDISABLE", "info->usri1_priv == USER_PRIV_USER",
        "wcscmp(info->usri1_name, account) == 0",
        "if (bytes && NetApiBufferFree(bytes) != NERR_Success) { *error = ERROR_INVALID_DATA; okay = 0; }",
        "return okay",
    ), "Acknowledged account disable must be read back without adopting another account")
    for required in (
        "CONTROLLER_DEATH_POST_RETURN_GATE_NOT_INFLIGHT_OR_PROTECTED_SUPERVISION",
        '\\"privateJobDuplicated\\":false', '\\"profileRequested\\":false', '\\"nativeStorageExecuted\\":false',
        '\\"inFlightCreationQualified\\":false', '\\"protectedSupervisorQualified\\":false',
    ):
        if required not in helper:
            raise ValueError("Preserve the explicit post-return-only qualification scope")


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
                         "not profile, JNI, or protected-supervisor qualification", "Controller death"):
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


class ControllerDeathRecipeTests(unittest.TestCase):
    """Deterministic recipe/mutation controls; these never execute Windows/native payloads."""

    def setUp(self):
        self.source = SOURCE.read_text()
        self.helper = DEATH_SOURCE.read_text()

    def reject_mutations(self, target, mutations):
        original = self.source if target == "source" else self.helper
        for before, after in mutations:
            with self.subTest(before=before, after=after):
                self.assertIn(before, original)
                changed = original.replace(before, after, 1)
                self.assertNotEqual(original, changed)
                with self.assertRaises(ValueError):
                    verify_death(changed if target == "source" else self.source,
                                 changed if target == "helper" else self.helper)

    def test_maintained_source_and_helper(self):
        verify_death(self.source, self.helper)

    def test_owner_deadline_is_original_absolute_budget_not_new_full_budget(self):
        self.reject_mutations("helper", (
            ("watch->start = link->deadline - PROBE_MS", "watch->start = GetTickCount64()"),
            ("link->deadline <= now", "0"),
            ("link->deadline - now > PROBE_MS", "0"),
            ("(unsigned long long)(watch.start + PROBE_MS)", "(unsigned long long)(GetTickCount64() + PROBE_MS)"),
        ))
        self.reject_mutations("source", (("!inheritance_watchdog(&watch, link)", "!start_watchdog(&watch)"),))

    def test_deadline_is_set_before_starting_watchdog_thread(self):
        before = "watch->start = link->deadline - PROBE_MS;"
        after = "watch->thread.value = CreateThread(NULL, 0, watchdog_thread, watch, 0, NULL);"
        changed = self.helper.replace(before, "", 1).replace(after, after + "\n" + before, 1)
        with self.assertRaises(ValueError):
            verify_death(self.source, changed)

    def test_owner_rejects_handle_alias_and_overflow_and_closes_both_owners(self):
        self.reject_mutations("helper", tuple((token, "REMOVED") for token in (
            "report_candidate == gate_candidate", "deadline > (UINT64_MAX - (unsigned)(*p - L'0')) / 10",
            "if (!close_once(&gate)) result = 8", "if (!close_once(&report)) result = 8",
        )))

    def test_acknowledged_account_custody_precedes_enable(self):
        ack = "if (link && !death_account_ack(link, account, &watch, &error)) goto done;"
        self.reject_mutations("source", ((ack, ""),))
        enable = "error = NetUserSetInfo(NULL, account, 1008, (LPBYTE)&enabled, &parameter);"
        changed = self.source.replace(ack, "", 1).replace(enable, enable + "\n" + ack, 1)
        with self.assertRaises(ValueError):
            verify_death(changed, self.helper)

    def test_observer_records_exact_account_before_acknowledging(self):
        ownership = "memcpy(account, note.account, sizeof(account)); account_acknowledged = 1;"
        signal = "if (!SetEvent(gate.value)) { error = GetLastError(); goto done; }"
        changed = self.helper.replace(ownership, "", 1).replace(signal, signal + "\n" + ownership, 1)
        with self.assertRaises(ValueError):
            verify_death(self.source, changed)
        self.reject_mutations("helper", (("!fresh_account_name(note.account)", "0"),))

    def test_account_ack_cannot_skip_its_wait_or_accept_failed_wait(self):
        self.reject_mutations("helper", (
            ("if (!written) return 0", "if (!written) return 1"),
            ("WaitForSingleObject(link->gate, remaining(watch))", "WAIT_OBJECT_0"),
            ("if (waited != WAIT_OBJECT_0)", "if (0)"),
        ))

    def test_exact_gate_and_handle_audit_cannot_be_skipped_before_death_ready(self):
        self.reject_mutations("source", tuple((token, "REMOVED") for token in (
            "known_handles_passed = 1", "accounting.ActiveProcesses != 2", "exact_two_before_close = 1",
            "death_ready_wait(link, process.value, child_process.value, known_absent, known_reused, &watch, &error)",
        )))
        self.reject_mutations("helper", (
            ("note.exact_members != 2", "note.exact_members < 2"),
            ("note.known_absent + note.known_reused != 3", "0"),
        ))

    def test_second_gate_signal_cannot_release_suspended_fault_child(self):
        self.reject_mutations("helper", (
            ("audit_ready = 1;", "SetEvent(gate.value); audit_ready = 1;"),
            ("DWORD waited = WaitForSingleObject(link->gate, remaining(watch));",
             "SetEvent(link->gate); DWORD waited = WaitForSingleObject(link->gate, remaining(watch));"),
        ))
        self.reject_mutations("source", (
            ("if (mode == INHERIT_CONTROLLER_DEATH) {", "if (mode == INHERIT_CONTROLLER_DEATH) { SetEvent(gate.value);"),
        ))

    def test_ready_wait_cannot_treat_any_observer_signal_as_success(self):
        self.reject_mutations("helper", (
            ("death_abort_current(CONTROLLER_READY_ABORT_EXIT);", "return;"),
            ("death_abort_current(CONTROLLER_READY_ABORT_EXIT);", "return; death_abort_current(CONTROLLER_READY_ABORT_EXIT);"),
        ))

    def test_published_broker_cannot_reenter_explicit_descendant_cleanup(self):
        fence = "if (mode == INHERIT_CONTROLLER_DEATH) death_broker_published_wait(gate, &watch);"
        self.reject_mutations("source", ((fence, ""), (fence, fence.replace("==", "!="))))
        self.reject_mutations("helper", (
            ("death_abort_current(BROKER_GATE_ABORT_EXIT);", "return;"),
            ("death_abort_current(BROKER_GATE_ABORT_EXIT);", "return; death_abort_current(BROKER_GATE_ABORT_EXIT);"),
        ))

    def test_postpublication_abort_is_self_only_terminal_and_rejected(self):
        self.reject_mutations("helper", (
            ("TerminateProcess(GetCurrentProcess(), exit_code)", "TerminateProcess(child_process, exit_code)"),
            ("__fastfail(FAST_FAIL_FATAL_APP_EXIT)", "return"),
            ("#define CONTROLLER_READY_ABORT_EXIT 127u", "#define CONTROLLER_READY_ABORT_EXIT 126u"),
            ("#define BROKER_GATE_ABORT_EXIT 124u", "#define BROKER_GATE_ABORT_EXIT 0u"),
            ("broker_exit == BROKER_GATE_ABORT_EXIT || broker_exit == 125u || broker_exit == 0xc0000409u", "0"),
            ("broker_exit == 125u", "0"),
            ("broker_exit == 0xc0000409u", "0"),
        ))

    def test_outer_job_is_atomically_admitted_and_never_inherited(self):
        self.reject_mutations("helper", (
            ("PROC_THREAD_ATTRIBUTE_JOB_LIST", "REMOVED"),
            ("PROC_THREAD_ATTRIBUTE_HANDLE_LIST", "REMOVED"),
            ("handles[] = {pipe_write.value, gate.value}", "handles[] = {containment.value, pipe_write.value, gate.value}"),
            ("verified_member(controller.value, containment.value)", "1"),
        ))

    def test_parent_pulls_only_exact_original_noninheritable_process_handles(self):
        self.reject_mutations("helper", (
            ("DuplicateHandle(controller.value, (HANDLE)note.broker", "DuplicateHandle(GetCurrentProcess(), (HANDLE)note.broker"),
            ("&broker.value,\n        PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, FALSE, 0)",
             "&broker.value,\n        PROCESS_ALL_ACCESS, TRUE, 0)"),
            ("(HANDLE)note.child_process", "(HANDLE)note.broker"),
            ("if (!DuplicateHandle(controller.value, (HANDLE)note.broker",
             "if (!DuplicateHandle(controller.value, (HANDLE)note.private_job"),
        ))

    def test_private_job_duplication_and_pid_reacquisition_are_forbidden(self):
        for added in ("DuplicateHandle(controller.value, job, GetCurrentProcess(), &copy, 0, FALSE, 0);",
                      "OpenProcess(SYNCHRONIZE, FALSE, child_id);", "OpenJobObjectW(0, FALSE, name);"):
            with self.subTest(added=added), self.assertRaises(ValueError):
                verify_death(self.source, self.helper + "\n" + added)
        self.reject_mutations("source", (
            ("if (!kill_job(&job))", "DuplicateHandle(GetCurrentProcess(), job.value, target, &copy, 0, FALSE, 0); if (!kill_job(&job))"),
            ("if (!kill_job(&job))", "OpenProcess(SYNCHRONIZE, FALSE, child_id); if (!kill_job(&job))"),
        ))

    def test_all_three_exact_live_processes_and_distinct_identities_are_required(self):
        self.reject_mutations("helper", tuple((token, "REMOVED") for token in (
            "death_live_process(controller.value, &error)", "death_live_process(broker.value, &error)",
            "death_live_process(child_process.value, &error)", "controller_id == broker_id || controller_id == child_id",
            "broker_id == child_id", "verified_member(broker.value, containment.value)",
            "verified_member(child_process.value, containment.value)",
        )))

    def test_every_original_exit_is_required_before_success(self):
        self.reject_mutations("helper", tuple((token, "REMOVED") for token in (
            "if (!death_exit_process(controller.value, &watch, &controller_exit, &error)) goto done",
            "if (!death_exit_process(broker.value, &watch, &broker_exit, &error)) goto done",
            "if (!death_exit_process(child_process.value, &watch, &child_exit, &error)) goto done",
            "controller_exit_observed = 1", "broker_exit_observed = 1", "child_exit_observed = 1",
            "if (controller_exit != CONTROLLER_FAULT_EXIT)", "if (child_exit == CHILD_EXIT)",
        )))

    def test_exit_helper_rejects_wait_failure_and_still_active(self):
        start = self.helper.index("static int death_exit_process(")
        prefix, suffix = self.helper[:start], self.helper[start:]
        for token in ("if (waited != WAIT_OBJECT_0)", "if (*exit_code == STILL_ACTIVE)"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                verify_death(self.source, prefix + suffix.replace(token, "if (0)", 1))

    def test_outer_close_and_explicit_descendant_termination_cannot_make_pass(self):
        marker = "audit_ready = 1;"
        self.reject_mutations("helper", tuple((marker, action + marker) for action in (
            "close_once(&containment); ", "CloseHandle(containment.value); ",
            "TerminateJobObject(containment.value, 125); ", "TerminateProcess(broker.value, 125); ",
            "TerminateProcess(child_process.value, 125); ",
        )))

    def test_explicit_failure_containment_cannot_be_unconditional_or_reset_failure(self):
        self.reject_mutations("helper", (
            ("if (result != 0 && containment.value)", "if (containment.value)"),
            ("explicit_failure_termination = 1;", "explicit_failure_termination = 1; result = 0;"),
            ("if (!cleanup) result = 8", "if (!cleanup) result = 0"),
        ))

    def test_reference_retirement_precedes_zero_job_observation_and_final_close(self):
        self.reject_mutations("helper", tuple((token, "REMOVED") for token in (
            "if (!close_once(&child_process)) cleanup = 0", "if (!close_once(&broker)) cleanup = 0",
            "if (!close_once(&controller_thread)) cleanup = 0", "if (!close_once(&controller)) cleanup = 0",
            "containment_empty = await_empty_job(containment.value, &watch)", "if (!containment_empty) cleanup = 0",
            "if (!close_once(&containment)) cleanup = 0", "if (!finish_watchdog(&watch)) cleanup = 0",
        )))

    def test_owned_account_disable_is_read_back_and_free_failure_remains_fatal(self):
        self.reject_mutations("helper", tuple((token, "REMOVED") for token in (
            "if (account_acknowledged)", "account_disabled = death_disable_account(account, &account_error)",
            "NetUserGetInfo(NULL, account, 1, &bytes)", "info->usri1_flags & UF_ACCOUNTDISABLE",
            "info->usri1_priv == USER_PRIV_USER", "wcscmp(info->usri1_name, account) == 0", "NetApiBufferFree(bytes)",
        )))
        self.reject_mutations("helper", (
            ("if (bytes && NetApiBufferFree(bytes) != NERR_Success) { *error = ERROR_INVALID_DATA; okay = 0; }",
             "if (bytes) NetApiBufferFree(bytes);"),
        ))

    def test_receipt_never_promotes_fixed_gate_into_inflight_profile_or_supervision(self):
        self.reject_mutations("helper", tuple((token, token.replace("false", "true")) for token in (
            '\\"privateJobDuplicated\\":false', '\\"profileRequested\\":false', '\\"nativeStorageExecuted\\":false',
            '\\"inFlightCreationQualified\\":false', '\\"protectedSupervisorQualified\\":false',
        )))


if __name__ == "__main__":
    unittest.main()
