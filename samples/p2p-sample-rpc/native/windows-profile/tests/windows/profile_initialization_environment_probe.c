/* Test-only environmental bootstrap, NOT the protected-payload supervisor.
 * No documented/qualified WithLogonW JOB_LIST path is used. This has a suspended post-creation
 * admission interval; no profile DLL/JNI/storage may execute through this path.
 * Once admitted it runs only the fixed OS-known-folder/NTFS environment probe.
 * Never use this as a fallback for failed AsUserW or standard-user admission. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
/* Diagnostic interposition observes unchanged API results; it cannot turn a failure into success.
 * Separate processes have separate counters. Only fixed numeric cleanup categories are returned. */
static DWORD observed_active = MAXDWORD, observed_first_active = MAXDWORD, observed_queries = 0;
static DWORD observed_query_error = 0, observed_close_error = 0;
static BOOL WINAPI observe_job(HANDLE job, JOBOBJECTINFOCLASS kind, LPVOID information, DWORD size, LPDWORD used) {
    BOOL okay = QueryInformationJobObject(job, kind, information, size, used);
    DWORD error = GetLastError();
    if (kind == JobObjectBasicAccountingInformation) {
        if (!okay) observed_query_error = error;
        else if (size >= sizeof(JOBOBJECT_BASIC_ACCOUNTING_INFORMATION)) {
            observed_active = ((JOBOBJECT_BASIC_ACCOUNTING_INFORMATION *)information)->ActiveProcesses;
            if (observed_first_active == MAXDWORD) observed_first_active = observed_active;
            ++observed_queries;
        }
    }
    SetLastError(error);
    return okay;
}
static BOOL WINAPI observe_close(HANDLE handle) {
    BOOL okay = CloseHandle(handle); DWORD error = GetLastError();
    if (!okay) observed_close_error = error;
    SetLastError(error);
    return okay;
}
#define QueryInformationJobObject observe_job
#define CloseHandle observe_close
#define wmain p2pkit_original_account_probe_main
#include "profile_account_probe.c"
#undef wmain
#include <userenv.h>
#include <shlobj.h>
#include <sddl.h>
#include "profile_hive_exact_observer.h"

/* Environment observation only, NOT protected root/ancestor/ACL custody. Never emit paths/SIDs.
 * Both known folders must already exist: no KF_FLAG_CREATE, synthetic environment or ACL repair. */
static int observed_folder(const WCHAR *path) {
    WCHAR volume[32768] = {0}, filesystem[32] = {0};
    owned_handle folder = {0}; FILE_ATTRIBUTE_TAG_INFO info = {0}; int okay = 0;
    if (!path || wcsnlen(path, 32768) >= 32768 ||
        !GetVolumePathNameW(path, volume, 32768) || GetDriveTypeW(volume) != DRIVE_FIXED) goto done;
    folder.value = CreateFileW(path, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (folder.value == INVALID_HANDLE_VALUE) { folder.value = NULL; goto done; }
    if (!GetFileInformationByHandleEx(folder.value, FileAttributeTagInfo, &info, sizeof(info)) ||
        !(info.FileAttributes & FILE_ATTRIBUTE_DIRECTORY) || (info.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) ||
        !GetVolumeInformationByHandleW(folder.value, NULL, 0, NULL, NULL, NULL, filesystem, 32) ||
        wcscmp(filesystem, L"NTFS") != 0) goto done;
    okay = 1;
done:
    if (!close_once(&folder)) okay = 0;
    SecureZeroMemory(volume, sizeof(volume)); SecureZeroMemory(filesystem, sizeof(filesystem));
    return okay;
}
static int profile_child(void) {
    int admission = child();
    if (admission != CHILD_EXIT) return admission;
    owned_handle token = {0}; WCHAR profile[32768] = {0}; DWORD length = 32768;
    PWSTR known_profile = NULL, local = NULL; int code = 20;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token.value)) goto done;
    code = 21;
    if (!GetUserProfileDirectoryW(token.value, profile, &length) || length > 32768 || !profile[0]) goto done;
    code = 22;
    if (SHGetKnownFolderPath(&FOLDERID_Profile, KF_FLAG_DEFAULT, NULL, &known_profile) != S_OK) goto done;
    code = 23;
    if (SHGetKnownFolderPath(&FOLDERID_LocalAppData, KF_FLAG_DEFAULT, NULL, &local) != S_OK) goto done;
    code = 24;
    size_t prefix = wcsnlen(profile, 32768), local_size = local ? wcsnlen(local, 32768) : 0;
    if (!known_profile || _wcsicmp(profile, known_profile) != 0 || !prefix || prefix >= 32768 ||
        local_size <= prefix + 1 || local_size >= 32768 || _wcsnicmp(profile, local, prefix) ||
        local[prefix] != L'\\') goto done;
    code = 25;
    if (!observed_folder(profile) || !observed_folder(local)) goto done;
    code = 0;
done:
    if (known_profile) { SecureZeroMemory(known_profile, wcslen(known_profile) * sizeof(WCHAR)); CoTaskMemFree(known_profile); }
    if (local) { SecureZeroMemory(local, wcslen(local) * sizeof(WCHAR)); CoTaskMemFree(local); }
    if (!close_once(&token)) code = 8;
    SecureZeroMemory(profile, sizeof(profile));
    return code;
}
/* Exact relative SID-name observation only, not all profile resources or registry stability.
 * The owner remains live across before/loaded/after checks and is retired on every done path. */
static DWORD hive_original_remaining(void *context) {
    return remaining((const watchdog *)context);
}

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
    LPWSTR sid_text = NULL;
    p2pkit_hive_exact_observation hive_exact = {0};
    DWORD hive_before_status = MAXDWORD, hive_loaded_status = MAXDWORD, hive_after_status = MAXDWORD;
    int hive_absent_before = 0, hive_loaded = 0, hive_absent_after = 0;
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
    if (!ConvertSidToStringSidW(expected, &sid_text) ||
        !p2pkit_hive_exact_open(sid_text, hive_original_remaining, &watch, &hive_exact)) goto done;
    int before = p2pkit_hive_exact_query(&hive_exact, hive_original_remaining, &watch);
    hive_before_status = hive_exact.last_lookup_status;
    if (before != P2PKIT_HIVE_EXACT_ABSENT) goto done;
    hive_absent_before = 1;
    DWORD length = GetModuleFileNameW(NULL, executable, 32768);
    UINT system_length = GetSystemWindowsDirectoryW(system, 32768);
    if (!length || length > 900 || wcschr(executable, L'"') || !system_length || system_length >= 32768 ||
        swprintf_s(command, 1024, L"\"%ls\" --profile-known-folder-child", executable) <= 0) goto done;
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
    /* Explicit OS-profile experiment, never a protected payload supervisor. No privilege grants,
     * inherited/caller-created profile paths, shell, P2pKit storage, or policy changes.
     * The bootstrap is NOT atomically assigned at creation, hence cannot qualify protected smoke. */
    if (!CreateProcessWithLogonW(name, L".", password, LOGON_WITH_PROFILE, executable, command,
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
    int loaded = p2pkit_hive_exact_query(&hive_exact, hive_original_remaining, &watch);
    hive_loaded_status = hive_exact.last_lookup_status;
    if (loaded != P2PKIT_HIVE_EXACT_PRESENT) goto done;
    hive_loaded = 1;
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
    /* ActiveProcesses is decremented after exit AND release of all process references.
     * Observe the exact original process first, then detach/close our child references once,
     * before asking the still-owned job for empty membership. A failed close stays fatal. */
    if (!close_once(&child_token)) cleanup = 0;
    if (!close_once(&thread)) cleanup = 0;
    if (!close_once(&process)) cleanup = 0;
    if (job.value && !await_empty_job(job.value, &watch)) cleanup = 0;
    if (account_created) {
        USER_INFO_1008 disabled = {UF_SCRIPT | UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE};
        if (NetUserSetInfo(NULL, name, 1008, (LPBYTE)&disabled, &parameter) != NERR_Success) cleanup = 0;
        /* Disabled fixture account retained until GitHub destroys this disposable VM. */
    }
    if (!close_once(&impersonation)) cleanup = 0;
    if (!close_once(&controller)) cleanup = 0;
    if (!close_once(&token)) cleanup = 0;
    if (created && sid_text && hive_absent_before) {
        hive_absent_after = p2pkit_hive_exact_await_absent(&hive_exact, hive_original_remaining, &watch);
        hive_after_status = hive_exact.last_lookup_status;
        if (!hive_absent_after) cleanup = 0;
    }
    if (!p2pkit_hive_exact_retire(&hive_exact, hive_original_remaining, &watch)) cleanup = 0;
    if (sid_text) {
        SecureZeroMemory(sid_text, wcslen(sid_text) * sizeof(WCHAR));
        if (LocalFree(sid_text) != NULL) cleanup = 0;
        sid_text = NULL;
    }
    if (!close_once(&job)) cleanup = 0;
    SecureZeroMemory(name, sizeof(name)); SecureZeroMemory(expected, sizeof(expected));
    SecureZeroMemory(actual, sizeof(actual));
    if (!finish_watchdog(&watch)) cleanup = 0;
    (void)remaining(&watch);
    if (!cleanup) result = 8;
    printf("{\"scope\":\"OS_PROFILE_INITIALIZATION_NOT_PROTECTED_STORAGE_OR_SUPERVISION\","
        "\"launchApi\":\"CreateProcessWithLogonW\",\"result\":%d,\"stage\":%lu,\"systemCode\":%lu,"
        "\"accountCreated\":%s,\"created\":%s,\"assignedBeforeResume\":%s,\"resumed\":%s,"
        "\"profileProbeExit\":%lu,\"cleanupObserved\":%s,\"bootstrapAtomicJobAdmission\":false,"
        "\"profileRequested\":true,\"nativeStorageExecuted\":false,"
        "\"finalJobActiveProcesses\":%lu,\"jobQueryError\":%lu,\"handleCloseError\":%lu,"
        "\"firstJobActiveProcesses\":%lu,\"jobObservations\":%lu,"
        "\"hiveObserverMethod\":\"EXACT_RELATIVE_SID_LOOKUP_POINT_IN_TIME\","
        "\"hiveAbsentBefore\":%s,\"hiveLoadedBeforeResume\":%s,\"hiveAbsentAfterExit\":%s,"
        "\"hiveObserverRetired\":%s,\"hiveBeforeStatus\":%lu,\"hiveLoadedStatus\":%lu,"
        "\"hiveAfterStatus\":%lu,\"hiveParentOpenStatus\":%lu,\"hiveLastLookupStatus\":%lu,"
        "\"hiveParentCloseStatus\":%lu,\"hiveChildCloseStatus\":%lu,\"hiveObserverSystemError\":%lu,"
        "\"hiveLookups\":%lu,\"hivePresences\":%lu,\"hiveAbsences\":%lu,\"hiveChildCloses\":%lu}\n", result,
        (unsigned long)stage, (unsigned long)error, account_created ? "true" : "false", created ? "true" : "false",
        assigned ? "true" : "false", resumed ? "true" : "false", (unsigned long)child_exit,
        cleanup ? "true" : "false", (unsigned long)observed_active, (unsigned long)observed_query_error,
        (unsigned long)observed_close_error, (unsigned long)observed_first_active, (unsigned long)observed_queries,
        hive_absent_before ? "true" : "false", hive_loaded ? "true" : "false", hive_absent_after ? "true" : "false",
        hive_exact.retired ? "true" : "false", (unsigned long)hive_before_status, (unsigned long)hive_loaded_status,
        (unsigned long)hive_after_status, (unsigned long)hive_exact.parent_open_status,
        (unsigned long)hive_exact.last_lookup_status, (unsigned long)hive_exact.parent_close_status,
        (unsigned long)hive_exact.child_close_status, (unsigned long)hive_exact.system_error,
        (unsigned long)hive_exact.lookups, (unsigned long)hive_exact.presences, (unsigned long)hive_exact.absences,
        (unsigned long)hive_exact.child_closes);
    return result;
}
int wmain(int argc, WCHAR **argv) {
    if (argc != 2) return 2;
    if (wcscmp(argv[1], L"--profile-known-folder-child") == 0) return profile_child();
    if (wcscmp(argv[1], L"--disposable-os-profile-probe") != 0) return 2;
    return bootstrap();
}
