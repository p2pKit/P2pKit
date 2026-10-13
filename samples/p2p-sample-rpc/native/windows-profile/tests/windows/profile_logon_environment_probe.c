/* Test-only environmental bootstrap, NOT the protected-payload supervisor.
 * No documented/qualified WithLogonW JOB_LIST path is used. This has a suspended post-creation
 * admission interval; no profile DLL/JNI/storage may execute through this path.
 * Once admitted it runs only the unchanged same-token atomic-job probe.
 * Never use this as a fallback for failed AsUserW or standard-user admission. */
#define wmain p2pkit_original_account_probe_main
#include "profile_account_probe.c"
#undef wmain

static int bootstrap(void) {
    watchdog watch;
    if (!native_x64() || !start_watchdog(&watch)) return 3;
    WCHAR name[20] = {0}, password[69] = {0}, executable[32768] = {0}, command[1024] = {0};
    WCHAR system[32768] = {0}, environment[65560] = {0};
    _Alignas(void *) unsigned char expected[SECURITY_MAX_SID_SIZE] = {0};
    _Alignas(void *) unsigned char actual[SECURITY_MAX_SID_SIZE] = {0};
    owned_handle token = {0}, controller = {0}, child_token = {0}, job = {0}, process = {0}, thread = {0};
    owned_handle impersonation = {0};
    int account_created = 0, created = 0, assigned = 0, resumed = 0, cleanup = 1, result = 5;
    DWORD stage = 1, error = 0, parameter = 0, child_exit = STILL_ACTIVE;
    TOKEN_ELEVATION elevation = {0}; DWORD size = 0;
    /* This explicitly selected hosted setup requires its actual elevated controller.
     * It never grants privileges or weakens an existing account/profile policy. */
    if (OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, TRUE, &impersonation.value) ||
        GetLastError() != ERROR_NO_TOKEN ||
        !OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &controller.value) ||
        !GetTokenInformation(controller.value, TokenElevation, &elevation, sizeof(elevation), &size) ||
        size != sizeof(elevation) || !elevation.TokenIsElevated) goto done;
    if (!credentials(name, password)) goto done;
    USER_INFO_1 account = {0};
    account.usri1_name = name; account.usri1_password = password; account.usri1_priv = USER_PRIV_USER;
    account.usri1_flags = UF_SCRIPT | UF_NORMAL_ACCOUNT;
    error = NetUserAdd(NULL, 1, (LPBYTE)&account, &parameter);
    if (error != NERR_Success) goto done; /* Never adopt or reset any existing account. */
    account_created = 1; stage = 2;
    error = ordinary_group(name);
    if (error != NERR_Success) goto done;
    stage = 3;
    if (!LogonUserW(name, L".", password, LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT, &token.value)) {
        error = GetLastError(); goto done;
    }
    if (!standard_token(token.value) || !token_sid(token.value, expected)) goto done;
    stage = 4;
    DWORD length = GetModuleFileNameW(NULL, executable, 32768);
    UINT system_length = GetSystemWindowsDirectoryW(system, 32768);
    if (!length || length > 900 || wcschr(executable, L'"') || !system_length || system_length >= 32768 ||
        swprintf_s(command, 1024, L"\"%ls\" --same-token-environment-child", executable) <= 0) goto done;
    int count = swprintf_s(environment, 65560, L"SystemRoot=%ls", system);
    if (count <= 0) goto done;
    int second = swprintf_s(environment + count + 1, 65560 - (size_t)count - 1, L"WINDIR=%ls", system);
    if (second <= 0) goto done;
    environment[(size_t)count + 1 + (size_t)second + 1] = 0;
    job.value = CreateJobObjectW(NULL, NULL);
    if (!job.value) { error = GetLastError(); goto done; }
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!SetInformationJobObject(job.value, JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        error = GetLastError(); goto done;
    }
    stage = 5; (void)remaining(&watch);
    STARTUPINFOW startup = {0}; PROCESS_INFORMATION pi = {0}; startup.cb = sizeof(startup);
    /* No LOGON_WITH_PROFILE, inherited environment, shell, requested privileges or payload selection.
     * The bootstrap is NOT atomically assigned at creation, hence cannot qualify the protected smoke. */
    if (!CreateProcessWithLogonW(name, L".", password, 0, executable, command,
        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW,
        environment, system, &startup, &pi)) { error = GetLastError(); goto done; }
    process.value = pi.hProcess; thread.value = pi.hThread; created = 1;
    SecureZeroMemory(password, sizeof(password));
    (void)remaining(&watch); stage = 6;
    if (!AssignProcessToJobObject(job.value, process.value)) { error = GetLastError(); goto done; }
    assigned = 1;
    BOOL member = FALSE;
    if (!IsProcessInJob(process.value, job.value, &member) || !member ||
        !OpenProcessToken(process.value, TOKEN_QUERY, &child_token.value) ||
        !standard_token(child_token.value) || !token_sid(child_token.value, actual) || !EqualSid(expected, actual)) {
        error = GetLastError(); goto done;
    }
    stage = 7; (void)remaining(&watch);
    if (ResumeThread(thread.value) != 1) { error = GetLastError(); goto done; }
    resumed = 1;
    if (WaitForSingleObject(process.value, remaining(&watch)) != WAIT_OBJECT_0) goto done;
    (void)remaining(&watch);
    if (!GetExitCodeProcess(process.value, &child_exit) || child_exit != 0) { error = child_exit; goto done; }
    stage = 8; result = 0;
done:
    SecureZeroMemory(password, sizeof(password));
    if (created && WaitForSingleObject(process.value, 0) != WAIT_OBJECT_0) {
        if (!TerminateProcess(process.value, 125)) cleanup = 0;
        if (WaitForSingleObject(process.value, remaining(&watch)) != WAIT_OBJECT_0) cleanup = 0;
    }
    if (job.value) {
        JOBOBJECT_BASIC_ACCOUNTING_INFORMATION info = {0};
        if (!QueryInformationJobObject(job.value, JobObjectBasicAccountingInformation, &info, sizeof(info), NULL) ||
            info.ActiveProcesses != 0) cleanup = 0;
    }
    if (account_created) {
        USER_INFO_1008 disabled = {UF_SCRIPT | UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE};
        if (NetUserSetInfo(NULL, name, 1008, (LPBYTE)&disabled, &parameter) != NERR_Success) cleanup = 0;
        /* Disabled fixture account retained until GitHub destroys this disposable VM. */
    }
    if (!close_once(&impersonation)) cleanup = 0;
    if (!close_once(&controller)) cleanup = 0;
    if (!close_once(&child_token)) cleanup = 0;
    if (!close_once(&thread)) cleanup = 0;
    if (!close_once(&process)) cleanup = 0;
    if (!close_once(&token)) cleanup = 0;
    if (!close_once(&job)) cleanup = 0;
    SecureZeroMemory(name, sizeof(name)); SecureZeroMemory(expected, sizeof(expected));
    SecureZeroMemory(actual, sizeof(actual));
    if (!finish_watchdog(&watch)) cleanup = 0;
    (void)remaining(&watch);
    if (!cleanup) result = 8;
    printf("{\"scope\":\"LOGON_ENVIRONMENT_FEASIBILITY_NOT_PROTECTED_SUPERVISION\","
        "\"launchApi\":\"CreateProcessWithLogonW\",\"result\":%d,\"stage\":%lu,\"systemCode\":%lu,"
        "\"accountCreated\":%s,\"created\":%s,\"assignedBeforeResume\":%s,\"resumed\":%s,"
        "\"sameTokenProbeExit\":%lu,\"cleanupObserved\":%s,\"bootstrapAtomicJobAdmission\":false,"
        "\"profileRequested\":false,\"nativeStorageExecuted\":false}\n", result,
        (unsigned long)stage, (unsigned long)error, account_created ? "true" : "false", created ? "true" : "false",
        assigned ? "true" : "false", resumed ? "true" : "false", (unsigned long)child_exit,
        cleanup ? "true" : "false");
    return result;
}
int wmain(int argc, WCHAR **argv) {
    if (argc != 2) return 2;
    if (wcscmp(argv[1], L"--standard-account-probe-child") == 0) return child();
    if (wcscmp(argv[1], L"--same-token-environment-child") == 0) return run_probe(EXISTING_STANDARD_USER);
    if (wcscmp(argv[1], L"--disposable-logon-environment-probe") != 0) return 2;
    return bootstrap();
}
