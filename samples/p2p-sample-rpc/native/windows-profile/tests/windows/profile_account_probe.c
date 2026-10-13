/* Test-only launch feasibility probes. No P2pKit storage code is linked or executed.
 * The credentialed lane creates/disables one fresh ordinary account on the separately approved runner.
 * The explicit existing-standard-user lane makes NO account/profile/credential/privilege changes and
 * must start inside an independently approved disposable standard-user session. It is NOT a fallback.
 * Neither lane is the native-smoke supervisor or application lifecycle qualification. */
#if !defined(_WIN32) || !defined(_M_X64)
#error Real Windows x64 SDK/compiler required.
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <lm.h>
#include <bcrypt.h>
#include <intrin.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#define PROBE_MS 60000u
#define CHILD_EXIT 42u
typedef struct { HANDLE value; int failed; } owned_handle;
typedef struct { owned_handle event, thread; ULONGLONG start; } watchdog;

static int close_once(owned_handle *owner) {
    HANDLE original = owner->value;
    owner->value = NULL;
    if (original && original != INVALID_HANDLE_VALUE && !CloseHandle(original)) owner->failed = 1;
    return !owner->failed;
}
static void expired(void) {
    (void)TerminateProcess(GetCurrentProcess(), 125);
    __fastfail(FAST_FAIL_FATAL_APP_EXIT);
}
static DWORD remaining(const watchdog *watch) {
    ULONGLONG elapsed = GetTickCount64() - watch->start;
    if (elapsed >= PROBE_MS) expired();
    return (DWORD)(PROBE_MS - elapsed);
}
static DWORD WINAPI watchdog_thread(void *argument) {
    watchdog *watch = argument;
    if (WaitForSingleObject(watch->event.value, remaining(watch)) != WAIT_OBJECT_0) expired();
    (void)remaining(watch);
    return 0;
}
static int start_watchdog(watchdog *watch) {
    memset(watch, 0, sizeof(*watch));
    watch->start = GetTickCount64();
    watch->event.value = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!watch->event.value) return 0;
    watch->thread.value = CreateThread(NULL, 0, watchdog_thread, watch, 0, NULL);
    if (!watch->thread.value) { (void)close_once(&watch->event); return 0; }
    (void)remaining(watch);
    return 1;
}
static int finish_watchdog(watchdog *watch) {
    (void)remaining(watch);
    if (!SetEvent(watch->event.value) ||
        WaitForSingleObject(watch->thread.value, remaining(watch)) != WAIT_OBJECT_0) expired();
    int okay = close_once(&watch->thread);
    if (!close_once(&watch->event)) okay = 0;
    (void)remaining(watch);
    return okay;
}
static int native_x64(void) {
    USHORT process = 0, native = 0;
    return sizeof(void *) == 8 && IsWow64Process2(GetCurrentProcess(), &process, &native) &&
        process == IMAGE_FILE_MACHINE_UNKNOWN && native == IMAGE_FILE_MACHINE_AMD64;
}
static int token_sid(HANDLE token, unsigned char sid[SECURITY_MAX_SID_SIZE]) {
    _Alignas(void *) unsigned char bytes[4096] = {0};
    DWORD size = 0; int okay = 0;
    if (GetTokenInformation(token, TokenUser, bytes, sizeof(bytes), &size) &&
        size >= sizeof(TOKEN_USER) && size <= sizeof(bytes)) {
        PSID value = ((TOKEN_USER *)bytes)->User.Sid;
        if (IsValidSid(value) && GetLengthSid(value) <= SECURITY_MAX_SID_SIZE)
            okay = CopySid(SECURITY_MAX_SID_SIZE, sid, value) != 0;
    }
    SecureZeroMemory(bytes, sizeof(bytes));
    return okay;
}
static int standard_token(HANDLE token) {
    TOKEN_ELEVATION elevation = {0}; TOKEN_ELEVATION_TYPE type;
    _Alignas(void *) unsigned char user[4096] = {0}, owner[4096] = {0}, groups[16384] = {0};
    DWORD size = 0; int okay = 0;
    if (!GetTokenInformation(token, TokenElevation, &elevation, sizeof(elevation), &size) ||
        size != sizeof(elevation) || elevation.TokenIsElevated ||
        !GetTokenInformation(token, TokenElevationType, &type, sizeof(type), &size) ||
        size != sizeof(type) || type != TokenElevationTypeDefault) goto done;
    if (!GetTokenInformation(token, TokenUser, user, sizeof(user), &size) ||
        size < sizeof(TOKEN_USER) || size > sizeof(user) ||
        !GetTokenInformation(token, TokenOwner, owner, sizeof(owner), &size) ||
        size < sizeof(TOKEN_OWNER) || size > sizeof(owner)) goto done;
    PSID user_sid = ((TOKEN_USER *)user)->User.Sid;
    PSID owner_sid = ((TOKEN_OWNER *)owner)->Owner;
    if (!IsValidSid(user_sid) || !IsValidSid(owner_sid) || !EqualSid(user_sid, owner_sid) ||
        IsWellKnownSid(user_sid, WinLocalSystemSid) || IsWellKnownSid(user_sid, WinLocalServiceSid) ||
        IsWellKnownSid(user_sid, WinNetworkServiceSid)) goto done;
    if (!GetTokenInformation(token, TokenGroups, groups, sizeof(groups), &size) ||
        size < offsetof(TOKEN_GROUPS, Groups) || size > sizeof(groups)) goto done;
    TOKEN_GROUPS *list = (TOKEN_GROUPS *)groups;
    if (list->GroupCount > (size - offsetof(TOKEN_GROUPS, Groups)) / sizeof(SID_AND_ATTRIBUTES)) goto done;
    for (DWORD i = 0; i < list->GroupCount; ++i)
        if (!IsValidSid(list->Groups[i].Sid) || IsWellKnownSid(list->Groups[i].Sid, WinBuiltinAdministratorsSid) ||
            IsWellKnownSid(list->Groups[i].Sid, WinServiceSid)) goto done;
    okay = 1;
done:
    SecureZeroMemory(user, sizeof(user)); SecureZeroMemory(owner, sizeof(owner));
    SecureZeroMemory(groups, sizeof(groups));
    return okay;
}
static int child(void) {
    owned_handle token = {0}, impersonation = {0}; int okay = 0, cleanup = 1;
    if (!native_x64()) goto done;
    if (OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, TRUE, &impersonation.value) ||
        GetLastError() != ERROR_NO_TOKEN) goto done;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token.value)) goto done;
    okay = standard_token(token.value);
done:
    if (!close_once(&token)) cleanup = 0;
    if (!close_once(&impersonation)) cleanup = 0;
    return !cleanup ? 8 : okay ? (int)CHILD_EXIT : 3;
}
static int credentials(WCHAR name[20], WCHAR password[69]) {
    unsigned char random[39] = {0};
    static const WCHAR hex[] = L"0123456789abcdef";
    if (BCryptGenRandom(NULL, random, sizeof(random), BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0) {
        SecureZeroMemory(random, sizeof(random)); return 0;
    }
    memcpy(name, L"p2ppr", 5 * sizeof(WCHAR));
    for (size_t i = 0; i < 7; ++i) {
        name[5 + 2 * i] = hex[random[i] >> 4]; name[6 + 2 * i] = hex[random[i] & 15];
    }
    name[19] = 0;
    for (size_t i = 0; i < 32; ++i) {
        password[2 * i] = hex[random[7 + i] >> 4]; password[2 * i + 1] = hex[random[7 + i] & 15];
    }
    memcpy(password + 64, L"Aa!9", 5 * sizeof(WCHAR));
    SecureZeroMemory(random, sizeof(random));
    return 1;
}
static NET_API_STATUS ordinary_group(WCHAR *name) {
    _Alignas(void *) unsigned char sid[SECURITY_MAX_SID_SIZE] = {0};
    WCHAR group[256] = {0}, domain[256] = {0}; SID_NAME_USE use;
    DWORD sid_size = sizeof(sid), group_size = 256, domain_size = 256;
    if (!CreateWellKnownSid(WinBuiltinUsersSid, NULL, sid, &sid_size) ||
        !LookupAccountSidW(NULL, sid, group, &group_size, domain, &domain_size, &use) ||
        use != SidTypeAlias) return ERROR_INVALID_DATA;
    LOCALGROUP_MEMBERS_INFO_3 member = {name};
    NET_API_STATUS result = NetLocalGroupAddMembers(NULL, group, 3, (LPBYTE)&member, 1);
    SecureZeroMemory(sid, sizeof(sid)); SecureZeroMemory(group, sizeof(group));
    SecureZeroMemory(domain, sizeof(domain));
    return result == ERROR_MEMBER_IN_ALIAS ? NERR_Success : result;
}
typedef enum { FRESH_CREDENTIALED_ACCOUNT = 0, EXISTING_STANDARD_USER = 1 } probe_environment;
static int run_probe(probe_environment environment_kind) {
    watchdog watch;
    if (!native_x64() || !start_watchdog(&watch)) return 3;
    WCHAR name[20] = {0}, password[69] = {0}, executable[32768] = {0}, command[1024] = {0};
    WCHAR system[32768] = {0}, environment[65560] = {0};
    _Alignas(void *) unsigned char expected_sid[SECURITY_MAX_SID_SIZE] = {0};
    _Alignas(void *) unsigned char observed_sid[SECURITY_MAX_SID_SIZE] = {0};
    owned_handle token = {0}, job = {0}, process = {0}, thread = {0}, child_token = {0};
    owned_handle controller_thread = {0};
    LPPROC_THREAD_ATTRIBUTE_LIST attributes = NULL;
    int initialized = 0, account_created = 0, created = 0, resumed = 0, result = 5, cleanup = 1;
    DWORD error = 0, parameter = 0, stage = 1; SIZE_T attribute_size = 0;
    if (OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, TRUE, &controller_thread.value)) goto done;
    if (GetLastError() != ERROR_NO_TOKEN) { error = GetLastError(); goto done; }
    if (environment_kind == EXISTING_STANDARD_USER) {
        /* A pre-established normal login owns this token. Never provision/switch/elevate from here. */
        if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token.value)) {
            error = GetLastError(); goto done;
        }
        /* Distinguish positive observation of an elevated token from unavailable/failed admission.
         * Only this successful query permits the hosted negative control to claim policy rejection. */
        TOKEN_ELEVATION elevation = {0}; DWORD elevation_size = 0;
        if (!GetTokenInformation(token.value, TokenElevation, &elevation, sizeof(elevation), &elevation_size) ||
            elevation_size != sizeof(elevation)) { error = GetLastError(); goto done; }
        if (elevation.TokenIsElevated) { result = 3; stage = 10; goto done; }
    } else {
        if (!credentials(name, password)) goto done;
        USER_INFO_1 account = {0};
        account.usri1_name = name; account.usri1_password = password; account.usri1_priv = USER_PRIV_USER;
        account.usri1_flags = UF_SCRIPT | UF_NORMAL_ACCOUNT;
        error = NetUserAdd(NULL, 1, (LPBYTE)&account, &parameter);
        if (error != NERR_Success) goto done; /* Collision refuses; never adopt/reset an existing account. */
        account_created = 1; stage = 2;
        error = ordinary_group(name);
        if (error != NERR_Success) goto done;
        stage = 3;
        if (!LogonUserW(name, L".", password, LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT, &token.value)) {
            error = GetLastError(); goto done;
        }
        SecureZeroMemory(password, sizeof(password));
    }
    if (!standard_token(token.value) || !token_sid(token.value, expected_sid)) {
        if (environment_kind == EXISTING_STANDARD_USER) result = 3;
        goto done;
    }
    stage = 4;
    DWORD length = GetModuleFileNameW(NULL, executable, 32768);
    if (!length || length >= 32768 || wcschr(executable, L'"')) goto done;
    UINT system_length = GetSystemWindowsDirectoryW(system, 32768);
    if (!system_length || system_length >= 32768) goto done;
    if (length > 900 || swprintf_s(command, 1024, L"\"%ls\" --standard-account-probe-child", executable) <= 0)
        goto done; /* Keep the same deliberately narrow command bound across credentialed APIs. */
    int count = swprintf_s(environment, 65560, L"SystemRoot=%ls", system);
    if (count <= 0) goto done;
    int second = swprintf_s(environment + count + 1, 65560 - (size_t)count - 1, L"WINDIR=%ls", system);
    if (second <= 0) goto done;
    environment[(size_t)count + 1 + (size_t)second + 1] = 0; /* Minimal double-NUL environment; no credentials. */
    job.value = CreateJobObjectW(NULL, NULL);
    if (!job.value) { error = GetLastError(); goto done; }
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!SetInformationJobObject(job.value, JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        error = GetLastError(); goto done;
    }
    stage = 5;
    (void)InitializeProcThreadAttributeList(NULL, 1, 0, &attribute_size);
    if (!attribute_size || attribute_size > 1024 * 1024) goto done;
    attributes = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, attribute_size);
    if (!attributes) goto done;
    if (!InitializeProcThreadAttributeList(attributes, 1, 0, &attribute_size)) {
        error = GetLastError(); goto done;
    }
    initialized = 1;
    HANDLE jobs[] = {job.value};
    if (!UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST, jobs, sizeof(jobs), NULL, NULL)) {
        error = GetLastError(); goto done;
    }
    STARTUPINFOEXW startup = {0}; PROCESS_INFORMATION pi = {0};
    startup.StartupInfo.cb = sizeof(startup); startup.lpAttributeList = attributes;
    stage = 6; (void)remaining(&watch);
    /* The prior WithTokenW/JOB_LIST combination refused creation with ERROR_INVALID_PARAMETER.
     * Exercise the documented AsUserW extended-startup path, never an unowned/elevated fallback.
     * The API may enable privileges already held by the caller for this call; no rights are granted.
     * FALSE requests no handle inheritance. Adversarial inheritance/capture controls remain separate. */
    if (environment_kind == EXISTING_STANDARD_USER) {
        /* Same-token creation requires neither cross-token launch rights nor credentials. Keep atomic
         * job admission and suspended verification identical; this branch is explicitly selected at entry. */
        if (!CreateProcessW(executable, command, NULL, NULL, FALSE,
            CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW,
            environment, system, &startup.StartupInfo, &pi)) { error = GetLastError(); goto done; }
    } else {
        if (!CreateProcessAsUserW(token.value, executable, command, NULL, NULL, FALSE,
            CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW,
            environment, system, &startup.StartupInfo, &pi)) { error = GetLastError(); goto done; }
    }
    process.value = pi.hProcess; thread.value = pi.hThread; created = 1;
    (void)remaining(&watch); stage = 7;
    BOOL member = FALSE;
    if (!IsProcessInJob(process.value, job.value, &member) || !member ||
        !OpenProcessToken(process.value, TOKEN_QUERY, &child_token.value) || !standard_token(child_token.value) ||
        !token_sid(child_token.value, observed_sid) || !EqualSid(expected_sid, observed_sid)) {
        error = GetLastError(); goto done;
    }
    stage = 8; (void)remaining(&watch);
    if (ResumeThread(thread.value) != 1) { error = GetLastError(); goto done; }
    resumed = 1;
    if (WaitForSingleObject(process.value, remaining(&watch)) != WAIT_OBJECT_0) goto done;
    (void)remaining(&watch);
    DWORD exit_code = 0;
    if (!GetExitCodeProcess(process.value, &exit_code) || exit_code != CHILD_EXIT) { error = exit_code; goto done; }
    stage = 9; result = 0;
done:
    SecureZeroMemory(password, sizeof(password));
    /* Directly returned original process handles authorize cleanup even if admission verification fails.
     * No PID lookup, process-name sweep, post-create assignment or unowned-launch fallback exists. */
    if (created) {
        DWORD observed = WaitForSingleObject(process.value, 0);
        if (observed != WAIT_OBJECT_0) {
            if (!TerminateProcess(process.value, 125)) cleanup = 0;
            if (WaitForSingleObject(process.value, remaining(&watch)) != WAIT_OBJECT_0) cleanup = 0;
        }
    }
    if (job.value) {
        JOBOBJECT_BASIC_ACCOUNTING_INFORMATION info = {0};
        if (!QueryInformationJobObject(job.value, JobObjectBasicAccountingInformation, &info, sizeof(info), NULL) ||
            info.ActiveProcesses != 0) cleanup = 0;
    }
    if (account_created) {
        USER_INFO_1008 disabled = {UF_SCRIPT | UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE};
        if (NetUserSetInfo(NULL, name, 1008, (LPBYTE)&disabled, &parameter) != NERR_Success) cleanup = 0;
        /* Retain this disabled account until the disposable VM is destroyed; no profile was requested. */
    }
    if (!close_once(&controller_thread)) cleanup = 0;
    if (!close_once(&child_token)) cleanup = 0;
    if (!close_once(&thread)) cleanup = 0;
    if (!close_once(&process)) cleanup = 0;
    if (!close_once(&token)) cleanup = 0;
    if (!close_once(&job)) cleanup = 0;
    if (initialized) DeleteProcThreadAttributeList(attributes);
    if (attributes && !HeapFree(GetProcessHeap(), 0, attributes)) cleanup = 0;
    SecureZeroMemory(name, sizeof(name)); SecureZeroMemory(expected_sid, sizeof(expected_sid));
    SecureZeroMemory(observed_sid, sizeof(observed_sid));
    if (!finish_watchdog(&watch)) cleanup = 0;
    (void)remaining(&watch);
    if (!cleanup) result = 8;
    printf("{\"scope\":\"%s\",\"launchApi\":\"%s\",\"accountCreated\":%s,"
           "\"result\":%d,\"stage\":%lu,\"systemCode\":%lu,\"created\":%s,\"resumed\":%s,"
           "\"cleanupObserved\":%s,\"nativeStorageExecuted\":false}\n",
           environment_kind == EXISTING_STANDARD_USER ? "EXISTING_STANDARD_USER_ADMISSION_NOT_SMOKE_OR_RELEASE" :
               "ACCOUNT_ADMISSION_FEASIBILITY_NOT_SMOKE_OR_RELEASE",
           environment_kind == EXISTING_STANDARD_USER ? "CreateProcessW" : "CreateProcessAsUserW",
           account_created ? "true" : "false", result, (unsigned long)stage, (unsigned long)error,
           created ? "true" : "false", resumed ? "true" : "false", cleanup ? "true" : "false");
    return result;
}
int wmain(int argc, WCHAR **argv) {
    if (argc != 2) return 2;
    if (wcscmp(argv[1], L"--standard-account-probe-child") == 0) return child();
    if (wcscmp(argv[1], L"--existing-disposable-standard-user-probe") == 0)
        return run_probe(EXISTING_STANDARD_USER);
    if (wcscmp(argv[1], L"--disposable-account-admission-probe") != 0) return 2;
    return run_probe(FRESH_CREDENTIALED_ACCOUNT);
}
