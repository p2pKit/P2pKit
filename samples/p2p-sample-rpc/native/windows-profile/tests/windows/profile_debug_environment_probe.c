/* Test-only debugger-custody experiment. No profile, DLL, JNI or storage payload is linked.
 * The outer controller atomically owns its debugger broker in a kill-on-close job. WithLogonW
 * DEBUG_ONLY_THIS_PROCESS must establish debugger custody at creation: default debugger-thread
 * exit kills the debuggee. A child is never resumed until its independent kill-on-close job is
 * verified and debugging has detached. Actual broker-death controls test every transfer boundary.
 * Failure is terminal. No AsUser/WithToken fallback, added privileges, PID lookup or ACL repair.
 * This focused recipe is NOT a fork/replacement of the Foundation protected-process supervisor. */
#define wmain p2pkit_original_account_probe_main
#include "profile_account_probe.c"
#undef wmain
#include <stdint.h>
#include <stdlib.h>

#define NOTE_MAGIC 0x50445731u
enum { NOTE_ACCOUNT = 1, NOTE_CHILD = 2, NOTE_FINAL = 3 };
enum { TRANSFER_NORMAL = 0, DEATH_PRE_JOB = 1, DEATH_IN_JOB = 2, DEATH_DETACHED = 3 };
typedef struct {
    DWORD magic, kind, stage, error;
    int result;
    uintptr_t handle;
    WCHAR account[20];
} debug_note;

static int write_note(HANDLE pipe, debug_note *note) {
    DWORD written = 0; note->magic = NOTE_MAGIC;
    return WriteFile(pipe, note, sizeof(*note), &written, NULL) && written == sizeof(*note);
}
static int read_note(HANDLE pipe, debug_note *note) {
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

static int debug_broker(int mode, HANDLE controller, HANDLE pipe, HANDLE gate) {
    watchdog watch; if (!elevated_controller() || !start_watchdog(&watch)) return 3;
    WCHAR name[20] = {0}, password[69] = {0}, executable[32768] = {0}, command[1024] = {0};
    WCHAR system[32768] = {0}, environment[65560] = {0};
    _Alignas(void *) unsigned char expected[SECURITY_MAX_SID_SIZE] = {0};
    _Alignas(void *) unsigned char actual[SECURITY_MAX_SID_SIZE] = {0};
    owned_handle token = {0}, child_token = {0}, process = {0}, thread = {0}, job = {0};
    DWORD stage = 1, error = 0, parameter = 0; int result = 5, cleanup = 1, detached = 0;
    debug_note note = {0};
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
    if (!kill_job(&job)) { error = GetLastError(); goto done; }
    STARTUPINFOW startup = {0}; PROCESS_INFORMATION pi = {0}; startup.cb = sizeof(startup);
    stage = 4; (void)remaining(&watch);
    /* No LOGON_WITH_PROFILE or inherited caller environment. Default debugger kill-on-exit covers
     * creation to the explicit TRUE confirmation below. FALSE is never requested at any boundary. */
    if (!CreateProcessWithLogonW(name, L".", password, 0, executable, command,
        DEBUG_ONLY_THIS_PROCESS | CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW,
        environment, system, &startup, &pi)) { error = GetLastError(); goto done; }
    process.value = pi.hProcess; thread.value = pi.hThread;
    SecureZeroMemory(password, sizeof(password)); stage = 5;
    if (!DebugSetProcessKillOnExit(TRUE)) { error = GetLastError(); goto done; }
    BOOL debugger_attached = FALSE;
    if (!CheckRemoteDebuggerPresent(process.value, &debugger_attached) || !debugger_attached) {
        error = GetLastError(); goto done;
    }
    if (!OpenProcessToken(process.value, TOKEN_QUERY, &child_token.value) ||
        !standard_token(child_token.value) || !token_sid(child_token.value, actual) ||
        !EqualSid(expected, actual)) { error = GetLastError(); goto done; }
    if (mode != DEATH_PRE_JOB) {
        stage = 6;
        if (!AssignProcessToJobObject(job.value, process.value) || !verified_member(process.value, job.value)) {
            error = GetLastError(); goto done;
        }
        if (mode == DEATH_DETACHED || mode == TRANSFER_NORMAL) {
            stage = 7;
            /* Exact original process is still held and suspended, so the returned PID cannot be reused.
             * Detach only AFTER independently verified job custody, never disable kill-on-debugger-exit. */
            if (!DebugActiveProcessStop(pi.dwProcessId)) { error = GetLastError(); goto done; }
            if (!CheckRemoteDebuggerPresent(process.value, &debugger_attached) || debugger_attached) {
                error = GetLastError(); goto done;
            }
            detached = 1;
        }
    }
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
    if (mode != TRANSFER_NORMAL || !detached) goto done;
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
    /* Outer owns a borrowed process reference until it observes exit; outer releases it BEFORE
     * waiting for broker exit, allowing this exact job-empty accounting to converge. */
    if (job.value && !await_empty_job(job.value, &watch)) cleanup = 0;
    if (!close_once(&job)) cleanup = 0;
    if (!close_once(&token)) cleanup = 0;
    SecureZeroMemory(name, sizeof(name)); SecureZeroMemory(expected, sizeof(expected));
    SecureZeroMemory(actual, sizeof(actual));
    if (!finish_watchdog(&watch)) cleanup = 0;
    if (!cleanup) result = 8;
    memset(&note, 0, sizeof(note)); note.kind = NOTE_FINAL; note.result = result; note.stage = stage; note.error = error;
    if (!write_note(pipe, &note)) return 8;
    return result;
}

static int debug_controller(int mode) {
    watchdog watch; if (!elevated_controller() || !start_watchdog(&watch)) return 3;
    owned_handle job = {0}, pipe_read = {0}, pipe_write = {0}, self = {0}, gate = {0};
    owned_handle process = {0}, thread = {0}, child_process = {0};
    LPPROC_THREAD_ATTRIBUTE_LIST attributes = NULL; int initialized = 0, cleanup = 1, result = 5;
    int account_created = 0, child_observed = 0, fault_injected = 0, child_exit_observed = 0;
    DWORD stage = 1, error = 0, parameter = 0, broker_exit = STILL_ACTIVE, child_exit = STILL_ACTIVE;
    WCHAR executable[32768] = {0}, command[2048] = {0}, system[32768] = {0}, environment[65560] = {0};
    WCHAR account[20] = {0}; debug_note note = {0}; SIZE_T attribute_size = 0;
    if (!kill_job(&job)) { error = GetLastError(); goto done; }
    SECURITY_ATTRIBUTES security = {sizeof(security), NULL, TRUE};
    if (!CreatePipe(&pipe_read.value, &pipe_write.value, &security, sizeof(debug_note) * 4) ||
        !SetHandleInformation(pipe_read.value, HANDLE_FLAG_INHERIT, 0) ||
        !DuplicateHandle(GetCurrentProcess(), GetCurrentProcess(), GetCurrentProcess(), &self.value,
            PROCESS_DUP_HANDLE | PROCESS_QUERY_LIMITED_INFORMATION, TRUE, 0)) { error = GetLastError(); goto done; }
    gate.value = CreateEventW(&security, TRUE, FALSE, NULL);
    if (!gate.value) { error = GetLastError(); goto done; }
    DWORD length = GetModuleFileNameW(NULL, executable, 32768);
    UINT system_length = GetSystemWindowsDirectoryW(system, 32768);
    if (!length || length > 900 || wcschr(executable, L'"') || !system_length || system_length >= 32768 ||
        swprintf_s(command, 2048, L"\"%ls\" --debug-broker %d %llu %llu %llu", executable, mode,
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
    if (mode == TRANSFER_NORMAL) {
        if (!SetEvent(gate.value)) { error = GetLastError(); goto done; }
    } else {
        /* Terminate ONLY the original returned broker, never the standard-user child. Its automatic
         * debugger/job retirement is the property under test, observed via a borrowed exact handle. */
        if (!TerminateProcess(process.value, 125)) { error = GetLastError(); goto done; }
        fault_injected = 1;
    }
    if (WaitForSingleObject(child_process.value, remaining(&watch)) != WAIT_OBJECT_0 ||
        !GetExitCodeProcess(child_process.value, &child_exit)) { error = GetLastError(); goto done; }
    child_exit_observed = 1;
    if ((mode == TRANSFER_NORMAL && child_exit != CHILD_EXIT) ||
        (mode != TRANSFER_NORMAL && (child_exit == CHILD_EXIT || child_exit == STILL_ACTIVE))) goto done;
    if (!close_once(&child_process)) goto done;
    stage = 5;
    if (WaitForSingleObject(process.value, remaining(&watch)) != WAIT_OBJECT_0 ||
        !GetExitCodeProcess(process.value, &broker_exit)) { error = GetLastError(); goto done; }
    if (mode == TRANSFER_NORMAL) {
        if (!read_note(pipe_read.value, &note) || note.kind != NOTE_FINAL || note.result ||
            note.stage != 10 || note.error || broker_exit) {
            stage = note.stage; error = note.error; goto done;
        }
    } else if (broker_exit != 125) goto done;
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
    if (job.value && !await_empty_job(job.value, &watch)) cleanup = 0;
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
    printf("{\"scope\":\"DEBUG_BOOTSTRAP_CUSTODY_EXPERIMENT_NOT_PROTECTED_SUPERVISION\","
        "\"mode\":%d,\"result\":%d,\"stage\":%lu,\"systemCode\":%lu,\"accountCreated\":%s,"
        "\"childObserved\":%s,\"brokerTerminationInjected\":%s,\"childExitObserved\":%s,"
        "\"childExit\":%lu,\"brokerExit\":%lu,\"cleanupObserved\":%s,"
        "\"profileRequested\":false,\"nativeStorageExecuted\":false}\n", mode, result,
        (unsigned long)stage, (unsigned long)error, account_created ? "true" : "false",
        child_observed ? "true" : "false", fault_injected ? "true" : "false",
        child_exit_observed ? "true" : "false", (unsigned long)child_exit, (unsigned long)broker_exit,
        cleanup ? "true" : "false");
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
    if (argc == 6 && wcscmp(argv[1], L"--debug-broker") == 0 &&
        wcslen(argv[2]) == 1 && argv[2][0] >= L'0' && argv[2][0] <= L'3') {
        HANDLE controller = parse_handle(argv[3]), pipe = parse_handle(argv[4]), gate = parse_handle(argv[5]);
        if (!controller || !pipe || !gate || !GetProcessId(controller) || GetProcessId(controller) == GetCurrentProcessId())
            return 2;
        return debug_broker(argv[2][0] - L'0', controller, pipe, gate);
    }
    if (argc != 2) return 2;
    if (wcscmp(argv[1], L"--standard-account-probe-child") == 0) return child();
    if (wcscmp(argv[1], L"--disposable-debug-normal-probe") == 0) return debug_controller(TRANSFER_NORMAL);
    if (wcscmp(argv[1], L"--disposable-debug-prejob-death-probe") == 0) return debug_controller(DEATH_PRE_JOB);
    if (wcscmp(argv[1], L"--disposable-debug-job-death-probe") == 0) return debug_controller(DEATH_IN_JOB);
    if (wcscmp(argv[1], L"--disposable-debug-detached-death-probe") == 0) return debug_controller(DEATH_DETACHED);
    return 2;
}
