/* Test-only WithLogonW job-INHERITANCE experiment; NO protected payload or alternate launch fallback.
 * A parent atomically job-binds a same-token broker; that broker creates a suspended standard user
 * using the unchanged successful WithLogonW API flags. Parent tests exact-child membership before
 * any resume. There is NO AssignProcessToJobObject, breakaway or debugger operation in this source.
 * Docs describe job association during child creation, but do not establish WithLogonW's secondary
 * logon service boundary. Actual positive membership/death evidence is required; absence fails closed.
 * https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
 * https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs
 * This is NOT the Foundation supervisor and cannot qualify protected-profile/JNI/application lifetime. */
#define wmain p2pkit_original_account_probe_main
#include "profile_account_probe.c"
#undef wmain
#include <stdint.h>
#include <stdlib.h>

#define NOTE_MAGIC 0x50495731u
enum { NOTE_ACCOUNT = 1, NOTE_CHILD = 2, NOTE_FINAL = 3 };
enum { INHERIT_NORMAL = 0, INHERIT_OWNER_CLOSE = 1 };
typedef struct {
    DWORD magic, kind, stage, error;
    int result;
    uintptr_t handle;
    WCHAR account[20];
} inheritance_note;

static int write_note(HANDLE pipe, inheritance_note *note) {
    DWORD written = 0; note->magic = NOTE_MAGIC;
    return WriteFile(pipe, note, sizeof(*note), &written, NULL) && written == sizeof(*note);
}
static int read_note(HANDLE pipe, inheritance_note *note) {
    DWORD read = 0; memset(note, 0, sizeof(*note));
    return ReadFile(pipe, note, sizeof(*note), &read, NULL) && read == sizeof(*note) &&
        note->magic == NOTE_MAGIC && note->kind >= NOTE_ACCOUNT && note->kind <= NOTE_FINAL;
}
static int fresh_account_name(const WCHAR name[20]) {
    if (wcsncmp(name, L"p2ppr", 5) || name[19]) return 0;
    for (size_t i = 5; i < 19; ++i)
        if (!((name[i] >= L'0' && name[i] <= L'9') || (name[i] >= L'a' && name[i] <= L'f'))) return 0;
    return 1;
}
static int elevated_controller(void) {
    owned_handle token = {0}, thread = {0}; TOKEN_ELEVATION elevation = {0}; DWORD size = 0;
    int okay = 0;
    if (!native_x64() || OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, TRUE, &thread.value) ||
        GetLastError() != ERROR_NO_TOKEN ||
        !OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token.value) ||
        !GetTokenInformation(token.value, TokenElevation, &elevation, sizeof(elevation), &size) ||
        size != sizeof(elevation) || !elevation.TokenIsElevated) goto done;
    okay = 1;
done:
    if (!close_once(&thread)) okay = 0;
    if (!close_once(&token)) okay = 0;
    return okay;
}
static int kill_job(owned_handle *job) {
    job->value = CreateJobObjectW(NULL, NULL);
    if (!job->value) return 0;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    return SetInformationJobObject(job->value, JobObjectExtendedLimitInformation, &limits, sizeof(limits)) != 0;
}
static int verified_member(HANDLE process, HANDLE job) {
    BOOL member = FALSE;
    return IsProcessInJob(process, job, &member) && member;
}

/* Failure-only bounded observations of the ORIGINAL job, never a process-name/PID sweep.
 * No path, SID, user name, registry value or other payload is emitted. These observations do not
 * admit extra members or relax the unchanged exact-two control below. */
static BOOL pre_close_query_succeeded = FALSE, pre_close_list_succeeded = FALSE;
static DWORD pre_close_active = MAXDWORD, pre_close_query_error = 0, pre_close_inventory_error = 0;
static DWORD pre_close_assigned = 0, pre_close_listed = 0, pre_close_brokers = 0, pre_close_children = 0;
static DWORD pre_close_consoles = 0, pre_close_other = 0, pre_close_retired = 0, pre_close_identities = 0;
static int diagnose_job(HANDLE job, HANDLE broker, HANDLE child_process) {
    enum { INVENTORY_LIMIT = 16 };
    _Alignas(ULONG_PTR) unsigned char bytes[sizeof(JOBOBJECT_BASIC_PROCESS_ID_LIST) +
        sizeof(ULONG_PTR) * (INVENTORY_LIMIT - 1)] = {0};
    JOBOBJECT_BASIC_PROCESS_ID_LIST *list = (JOBOBJECT_BASIC_PROCESS_ID_LIST *)bytes;
    pre_close_list_succeeded = QueryInformationJobObject(job, JobObjectBasicProcessIdList,
        bytes, sizeof(bytes), NULL);
    pre_close_assigned = list->NumberOfAssignedProcesses;
    pre_close_listed = list->NumberOfProcessIdsInList;
    if (!pre_close_list_succeeded) { pre_close_inventory_error = GetLastError(); return 1; }
    if (pre_close_listed > INVENTORY_LIMIT || pre_close_assigned > INVENTORY_LIMIT ||
        pre_close_listed != pre_close_assigned) { pre_close_inventory_error = ERROR_INVALID_DATA; return 1; }
    int cleanup = 1;
    DWORD broker_id = GetProcessId(broker), child_id = GetProcessId(child_process);
    for (DWORD i = 0; i < pre_close_listed; ++i) {
        owned_handle original = {0}; BOOL member = FALSE;
        FILETIME created = {0}, exited = {0}, kernel = {0}, user = {0};
        if (list->ProcessIdList[i] == 0 || list->ProcessIdList[i] > MAXDWORD) {
            pre_close_inventory_error = ERROR_INVALID_DATA; break;
        }
        DWORD pid = (DWORD)list->ProcessIdList[i];
        original.value = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, FALSE, pid);
        if (!original.value) { pre_close_inventory_error = GetLastError(); break; }
        if (!IsProcessInJob(original.value, job, &member) || !member || GetProcessId(original.value) != pid ||
            !GetProcessTimes(original.value, &created, &exited, &kernel, &user) ||
            (!created.dwLowDateTime && !created.dwHighDateTime)) {
            pre_close_inventory_error = ERROR_INVALID_DATA;
        } else {
            ++pre_close_identities;
            DWORD waited = WaitForSingleObject(original.value, 0);
            if (waited == WAIT_OBJECT_0) ++pre_close_retired;
            else if (waited != WAIT_TIMEOUT) pre_close_inventory_error = GetLastError();
            if (pid == broker_id) ++pre_close_brokers;
            else if (pid == child_id) ++pre_close_children;
            else {
                WCHAR path[32768] = {0}, system[32768] = {0}; DWORD size = 32768;
                UINT prefix = GetSystemDirectoryW(system, 32768);
                if (prefix && prefix < 32768 && QueryFullProcessImageNameW(original.value, 0, path, &size) &&
                    size > prefix && _wcsnicmp(path, system, prefix) == 0 &&
                    (_wcsicmp(path + prefix, L"\\conhost.exe") == 0 ||
                     _wcsicmp(path + prefix, L"\\OpenConsole.exe") == 0)) ++pre_close_consoles;
                else ++pre_close_other;
                SecureZeroMemory(path, sizeof(path)); SecureZeroMemory(system, sizeof(system));
            }
        }
        if (!close_once(&original)) { cleanup = 0; pre_close_inventory_error = ERROR_INVALID_HANDLE; }
        if (pre_close_inventory_error) break;
    }
    SecureZeroMemory(bytes, sizeof(bytes));
    return cleanup;
}

static int inheritance_broker(int mode, HANDLE controller, HANDLE pipe, HANDLE gate) {
    watchdog watch; if (!elevated_controller() || !start_watchdog(&watch)) return 3;
    WCHAR name[20] = {0}, password[69] = {0}, executable[32768] = {0}, command[1024] = {0};
    WCHAR system[32768] = {0}, environment[65560] = {0};
    _Alignas(void *) unsigned char expected[SECURITY_MAX_SID_SIZE] = {0};
    _Alignas(void *) unsigned char actual[SECURITY_MAX_SID_SIZE] = {0};
    owned_handle token = {0}, child_token = {0}, process = {0}, thread = {0};
    DWORD stage = 1, error = 0, parameter = 0; int result = 5, cleanup = 1;
    inheritance_note note = {0};
    if (!credentials(name, password)) goto done;
    USER_INFO_1 account = {0}; account.usri1_name = name; account.usri1_password = password;
    account.usri1_priv = USER_PRIV_USER; account.usri1_flags = UF_SCRIPT | UF_NORMAL_ACCOUNT;
    error = NetUserAdd(NULL, 1, (LPBYTE)&account, &parameter);
    if (error != NERR_Success) goto done; /* Refuse collisions, never adopt/reset an existing account. */
    note.kind = NOTE_ACCOUNT; memcpy(note.account, name, sizeof(name));
    if (!write_note(pipe, &note)) goto done;
    stage = 2; error = ordinary_group(name);
    if (error != NERR_Success) goto done;
    if (!LogonUserW(name, L".", password, LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT, &token.value)) {
        error = GetLastError(); goto done;
    }
    if (!standard_token(token.value) || !token_sid(token.value, expected)) goto done;
    stage = 3;
    DWORD length = GetModuleFileNameW(NULL, executable, 32768);
    UINT system_length = GetSystemWindowsDirectoryW(system, 32768);
    if (!length || length > 900 || wcschr(executable, L'"') || !system_length || system_length >= 32768 ||
        swprintf_s(command, 1024, L"\"%ls\" --standard-account-probe-child", executable) <= 0) goto done;
    int count = swprintf_s(environment, 65560, L"SystemRoot=%ls", system);
    if (count <= 0) goto done;
    int second = swprintf_s(environment + count + 1, 65560 - (size_t)count - 1, L"WINDIR=%ls", system);
    if (second <= 0) goto done;
    environment[(size_t)count + 1 + (size_t)second + 1] = 0;
    STARTUPINFOW startup = {0}; PROCESS_INFORMATION pi = {0}; startup.cb = sizeof(startup);
    stage = 4; (void)remaining(&watch);
    /* This is a separately selected inheritance observation, NOT a retry/fallback for failed
     * debugger admission. No post-creation job assignment is performed anywhere in this program. */
    if (!CreateProcessWithLogonW(name, L".", password, 0, executable, command,
        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW,
        environment, system, &startup, &pi)) { error = GetLastError(); goto done; }
    process.value = pi.hProcess; thread.value = pi.hThread;
    SecureZeroMemory(password, sizeof(password)); stage = 5;
    if (!OpenProcessToken(process.value, TOKEN_QUERY, &child_token.value) ||
        !standard_token(child_token.value) || !token_sid(child_token.value, actual) ||
        !EqualSid(expected, actual)) { error = GetLastError(); goto done; }
    stage = 8;
    HANDLE borrowed = NULL;
    if (!DuplicateHandle(GetCurrentProcess(), process.value, controller, &borrowed,
        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE | SYNCHRONIZE, FALSE, 0)) {
        error = GetLastError(); goto done;
    }
    memset(&note, 0, sizeof(note)); note.kind = NOTE_CHILD; note.handle = (uintptr_t)borrowed;
    if (!write_note(pipe, &note)) goto done;
    /* Controller observes the exact child handle before selecting normal continuation or terminating
     * this broker. Fault controls remain suspended; they can never run candidate code. */
    if (WaitForSingleObject(gate, remaining(&watch)) != WAIT_OBJECT_0) goto done;
    if (mode != INHERIT_NORMAL) goto done;
    stage = 9;
    if (ResumeThread(thread.value) != 1 || WaitForSingleObject(process.value, remaining(&watch)) != WAIT_OBJECT_0) {
        error = GetLastError(); goto done;
    }
    DWORD exit_code = STILL_ACTIVE;
    if (!GetExitCodeProcess(process.value, &exit_code) || exit_code != CHILD_EXIT) { error = exit_code; goto done; }
    result = 0; stage = 10;
done:
    SecureZeroMemory(password, sizeof(password));
    if (process.value && WaitForSingleObject(process.value, 0) != WAIT_OBJECT_0) {
        if (!TerminateProcess(process.value, 125)) cleanup = 0;
        if (WaitForSingleObject(process.value, remaining(&watch)) != WAIT_OBJECT_0) cleanup = 0;
    }
    if (!close_once(&child_token)) cleanup = 0;
    if (!close_once(&thread)) cleanup = 0;
    if (!close_once(&process)) cleanup = 0;
    if (!close_once(&token)) cleanup = 0;
    SecureZeroMemory(name, sizeof(name)); SecureZeroMemory(expected, sizeof(expected));
    SecureZeroMemory(actual, sizeof(actual));
    if (!finish_watchdog(&watch)) cleanup = 0;
    if (!cleanup) result = 8;
    memset(&note, 0, sizeof(note)); note.kind = NOTE_FINAL; note.result = result; note.stage = stage; note.error = error;
    if (!write_note(pipe, &note)) return 8;
    return result;
}

static int inheritance_controller(int mode) {
    watchdog watch; if (!elevated_controller() || !start_watchdog(&watch)) return 3;
    owned_handle job = {0}, pipe_read = {0}, pipe_write = {0}, self = {0}, gate = {0};
    owned_handle process = {0}, thread = {0}, child_process = {0};
    LPPROC_THREAD_ATTRIBUTE_LIST attributes = NULL; int initialized = 0, cleanup = 1, result = 5;
    int account_created = 0, child_observed = 0, fault_injected = 0, child_exit_observed = 0;
    int inherited_member = 0, exact_two_before_close = 0, empty_job_observed = 0;
    DWORD stage = 1, error = 0, parameter = 0, broker_exit = STILL_ACTIVE, child_exit = STILL_ACTIVE;
    WCHAR executable[32768] = {0}, command[2048] = {0}, system[32768] = {0}, environment[65560] = {0};
    WCHAR account[20] = {0}; inheritance_note note = {0}; SIZE_T attribute_size = 0;
    if (!kill_job(&job)) { error = GetLastError(); goto done; }
    SECURITY_ATTRIBUTES security = {sizeof(security), NULL, TRUE};
    if (!CreatePipe(&pipe_read.value, &pipe_write.value, &security, sizeof(inheritance_note) * 4) ||
        !SetHandleInformation(pipe_read.value, HANDLE_FLAG_INHERIT, 0) ||
        !DuplicateHandle(GetCurrentProcess(), GetCurrentProcess(), GetCurrentProcess(), &self.value,
            PROCESS_DUP_HANDLE | PROCESS_QUERY_LIMITED_INFORMATION, TRUE, 0)) { error = GetLastError(); goto done; }
    gate.value = CreateEventW(&security, TRUE, FALSE, NULL);
    if (!gate.value) { error = GetLastError(); goto done; }
    DWORD length = GetModuleFileNameW(NULL, executable, 32768);
    UINT system_length = GetSystemWindowsDirectoryW(system, 32768);
    if (!length || length > 900 || wcschr(executable, L'"') || !system_length || system_length >= 32768 ||
        swprintf_s(command, 2048, L"\"%ls\" --inheritance-broker %d %llu %llu %llu", executable, mode,
            (unsigned long long)(uintptr_t)self.value, (unsigned long long)(uintptr_t)pipe_write.value,
            (unsigned long long)(uintptr_t)gate.value) <= 0) goto done;
    int count = swprintf_s(environment, 65560, L"SystemRoot=%ls", system);
    if (count <= 0) goto done;
    int second = swprintf_s(environment + count + 1, 65560 - (size_t)count - 1, L"WINDIR=%ls", system);
    if (second <= 0) goto done;
    environment[(size_t)count + 1 + (size_t)second + 1] = 0;
    (void)InitializeProcThreadAttributeList(NULL, 2, 0, &attribute_size);
    if (!attribute_size || attribute_size > 1024 * 1024) goto done;
    attributes = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, attribute_size);
    if (!attributes) goto done;
    if (!InitializeProcThreadAttributeList(attributes, 2, 0, &attribute_size)) { error = GetLastError(); goto done; }
    initialized = 1;
    HANDLE jobs[] = {job.value}, handles[] = {self.value, pipe_write.value, gate.value};
    if (!UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST, jobs, sizeof(jobs), NULL, NULL) ||
        !UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
            handles, sizeof(handles), NULL, NULL)) { error = GetLastError(); goto done; }
    STARTUPINFOEXW startup = {0}; PROCESS_INFORMATION pi = {0};
    startup.StartupInfo.cb = sizeof(startup); startup.lpAttributeList = attributes; stage = 2;
    if (!CreateProcessW(executable, command, NULL, NULL, TRUE,
        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW,
        environment, system, &startup.StartupInfo, &pi)) { error = GetLastError(); goto done; }
    process.value = pi.hProcess; thread.value = pi.hThread;
    if (!verified_member(process.value, job.value) || ResumeThread(thread.value) != 1) {
        error = GetLastError(); goto done;
    }
    if (!close_once(&pipe_write)) goto done; /* EOF remains observable after broker death. */
    stage = 3;
    if (!read_note(pipe_read.value, &note)) goto done;
    if (note.kind == NOTE_FINAL) { stage = note.stage; error = note.error; goto done; }
    if (note.kind != NOTE_ACCOUNT || !fresh_account_name(note.account)) goto done;
    account_created = 1; memcpy(account, note.account, sizeof(account));
    if (!read_note(pipe_read.value, &note)) goto done;
    if (note.kind == NOTE_FINAL) { stage = note.stage; error = note.error; goto done; }
    if (note.kind != NOTE_CHILD || !note.handle || note.handle == (uintptr_t)INVALID_HANDLE_VALUE) goto done;
    child_process.value = (HANDLE)note.handle; child_observed = 1; stage = 4;
    if (!GetProcessId(child_process.value) || WaitForSingleObject(child_process.value, 0) != WAIT_TIMEOUT) goto done;
    /* Only this parent owns the job handle. It was never inherited or named, so membership here
     * can only originate in the OS creation path, never this program's post-create assignment. */
    BOOL member = FALSE;
    if (!IsProcessInJob(child_process.value, job.value, &member)) { error = GetLastError(); goto done; }
    inherited_member = member != FALSE;
    if (!inherited_member) goto done;
    if (mode == INHERIT_NORMAL) {
        if (!SetEvent(gate.value)) { error = GetLastError(); goto done; }
    } else {
        /* Both known processes are stopped at a fixed gate; neither can create descendants here.
         * Count before the last handle closes; never claim a post-close job query was performed. */
        JOBOBJECT_BASIC_ACCOUNTING_INFORMATION accounting = {0};
        pre_close_query_succeeded = QueryInformationJobObject(job.value, JobObjectBasicAccountingInformation,
            &accounting, sizeof(accounting), NULL);
        pre_close_query_error = pre_close_query_succeeded ? 0 : GetLastError();
        pre_close_active = pre_close_query_succeeded ? accounting.ActiveProcesses : MAXDWORD;
        if (!pre_close_query_succeeded || accounting.ActiveProcesses != 2) {
            if (!diagnose_job(job.value, process.value, child_process.value)) cleanup = 0;
            goto done;
        }
        exact_two_before_close = 1;
        if (!close_once(&job)) goto done;
        fault_injected = 1;
    }
    if (WaitForSingleObject(child_process.value, remaining(&watch)) != WAIT_OBJECT_0 ||
        !GetExitCodeProcess(child_process.value, &child_exit)) { error = GetLastError(); goto done; }
    child_exit_observed = 1;
    if ((mode == INHERIT_NORMAL && child_exit != CHILD_EXIT) ||
        (mode != INHERIT_NORMAL && (child_exit == CHILD_EXIT || child_exit == STILL_ACTIVE))) goto done;
    if (!close_once(&child_process)) goto done;
    stage = 5;
    if (WaitForSingleObject(process.value, remaining(&watch)) != WAIT_OBJECT_0 ||
        !GetExitCodeProcess(process.value, &broker_exit)) { error = GetLastError(); goto done; }
    if (mode == INHERIT_NORMAL) {
        if (!read_note(pipe_read.value, &note) || note.kind != NOTE_FINAL || note.result ||
            note.stage != 10 || note.error || broker_exit) {
            stage = note.stage; error = note.error; goto done;
        }
    } else if (broker_exit == STILL_ACTIVE) goto done;
    result = 0; stage = 6;
done:
    /* Error cleanup is not an observation of automatic retirement. It cannot convert failure to pass. */
    if (child_process.value && WaitForSingleObject(child_process.value, 0) != WAIT_OBJECT_0) {
        if (!TerminateProcess(child_process.value, 125)) cleanup = 0;
        if (WaitForSingleObject(child_process.value, remaining(&watch)) != WAIT_OBJECT_0) cleanup = 0;
    }
    if (process.value && WaitForSingleObject(process.value, 0) != WAIT_OBJECT_0) {
        if (!TerminateProcess(process.value, 125)) cleanup = 0;
        if (WaitForSingleObject(process.value, remaining(&watch)) != WAIT_OBJECT_0) cleanup = 0;
    }
    if (!close_once(&child_process)) cleanup = 0;
    if (!close_once(&thread)) cleanup = 0;
    if (!close_once(&process)) cleanup = 0;
    if (job.value) {
        empty_job_observed = await_empty_job(job.value, &watch);
        if (!empty_job_observed) cleanup = 0;
    }
    if (account_created) {
        USER_INFO_1008 disabled = {UF_SCRIPT | UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE};
        if (NetUserSetInfo(NULL, account, 1008, (LPBYTE)&disabled, &parameter) != NERR_Success) cleanup = 0;
    }
    if (!close_once(&pipe_write)) cleanup = 0;
    if (!close_once(&pipe_read)) cleanup = 0;
    if (!close_once(&gate)) cleanup = 0;
    if (!close_once(&self)) cleanup = 0;
    if (!close_once(&job)) cleanup = 0;
    if (initialized) DeleteProcThreadAttributeList(attributes);
    if (attributes && !HeapFree(GetProcessHeap(), 0, attributes)) cleanup = 0;
    SecureZeroMemory(account, sizeof(account)); SecureZeroMemory(&note, sizeof(note));
    if (!finish_watchdog(&watch)) cleanup = 0;
    if (!cleanup) result = 8;
    printf("{\"scope\":\"LOGON_JOB_INHERITANCE_EXPERIMENT_NOT_PROTECTED_SUPERVISION\","
        "\"mode\":%d,\"result\":%d,\"stage\":%lu,\"systemCode\":%lu,\"accountCreated\":%s,"
        "\"childObserved\":%s,\"inheritedMember\":%s,\"lastJobHandleClosed\":%s,"
        "\"exactTwoBeforeClose\":%s,\"childExitObserved\":%s,\"childExit\":%lu,\"brokerExit\":%lu,"
        "\"emptyJobObserved\":%s,\"cleanupObserved\":%s,\"profileRequested\":false,\"nativeStorageExecuted\":false,"
        "\"preCloseQuerySucceeded\":%s,\"preCloseActiveProcesses\":%lu,\"preCloseQueryError\":%lu,"
        "\"preCloseListSucceeded\":%s,\"preCloseAssignedCount\":%lu,\"preCloseListedCount\":%lu,"
        "\"preCloseInventoryError\":%lu,\"preCloseBrokerCount\":%lu,\"preCloseChildCount\":%lu,"
        "\"preCloseConsoleCount\":%lu,\"preCloseOtherCount\":%lu,\"preCloseRetiredCount\":%lu,"
        "\"preCloseIdentityCheckedCount\":%lu}\n",
        mode, result, (unsigned long)stage, (unsigned long)error, account_created ? "true" : "false",
        child_observed ? "true" : "false", inherited_member ? "true" : "false", fault_injected ? "true" : "false",
        exact_two_before_close ? "true" : "false", child_exit_observed ? "true" : "false",
        (unsigned long)child_exit, (unsigned long)broker_exit, empty_job_observed ? "true" : "false",
        cleanup ? "true" : "false", pre_close_query_succeeded ? "true" : "false",
        (unsigned long)pre_close_active, (unsigned long)pre_close_query_error,
        pre_close_list_succeeded ? "true" : "false", (unsigned long)pre_close_assigned,
        (unsigned long)pre_close_listed, (unsigned long)pre_close_inventory_error, (unsigned long)pre_close_brokers,
        (unsigned long)pre_close_children, (unsigned long)pre_close_consoles, (unsigned long)pre_close_other,
        (unsigned long)pre_close_retired, (unsigned long)pre_close_identities);
    return result;
}
static HANDLE parse_handle(const WCHAR *text) {
    if (!text || !*text) return NULL;
    for (const WCHAR *p = text; *p; ++p) if (*p < L'0' || *p > L'9') return NULL;
    WCHAR *end = NULL; unsigned long long number = _wcstoui64(text, &end, 10);
    if (!end || *end || !number || number >= UINTPTR_MAX) return NULL;
    HANDLE handle = (HANDLE)(uintptr_t)number; DWORD flags = 0;
    return GetHandleInformation(handle, &flags) && (flags & HANDLE_FLAG_INHERIT) ? handle : NULL;
}
int wmain(int argc, WCHAR **argv) {
    if (argc == 6 && wcscmp(argv[1], L"--inheritance-broker") == 0 &&
        wcslen(argv[2]) == 1 && argv[2][0] >= L'0' && argv[2][0] <= L'1') {
        HANDLE controller = parse_handle(argv[3]), pipe = parse_handle(argv[4]), gate = parse_handle(argv[5]);
        if (!controller || !pipe || !gate || !GetProcessId(controller) || GetProcessId(controller) == GetCurrentProcessId())
            return 2;
        return inheritance_broker(argv[2][0] - L'0', controller, pipe, gate);
    }
    if (argc != 2) return 2;
    if (wcscmp(argv[1], L"--standard-account-probe-child") == 0) return child();
    if (wcscmp(argv[1], L"--disposable-inheritance-normal-probe") == 0) return inheritance_controller(INHERIT_NORMAL);
    if (wcscmp(argv[1], L"--disposable-inheritance-owner-close-probe") == 0)
        return inheritance_controller(INHERIT_OWNER_CLOSE);
    return 2;
}
