/* Fixed TEST-ONLY API compatibility experiment: WithLogonW + STARTUPINFOEXW + JOB_LIST.
 * The earlier WithTokenW/JOB_LIST refusal does not establish this API's behavior. Exactly one
 * credentialed creation is attempted, with no alternate launcher, assignment retry or fallback.
 * A passing returned-child observation is NOT proof of interrupted Secondary Logon handoff,
 * the Foundation supervisor, protected profile/JNI/storage, or installed-application lifetime.
 * The controlled child only checks its actual ordinary token and exits. No profile is requested. */
#define wmain p2pkit_unused_original_account_probe_main
#include "profile_account_probe.c"
#undef wmain

static int atomic_controller_admission(void) {
    owned_handle token = {0}, impersonation = {0}; TOKEN_ELEVATION elevation = {0}; DWORD size = 0;
    int okay = 0;
    if (OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, TRUE, &impersonation.value) ||
        GetLastError() != ERROR_NO_TOKEN ||
        !OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token.value) ||
        !GetTokenInformation(token.value, TokenElevation, &elevation, sizeof(elevation), &size) ||
        size != sizeof(elevation) || !elevation.TokenIsElevated) goto done;
    okay = 1;
done:
    if (!close_once(&impersonation)) okay = 0;
    if (!close_once(&token)) okay = 0;
    return okay;
}
static int atomic_disable_account(const WCHAR name[20], DWORD *error) {
    USER_INFO_1008 disabled = {UF_SCRIPT | UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE}; DWORD parameter = 0;
    NET_API_STATUS status = NetUserSetInfo(NULL, name, 1008, (LPBYTE)&disabled, &parameter);
    if (status != NERR_Success) { *error = status; return 0; }
    LPBYTE bytes = NULL;
    status = NetUserGetInfo(NULL, name, 1, &bytes);
    int okay = status == NERR_Success && bytes;
    if (okay) {
        const USER_INFO_1 *info = (const USER_INFO_1 *)bytes;
        okay = info->usri1_priv == USER_PRIV_USER && (info->usri1_flags & UF_ACCOUNTDISABLE) &&
            info->usri1_name && wcscmp(info->usri1_name, name) == 0;
    }
    if (!okay) *error = status == NERR_Success ? ERROR_INVALID_DATA : status;
    if (bytes && NetApiBufferFree(bytes) != NERR_Success) { *error = ERROR_INVALID_DATA; okay = 0; }
    return okay;
}
static int atomic_wait_empty(HANDLE job, const watchdog *watch, DWORD *active, DWORD *observations, DWORD *error) {
    for (;;) {
        JOBOBJECT_BASIC_ACCOUNTING_INFORMATION info = {0}; (void)remaining(watch);
        if (*observations >= 65536u) { *error = ERROR_NOT_ENOUGH_QUOTA; return 0; }
        if (!QueryInformationJobObject(job, JobObjectBasicAccountingInformation, &info, sizeof(info), NULL)) {
            *error = GetLastError(); return 0;
        }
        ++*observations; *active = info.ActiveProcesses; (void)remaining(watch);
        if (!*active) return 1;
        Sleep(1); /* Observation only, under the unchanged original watchdog; no failed API retry. */
    }
}
static int atomic_logon_probe(void) {
    watchdog watch; if (!native_x64() || !start_watchdog(&watch)) return 3;
    owned_handle token = {0}, child_token = {0}, process = {0}, thread = {0}, job = {0};
    LPPROC_THREAD_ATTRIBUTE_LIST attributes = NULL; SIZE_T attribute_size = 0; int initialized = 0;
    WCHAR name[20] = {0}, password[69] = {0}, executable[32768] = {0}, command[1024] = {0};
    WCHAR system[32768] = {0}, environment[65560] = {0};
    _Alignas(void *) unsigned char expected[SECURITY_MAX_SID_SIZE] = {0};
    _Alignas(void *) unsigned char actual[SECURITY_MAX_SID_SIZE] = {0};
    DWORD stage = 1, error = 0, parameter = 0, child_exit = STILL_ACTIVE, final_active = MAXDWORD, observations = 0;
    int result = 5, cleanup = 1, account_created = 0, account_enabled = 0, account_disabled = 0;
    int attempted = 0, extended_requested = 0, list_requested = 0, created = 0, member_observed = 0;
    int token_matched = 0, resumed = 0, child_executed = 0, exit_observed = 0, job_empty = 0;
    int failure_cleanup = 0;
    if (!atomic_controller_admission()) { error = ERROR_ACCESS_DENIED; goto done; }
    if (!credentials(name, password)) { error = ERROR_INVALID_DATA; goto done; }
    USER_INFO_1 account = {0}; account.usri1_name = name; account.usri1_password = password;
    account.usri1_priv = USER_PRIV_USER; account.usri1_flags = UF_SCRIPT | UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE;
    stage = 2;
    error = NetUserAdd(NULL, 1, (LPBYTE)&account, &parameter);
    if (error != NERR_Success) goto done; /* Never adopt, reset, delete or enumerate another account. */
    account_created = 1;
    /* This controller owns the successful creation before enabling it. Premature controller death
     * is NOT qualified cleanup; any retained fixture account requires authorized disposable-VM teardown. */
    USER_INFO_1008 enabled = {UF_SCRIPT | UF_NORMAL_ACCOUNT};
    error = NetUserSetInfo(NULL, name, 1008, (LPBYTE)&enabled, &parameter);
    if (error != NERR_Success) goto done;
    account_enabled = 1; stage = 3;
    error = ordinary_group(name);
    if (error != NERR_Success) goto done;
    if (!LogonUserW(name, L".", password, LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT, &token.value)) {
        error = GetLastError(); goto done;
    }
    if (!standard_token(token.value) || !token_sid(token.value, expected)) { error = ERROR_INVALID_DATA; goto done; }
    stage = 4;
    job.value = CreateJobObjectW(NULL, NULL);
    if (!job.value) { error = GetLastError(); goto done; }
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!SetInformationJobObject(job.value, JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        error = GetLastError(); goto done;
    }
    /* The controller is NOT associated with this new job. Returned-child membership therefore
     * cannot be mistaken for ordinary inheritance from this controller's own private job. */
    (void)InitializeProcThreadAttributeList(NULL, 1, 0, &attribute_size);
    if (!attribute_size || attribute_size > 1024 * 1024) { error = ERROR_INVALID_DATA; goto done; }
    attributes = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, attribute_size);
    if (!attributes) { error = ERROR_NOT_ENOUGH_MEMORY; goto done; }
    if (!InitializeProcThreadAttributeList(attributes, 1, 0, &attribute_size)) { error = GetLastError(); goto done; }
    initialized = 1;
    HANDLE jobs[] = {job.value};
    if (!UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST, jobs, sizeof(jobs), NULL, NULL)) {
        error = GetLastError(); goto done;
    }
    list_requested = 1; stage = 5;
    DWORD length = GetModuleFileNameW(NULL, executable, 32768);
    UINT system_length = GetSystemWindowsDirectoryW(system, 32768);
    if (!length || length > 900 || wcschr(executable, L'"') || !system_length || system_length >= 32768 ||
        swprintf_s(command, 1024, L"\"%ls\" --atomic-logon-standard-child", executable) <= 0) {
        error = ERROR_INVALID_DATA; goto done;
    }
    int count = swprintf_s(environment, 65560, L"SystemRoot=%ls", system);
    if (count <= 0) { error = ERROR_INVALID_DATA; goto done; }
    int second = swprintf_s(environment + count + 1, 65560 - (size_t)count - 1, L"WINDIR=%ls", system);
    if (second <= 0) { error = ERROR_INVALID_DATA; goto done; }
    environment[(size_t)count + 1 + (size_t)second + 1] = 0;
    STARTUPINFOEXW startup = {0}; PROCESS_INFORMATION pi = {0};
    startup.StartupInfo.cb = sizeof(startup); startup.lpAttributeList = attributes;
    extended_requested = 1; stage = 6; (void)remaining(&watch); attempted = 1;
    /* One fixed API attempt. ERROR_INVALID_PARAMETER/87 remains a failed compatibility experiment.
     * No debugger, assignment-after-create, altered privileges or alternate API can replace this call. */
    if (!CreateProcessWithLogonW(name, L".", password, 0, executable, command,
        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW,
        environment, system, &startup.StartupInfo, &pi)) {
        error = GetLastError();
        /* Contradictory failure outputs are quarantined, not adopted or closed as trusted owners. */
        if (pi.hProcess || pi.hThread) cleanup = 0;
        goto done;
    }
    created = 1;
    if (!pi.hProcess || !pi.hThread || pi.hProcess == INVALID_HANDLE_VALUE || pi.hThread == INVALID_HANDLE_VALUE ||
        pi.hProcess == pi.hThread) { error = ERROR_INVALID_HANDLE; cleanup = 0; goto done; }
    process.value = pi.hProcess; thread.value = pi.hThread;
    SecureZeroMemory(password, sizeof(password)); stage = 7; (void)remaining(&watch);
    BOOL member = FALSE;
    if (!IsProcessInJob(process.value, job.value, &member)) { error = GetLastError(); goto done; }
    if (!member) { error = ERROR_INVALID_DATA; goto done; }
    member_observed = 1;
    if (!OpenProcessToken(process.value, TOKEN_QUERY, &child_token.value)) { error = GetLastError(); goto done; }
    if (!standard_token(child_token.value) || !token_sid(child_token.value, actual) || !EqualSid(expected, actual)) {
        error = ERROR_INVALID_DATA; goto done;
    }
    token_matched = 1; stage = 8;
    DWORD previous_suspend = ResumeThread(thread.value);
    if (previous_suspend != 1) { error = previous_suspend == MAXDWORD ? GetLastError() : ERROR_INVALID_DATA; goto done; }
    resumed = 1;
    DWORD waited = WaitForSingleObject(process.value, remaining(&watch));
    if (waited != WAIT_OBJECT_0) { error = waited == WAIT_FAILED ? GetLastError() : ERROR_INVALID_DATA; goto done; }
    (void)remaining(&watch);
    if (!GetExitCodeProcess(process.value, &child_exit)) { error = GetLastError(); goto done; }
    exit_observed = 1;
    if (child_exit != CHILD_EXIT) { error = ERROR_INVALID_DATA; goto done; }
    child_executed = 1; stage = 9; result = 0;
done:
    SecureZeroMemory(password, sizeof(password));
    /* Explicit error retirement cannot turn this experiment into a pass. Use original owners only. */
    if (result != 0 && process.value) {
        DWORD waited = WaitForSingleObject(process.value, 0);
        if (waited == WAIT_TIMEOUT) {
            failure_cleanup = 1;
            if (!TerminateProcess(process.value, 125)) { if (!error) error = GetLastError(); cleanup = 0; }
            if (WaitForSingleObject(process.value, remaining(&watch)) != WAIT_OBJECT_0) cleanup = 0;
        } else if (waited != WAIT_OBJECT_0) cleanup = 0;
    }
    if (result != 0 && job.value) {
        failure_cleanup = 1;
        if (!TerminateJobObject(job.value, 125)) { if (!error) error = GetLastError(); cleanup = 0; }
    }
    if (!close_once(&child_token)) cleanup = 0;
    if (!close_once(&thread)) cleanup = 0;
    if (!close_once(&process)) cleanup = 0;
    if (!close_once(&token)) cleanup = 0;
    if (job.value) {
        DWORD job_error = 0;
        job_empty = atomic_wait_empty(job.value, &watch, &final_active, &observations, &job_error);
        if (!job_empty) { if (!error) error = job_error; cleanup = 0; }
    }
    if (account_created) {
        DWORD account_error = 0;
        account_disabled = atomic_disable_account(name, &account_error);
        if (!account_disabled) { if (!error) error = account_error; cleanup = 0; }
    }
    if (initialized) DeleteProcThreadAttributeList(attributes);
    if (attributes && !HeapFree(GetProcessHeap(), 0, attributes)) cleanup = 0;
    if (!close_once(&job)) cleanup = 0;
    SecureZeroMemory(name, sizeof(name)); SecureZeroMemory(expected, sizeof(expected)); SecureZeroMemory(actual, sizeof(actual));
    if (!finish_watchdog(&watch)) cleanup = 0;
    if (!cleanup) result = 8;
    if (!result) stage = 10;
    printf("{\"scope\":\"ATOMIC_LOGON_JOB_LIST_API_PROBE_NOT_PROTECTED_SUPERVISION\","
        "\"launchApi\":\"CreateProcessWithLogonW\",\"result\":%d,\"stage\":%lu,\"systemCode\":%lu,"
        "\"accountCreated\":%s,\"accountEnabled\":%s,\"accountDisabledObserved\":%s,"
        "\"creationAttempted\":%s,\"startupInfoExRequested\":%s,\"jobListRequested\":%s,\"created\":%s,"
        "\"memberBeforeResume\":%s,\"tokenMatched\":%s,\"resumed\":%s,\"childExecuted\":%s,"
        "\"childExitObserved\":%s,\"childExit\":%lu,\"finalJobActiveProcesses\":%lu,\"jobObservations\":%lu,"
        "\"jobEmptyObserved\":%s,\"cleanupObserved\":%s,\"explicitFailureCleanup\":%s,"
        "\"profileRequested\":false,\"nativeStorageExecuted\":false,"
        "\"inFlightCreationQualified\":false,\"protectedSupervisorQualified\":false}\n",
        result, (unsigned long)stage, (unsigned long)error,
        account_created ? "true" : "false", account_enabled ? "true" : "false", account_disabled ? "true" : "false",
        attempted ? "true" : "false", extended_requested ? "true" : "false", list_requested ? "true" : "false",
        created ? "true" : "false", member_observed ? "true" : "false", token_matched ? "true" : "false",
        resumed ? "true" : "false", child_executed ? "true" : "false", exit_observed ? "true" : "false",
        (unsigned long)child_exit, (unsigned long)final_active, (unsigned long)observations,
        job_empty ? "true" : "false", cleanup ? "true" : "false", failure_cleanup ? "true" : "false");
    return result;
}
int wmain(int argc, WCHAR **argv) {
    if (argc != 2) return 2;
    if (wcscmp(argv[1], L"--atomic-logon-standard-child") == 0) return child();
    if (wcscmp(argv[1], L"--disposable-atomic-logon-environment-probe") == 0) return atomic_logon_probe();
    return 2;
}
