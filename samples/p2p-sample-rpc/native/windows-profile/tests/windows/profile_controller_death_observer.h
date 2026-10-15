/* Fixed TEST-ONLY controller-death control. Included only by the GUI inheritance fixture.
 * This is not a process supervisor, alternate app launcher or protected-profile/JNI admission.
 * The outer containment job stays OPEN during the successful fault observation. It is a different
 * job from the controller's private job; that private job is never named, inherited or duplicated.
 * Every death injection occurs AFTER WithLogon has returned and the exact suspended child passed
 * the existing controller audits. Nothing here observes the Secondary Logon service's in-flight
 * handoff or qualifies a death during that handoff. No profile, storage or candidate DLL executes. */
#ifndef P2PKIT_CONTROLLER_DEATH_OBSERVER_H
#define P2PKIT_CONTROLLER_DEATH_OBSERVER_H

#define DEATH_NOTE_MAGIC 0x50444331u
#define CONTROLLER_FAULT_EXIT 126u
#define CONTROLLER_READY_ABORT_EXIT 127u
#define BROKER_GATE_ABORT_EXIT 124u
enum { DEATH_ACCOUNT = 1, DEATH_READY = 2 };
typedef struct {
    DWORD magic, kind, exact_members, known_absent, known_reused;
    uintptr_t broker, child_process;
    WCHAR account[20];
} death_note;

static int inheritance_watchdog(watchdog *watch, const controller_death_link *link) {
    if (!link) return start_watchdog(watch);
    ULONGLONG now = GetTickCount64();
    if (!link->report || !link->gate || link->deadline < PROBE_MS || link->deadline <= now ||
        link->deadline - now > PROBE_MS) return 0;
    memset(watch, 0, sizeof(*watch));
    /* Set before creating the watchdog thread: never extend/reset the outer experiment's budget. */
    watch->start = link->deadline - PROBE_MS;
    watch->event.value = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!watch->event.value) return 0;
    watch->thread.value = CreateThread(NULL, 0, watchdog_thread, watch, 0, NULL);
    if (!watch->thread.value) { (void)close_once(&watch->event); return 0; }
    (void)remaining(watch);
    return 1;
}
static int write_death_note(HANDLE pipe, death_note *note, DWORD *error) {
    DWORD written = 0; note->magic = DEATH_NOTE_MAGIC;
    if (!WriteFile(pipe, note, sizeof(*note), &written, NULL)) { *error = GetLastError(); return 0; }
    if (written != sizeof(*note)) { *error = ERROR_INVALID_DATA; return 0; }
    return 1;
}
static int death_account_ack(const controller_death_link *link, const WCHAR account[20],
    const watchdog *watch, DWORD *error) {
    death_note note = {0}; note.kind = DEATH_ACCOUNT;
    memcpy(note.account, account, sizeof(note.account));
    int written = write_death_note(link->report, &note, error);
    SecureZeroMemory(&note, sizeof(note));
    if (!written) return 0;
    DWORD waited = WaitForSingleObject(link->gate, remaining(watch));
    if (waited != WAIT_OBJECT_0) {
        *error = waited == WAIT_FAILED ? GetLastError() : ERROR_INVALID_DATA; return 0;
    }
    (void)remaining(watch);
    return 1;
}
static __declspec(noreturn) void death_abort_current(UINT exit_code) {
    (void)TerminateProcess(GetCurrentProcess(), exit_code);
    __fastfail(FAST_FAIL_FATAL_APP_EXIT);
}
static __declspec(noreturn) void death_broker_published_wait(HANDLE gate, const watchdog *watch) {
    (void)WaitForSingleObject(gate, remaining(watch));
    /* Even an unexpected valid signal is fatal in mode2. Never execute ordinary descendant cleanup
     * after NOTE_CHILD publication: the observer rejects this distinct broker-failure exit. */
    death_abort_current(BROKER_GATE_ABORT_EXIT);
}
static void death_ready_wait(const controller_death_link *link, HANDLE broker, HANDLE child_process,
    DWORD absent, DWORD reused, const watchdog *watch, DWORD *error) {
    if (!link) { *error = ERROR_INVALID_PARAMETER; return; }
    death_note note = {0}; note.kind = DEATH_READY; note.exact_members = 2;
    note.known_absent = absent; note.known_reused = reused;
    note.broker = (uintptr_t)broker; note.child_process = (uintptr_t)child_process;
    /* Values remain in this controller's handle table. Never inject handles into the observer. */
    if (!write_death_note(link->report, &note, error)) return;
    SecureZeroMemory(&note, sizeof(note));
    (void)WaitForSingleObject(link->gate, remaining(watch));
    /* After publication, never return into controller cleanup: explicit descendant termination
     * there could race the observer's death injection and produce a false automatic-retirement pass.
     * A gate failure kills ONLY this controller, under a distinct nonpassing exit code. */
    death_abort_current(CONTROLLER_READY_ABORT_EXIT);
}
static int read_death_note(HANDLE pipe, HANDLE controller, const watchdog *watch,
    death_note *note, DWORD *error) {
    memset(note, 0, sizeof(*note)); *error = ERROR_SUCCESS;
    for (;;) {
        DWORD available = 0; (void)remaining(watch);
        if (!PeekNamedPipe(pipe, NULL, 0, NULL, &available, NULL)) { *error = GetLastError(); return 0; }
        if (available >= sizeof(*note)) break;
        DWORD budget = remaining(watch);
        DWORD waited = WaitForSingleObject(controller, budget < 10 ? budget : 10);
        if (waited == WAIT_OBJECT_0) {
            if (!PeekNamedPipe(pipe, NULL, 0, NULL, &available, NULL)) { *error = GetLastError(); return 0; }
            if (available < sizeof(*note)) {
                *error = available ? ERROR_INVALID_DATA : ERROR_BROKEN_PIPE; return 0;
            }
            break;
        }
        if (waited != WAIT_TIMEOUT) {
            *error = waited == WAIT_FAILED ? GetLastError() : ERROR_INVALID_DATA; return 0;
        }
    }
    DWORD read = 0;
    if (!ReadFile(pipe, note, sizeof(*note), &read, NULL)) { *error = GetLastError(); return 0; }
    (void)remaining(watch);
    if (read != sizeof(*note) || note->magic != DEATH_NOTE_MAGIC ||
        (note->kind != DEATH_ACCOUNT && note->kind != DEATH_READY)) {
        *error = ERROR_INVALID_DATA; return 0;
    }
    return 1;
}
static int death_live_process(HANDLE process, DWORD *error) {
    DWORD waited = WaitForSingleObject(process, 0);
    if (waited != WAIT_TIMEOUT) {
        *error = waited == WAIT_FAILED ? GetLastError() : ERROR_INVALID_DATA; return 0;
    }
    DWORD id = GetProcessId(process);
    if (!id || id == GetCurrentProcessId()) { *error = ERROR_INVALID_DATA; return 0; }
    return 1;
}
static int death_exit_process(HANDLE process, const watchdog *watch, DWORD *exit_code, DWORD *error) {
    DWORD waited = WaitForSingleObject(process, remaining(watch));
    if (waited != WAIT_OBJECT_0) {
        *error = waited == WAIT_FAILED ? GetLastError() : ERROR_INVALID_DATA; return 0;
    }
    (void)remaining(watch);
    if (!GetExitCodeProcess(process, exit_code)) { *error = GetLastError(); return 0; }
    if (*exit_code == STILL_ACTIVE) { *error = ERROR_INVALID_DATA; return 0; }
    return 1;
}
static int death_disable_account(const WCHAR account[20], DWORD *error) {
    DWORD parameter = 0; USER_INFO_1008 disabled = {UF_SCRIPT | UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE};
    NET_API_STATUS status = NetUserSetInfo(NULL, account, 1008, (LPBYTE)&disabled, &parameter);
    if (status != NERR_Success) { *error = status; return 0; }
    LPBYTE bytes = NULL;
    status = NetUserGetInfo(NULL, account, 1, &bytes);
    int okay = status == NERR_Success && bytes != NULL;
    if (okay) {
        const USER_INFO_1 *info = (const USER_INFO_1 *)bytes;
        okay = (info->usri1_flags & UF_ACCOUNTDISABLE) != 0 && info->usri1_priv == USER_PRIV_USER &&
            info->usri1_name && wcscmp(info->usri1_name, account) == 0;
    }
    if (!okay) *error = status == NERR_Success ? ERROR_INVALID_DATA : status;
    if (bytes && NetApiBufferFree(bytes) != NERR_Success) { *error = ERROR_INVALID_DATA; okay = 0; }
    return okay;
}
static int death_owner_main(const WCHAR *pipe_text, const WCHAR *gate_text, const WCHAR *deadline_text) {
    HANDLE report_candidate = parse_handle(pipe_text), gate_candidate = parse_handle(gate_text);
    /* Refuse aliases before adopting either owner, so malformed arguments cannot double-close. */
    if (!report_candidate || !gate_candidate || report_candidate == gate_candidate) return 2;
    owned_handle report = {report_candidate, 0}, gate = {gate_candidate, 0};
    ULONGLONG deadline = 0; int result = 2;
    if (!deadline_text || !*deadline_text) goto done;
    for (const WCHAR *p = deadline_text; *p; ++p) {
        if (*p < L'0' || *p > L'9' || deadline > (UINT64_MAX - (unsigned)(*p - L'0')) / 10) goto done;
        deadline = deadline * 10 + (unsigned)(*p - L'0');
    }
    controller_death_link link = {report.value, gate.value, deadline};
    result = inheritance_controller(INHERIT_CONTROLLER_DEATH, &link);
done:
    if (!close_once(&gate)) result = 8;
    if (!close_once(&report)) result = 8;
    return result;
}
static int death_observer(void) {
    watchdog watch; if (!elevated_controller() || !start_watchdog(&watch)) return 3;
    /* Only this separate containment job covers observer failure. Keep it live/open while testing
     * whether terminating the controller releases its DIFFERENT private job and its gated children. */
    owned_handle containment = {0}, pipe_read = {0}, pipe_write = {0}, gate = {0};
    owned_handle controller = {0}, controller_thread = {0}, broker = {0}, child_process = {0};
    LPPROC_THREAD_ATTRIBUTE_LIST attributes = NULL; SIZE_T attribute_size = 0;
    int initialized = 0, result = 5, cleanup = 1, account_acknowledged = 0, account_disabled = 0;
    int controller_created = 0, atomic_admission = 0, audit_ready = 0, injected = 0;
    int controller_exit_observed = 0, broker_exit_observed = 0, child_exit_observed = 0;
    int broker_pulled = 0, child_pulled = 0, outer_open_during_observation = 0, containment_empty = 0;
    int explicit_failure_termination = 0;
    DWORD stage = 1, error = 0, controller_exit = STILL_ACTIVE, broker_exit = STILL_ACTIVE, child_exit = STILL_ACTIVE;
    DWORD known_absent = 0, known_reused = 0;
    WCHAR executable[32768] = {0}, command[2048] = {0}, system[32768] = {0}, environment[65560] = {0};
    WCHAR account[20] = {0}; death_note note = {0};
    if (!kill_job(&containment)) { error = GetLastError(); goto done; }
    SECURITY_ATTRIBUTES security = {sizeof(security), NULL, TRUE};
    if (!CreatePipe(&pipe_read.value, &pipe_write.value, &security, sizeof(death_note) * 3) ||
        !SetHandleInformation(pipe_read.value, HANDLE_FLAG_INHERIT, 0)) { error = GetLastError(); goto done; }
    gate.value = CreateEventW(&security, FALSE, FALSE, NULL);
    if (!gate.value) { error = GetLastError(); goto done; }
    DWORD length = GetModuleFileNameW(NULL, executable, 32768);
    UINT system_length = GetSystemWindowsDirectoryW(system, 32768);
    if (!length || length > 900 || wcschr(executable, L'"') || !system_length || system_length >= 32768 ||
        swprintf_s(command, 2048, L"\"%ls\" --inheritance-controller-death-owner %llu %llu %llu", executable,
            (unsigned long long)(uintptr_t)pipe_write.value, (unsigned long long)(uintptr_t)gate.value,
            (unsigned long long)(watch.start + PROBE_MS)) <= 0) { error = ERROR_INVALID_DATA; goto done; }
    int count = swprintf_s(environment, 65560, L"SystemRoot=%ls", system);
    if (count <= 0) { error = ERROR_INVALID_DATA; goto done; }
    int second = swprintf_s(environment + count + 1, 65560 - (size_t)count - 1, L"WINDIR=%ls", system);
    if (second <= 0) { error = ERROR_INVALID_DATA; goto done; }
    environment[(size_t)count + 1 + (size_t)second + 1] = 0;
    (void)InitializeProcThreadAttributeList(NULL, 2, 0, &attribute_size);
    if (!attribute_size || attribute_size > 1024 * 1024) { error = ERROR_INVALID_DATA; goto done; }
    attributes = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, attribute_size);
    if (!attributes) { error = ERROR_NOT_ENOUGH_MEMORY; goto done; }
    if (!InitializeProcThreadAttributeList(attributes, 2, 0, &attribute_size)) { error = GetLastError(); goto done; }
    initialized = 1;
    HANDLE jobs[] = {containment.value}, handles[] = {pipe_write.value, gate.value};
    if (!UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST, jobs, sizeof(jobs), NULL, NULL) ||
        !UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
            handles, sizeof(handles), NULL, NULL)) { error = GetLastError(); goto done; }
    STARTUPINFOEXW startup = {0}; PROCESS_INFORMATION pi = {0};
    startup.StartupInfo.cb = sizeof(startup); startup.lpAttributeList = attributes;
    stage = 2; (void)remaining(&watch);
    if (!CreateProcessW(executable, command, NULL, NULL, TRUE,
        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW,
        environment, system, &startup.StartupInfo, &pi)) { error = GetLastError(); goto done; }
    controller.value = pi.hProcess; controller_thread.value = pi.hThread; controller_created = 1;
    if (!verified_member(controller.value, containment.value)) { error = ERROR_INVALID_DATA; goto done; }
    atomic_admission = 1;
    if (ResumeThread(controller_thread.value) != 1) { error = GetLastError(); goto done; }
    if (!close_once(&pipe_write)) { error = ERROR_INVALID_HANDLE; goto done; }
    stage = 3;
    if (!read_death_note(pipe_read.value, controller.value, &watch, &note, &error)) goto done;
    if (note.kind != DEATH_ACCOUNT || !fresh_account_name(note.account) || note.exact_members ||
        note.known_absent || note.known_reused || note.broker || note.child_process) {
        error = ERROR_INVALID_DATA; goto done;
    }
    memcpy(account, note.account, sizeof(account)); account_acknowledged = 1;
    SecureZeroMemory(&note, sizeof(note));
    /* Single account-custody acknowledgment. There is deliberately NO second observer signal. */
    if (!SetEvent(gate.value)) { error = GetLastError(); goto done; }
    if (!read_death_note(pipe_read.value, controller.value, &watch, &note, &error)) goto done;
    WCHAR empty_account[20] = {0};
    if (note.kind != DEATH_READY || note.exact_members != 2 || note.known_absent > 3 || note.known_reused > 3 ||
        note.known_absent + note.known_reused != 3 || memcmp(note.account, empty_account, sizeof(empty_account)) ||
        !note.broker || note.broker == UINTPTR_MAX || !note.child_process || note.child_process == UINTPTR_MAX ||
        note.broker == note.child_process) { error = ERROR_INVALID_DATA; goto done; }
    known_absent = note.known_absent; known_reused = note.known_reused;
    /* Parent-pull only, from the exact original controller, while its originals remain gated/live.
     * Do not request a job handle or accept numerical process IDs as resource identities. */
    if (!DuplicateHandle(controller.value, (HANDLE)note.broker, GetCurrentProcess(), &broker.value,
        PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, FALSE, 0)) { error = GetLastError(); goto done; }
    broker_pulled = 1;
    if (!DuplicateHandle(controller.value, (HANDLE)note.child_process, GetCurrentProcess(), &child_process.value,
        PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, FALSE, 0)) { error = GetLastError(); goto done; }
    child_pulled = 1;
    if (!death_live_process(controller.value, &error) || !death_live_process(broker.value, &error) ||
        !death_live_process(child_process.value, &error)) goto done;
    DWORD controller_id = GetProcessId(controller.value), broker_id = GetProcessId(broker.value);
    DWORD child_id = GetProcessId(child_process.value);
    if (!controller_id || !broker_id || !child_id || controller_id == broker_id || controller_id == child_id ||
        broker_id == child_id) { error = ERROR_INVALID_DATA; goto done; }
    if (!verified_member(broker.value, containment.value) || !verified_member(child_process.value, containment.value)) {
        error = ERROR_INVALID_DATA; goto done;
    }
    audit_ready = 1; stage = 4; (void)remaining(&watch);
    if (!TerminateProcess(controller.value, CONTROLLER_FAULT_EXIT)) { error = GetLastError(); goto done; }
    injected = 1;
    if (!death_exit_process(controller.value, &watch, &controller_exit, &error)) goto done;
    controller_exit_observed = 1;
    if (controller_exit != CONTROLLER_FAULT_EXIT) { error = ERROR_INVALID_DATA; goto done; }
    if (!death_exit_process(broker.value, &watch, &broker_exit, &error)) goto done;
    broker_exit_observed = 1;
    /* Refuse every broker self-failure path, including its watchdog and __fastfail fallback. */
    if (broker_exit == BROKER_GATE_ABORT_EXIT || broker_exit == 125u || broker_exit == 0xc0000409u) {
        error = ERROR_INVALID_DATA; goto done;
    }
    if (!death_exit_process(child_process.value, &watch, &child_exit, &error)) goto done;
    child_exit_observed = 1;
    if (child_exit == CHILD_EXIT) { error = ERROR_INVALID_DATA; goto done; }
    /* Nothing has closed or terminated the OUTER job. No explicit descendant termination occurred.
     * Only controller death can release its private last job handle at this fixed audited gate. */
    outer_open_during_observation = 1; stage = 5; result = 0;
done:
    /* Explicit failure containment must NEVER convert missing automatic retirement into a pass. */
    if (result != 0 && containment.value) {
        explicit_failure_termination = 1;
        if (!TerminateJobObject(containment.value, 125)) { if (!error) error = GetLastError(); cleanup = 0; }
    }
    if (controller.value) {
        DWORD ignored = STILL_ACTIVE, wait_error = 0;
        if (!death_exit_process(controller.value, &watch, &ignored, &wait_error)) {
            if (!error) error = wait_error; cleanup = 0;
        }
    }
    if (broker.value && !broker_exit_observed) {
        DWORD ignored = STILL_ACTIVE, wait_error = 0;
        if (!death_exit_process(broker.value, &watch, &ignored, &wait_error)) {
            if (!error) error = wait_error; cleanup = 0;
        }
    }
    if (child_process.value && !child_exit_observed) {
        DWORD ignored = STILL_ACTIVE, wait_error = 0;
        if (!death_exit_process(child_process.value, &watch, &ignored, &wait_error)) {
            if (!error) error = wait_error; cleanup = 0;
        }
    }
    if (!close_once(&child_process)) cleanup = 0;
    if (!close_once(&broker)) cleanup = 0;
    if (!close_once(&controller_thread)) cleanup = 0;
    if (!close_once(&controller)) cleanup = 0;
    if (containment.value) {
        containment_empty = await_empty_job(containment.value, &watch);
        if (!containment_empty) cleanup = 0;
    }
    if (account_acknowledged) {
        DWORD account_error = 0;
        account_disabled = death_disable_account(account, &account_error);
        if (!account_disabled) { if (!error) error = account_error; cleanup = 0; }
    }
    if (!close_once(&pipe_write)) cleanup = 0;
    if (!close_once(&pipe_read)) cleanup = 0;
    if (!close_once(&gate)) cleanup = 0;
    if (!close_once(&containment)) cleanup = 0;
    if (initialized) DeleteProcThreadAttributeList(attributes);
    if (attributes && !HeapFree(GetProcessHeap(), 0, attributes)) cleanup = 0;
    SecureZeroMemory(account, sizeof(account)); SecureZeroMemory(&note, sizeof(note));
    if (!finish_watchdog(&watch)) cleanup = 0;
    if (!cleanup) result = 8;
    if (!result) stage = 6;
    printf("{\"scope\":\"CONTROLLER_DEATH_POST_RETURN_GATE_NOT_INFLIGHT_OR_PROTECTED_SUPERVISION\","
        "\"mode\":2,\"result\":%d,\"stage\":%lu,\"systemCode\":%lu,"
        "\"accountAcknowledged\":%s,\"accountDisabledObserved\":%s,"
        "\"controllerCreated\":%s,\"controllerAtomicOuterAdmission\":%s,\"auditedGateObserved\":%s,"
        "\"brokerHandlePulled\":%s,\"childHandlePulled\":%s,\"controllerDeathInjected\":%s,"
        "\"controllerExitObserved\":%s,\"brokerExitObserved\":%s,\"childExitObserved\":%s,"
        "\"controllerExit\":%lu,\"brokerExit\":%lu,\"childExit\":%lu,"
        "\"outerJobOpenDuringObservation\":%s,\"outerJobEmptyObserved\":%s,"
        "\"explicitFailureTermination\":%s,\"cleanupObserved\":%s,"
        "\"knownHandleChecked\":%lu,\"knownHandleAbsent\":%lu,\"knownHandleReused\":%lu,"
        "\"privateJobDuplicated\":false,\"profileRequested\":false,\"nativeStorageExecuted\":false,"
        "\"inFlightCreationQualified\":false,\"protectedSupervisorQualified\":false}\n",
        result, (unsigned long)stage, (unsigned long)error,
        account_acknowledged ? "true" : "false", account_disabled ? "true" : "false",
        controller_created ? "true" : "false", atomic_admission ? "true" : "false", audit_ready ? "true" : "false",
        broker_pulled ? "true" : "false", child_pulled ? "true" : "false", injected ? "true" : "false",
        controller_exit_observed ? "true" : "false", broker_exit_observed ? "true" : "false",
        child_exit_observed ? "true" : "false", (unsigned long)controller_exit, (unsigned long)broker_exit,
        (unsigned long)child_exit, outer_open_during_observation ? "true" : "false",
        containment_empty ? "true" : "false", explicit_failure_termination ? "true" : "false",
        cleanup ? "true" : "false", (unsigned long)(audit_ready ? 3 : 0),
        (unsigned long)known_absent, (unsigned long)known_reused);
    return result;
}
#endif
