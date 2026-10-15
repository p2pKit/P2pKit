/* Test-only real Windows custody smoke. Never compile against fake Windows headers or a mock backend.
 * EXTERNAL prerequisite: a newly disposable standard-user account/VM, with no concurrent P2pKit activity.
 * The flag/preflight cannot prove disposability. No canonical fixture is deleted/reset/repaired afterward.
 * One declared synthetic ordinary record is created and expected-ID deleted by run_delete_controls only. */
#if !defined(_WIN32) || !defined(_M_X64)
#error Real Windows x64 SDK/compiler required.
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlobj.h>
#include <intrin.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "profile_win32.h"

_Static_assert(sizeof(void *) == 8 && sizeof(WCHAR) == 2, "Windows x64 ABI required");
#define SMOKE_DEADLINE_MS 120000u
#define RESTART_SMOKE_DEADLINE_MS 30000u
enum { SMOKE_OK = 0, SMOKE_SCOPE = 2, SMOKE_PREFLIGHT = 3, SMOKE_EXISTING = 4,
       SMOKE_CONTROL = 5, SMOKE_CLEANUP_UNKNOWN = 8, SMOKE_DEADLINE_UNKNOWN = 125 };
typedef struct { HANDLE handle; int attempted, closed; } owned_handle;
static int close_owned(owned_handle *owned) {
    if (!owned->handle || owned->handle == INVALID_HANDLE_VALUE) return 1;
    if (owned->attempted) return owned->closed;
    owned->attempted = 1;
    owned->closed = CloseHandle(owned->handle) != 0;
    return owned->closed; /* Retain the exact value and cached failure; never physically retry it. */
}
typedef struct { owned_handle event, thread; ULONGLONG started; DWORD budget; } watchdog;
static void deadline_exit(void) {
    /* No stdio/locks before termination: even logging to a blocked pipe must not defeat this deadline.
     * Exit125 is failed, unproven cleanup, NOT successful native cancellation or a cleanup receipt. */
    (void)TerminateProcess(GetCurrentProcess(), SMOKE_DEADLINE_UNKNOWN);
    __fastfail(FAST_FAIL_FATAL_APP_EXIT);
}
static DWORD WINAPI watchdog_wait(void *opaque) {
    watchdog *owner = opaque;
    ULONGLONG elapsed = GetTickCount64()-owner->started;
    if (elapsed >= owner->budget) deadline_exit();
    DWORD result = WaitForSingleObject(owner->event.handle, (DWORD)(owner->budget-elapsed));
    if (result != WAIT_OBJECT_0 || GetTickCount64()-owner->started >= owner->budget) deadline_exit();
    return 0;
}
static int watchdog_start(watchdog *owner, DWORD budget) {
    memset(owner, 0, sizeof(*owner)); owner->started = GetTickCount64(); owner->budget = budget;
    owner->event.handle = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!owner->event.handle) return 0;
    owner->thread.handle = CreateThread(NULL, 0, watchdog_wait, owner, 0, NULL);
    if (!owner->thread.handle) { (void)close_owned(&owner->event); return 0; }
    return 1;
}
static int watchdog_finish(watchdog *owner) {
    ULONGLONG elapsed = GetTickCount64()-owner->started;
    if (elapsed >= owner->budget || !SetEvent(owner->event.handle)) deadline_exit();
    DWORD waited = WaitForSingleObject(owner->thread.handle, (DWORD)(owner->budget-elapsed));
    if (waited != WAIT_OBJECT_0 || GetTickCount64()-owner->started >= owner->budget) deadline_exit();
    /* The required external owner bounds these final closes and CRT/process exit after this thread joined. */
    int thread_closed = close_owned(&owner->thread);
    int event_closed = close_owned(&owner->event); /* Independent release despite earlier uncertainty. */
    if (GetTickCount64()-owner->started >= owner->budget) deadline_exit();
    return thread_closed && event_closed;
}
static int standard_user(void) {
    owned_handle thread = {0}, process = {0}; int result = SMOKE_PREFLIGHT;
    _Alignas(void *) unsigned char user_bytes[4096] = {0}, owner_bytes[4096] = {0}, group_bytes[16384] = {0};
    if (OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, TRUE, &thread.handle)) goto cleanup;
    if (GetLastError() != ERROR_NO_TOKEN) goto cleanup;
    USHORT process_machine = 0, native_machine = 0;
    if (!IsWow64Process2(GetCurrentProcess(), &process_machine, &native_machine) ||
        process_machine != IMAGE_FILE_MACHINE_UNKNOWN || native_machine != IMAGE_FILE_MACHINE_AMD64) goto cleanup;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &process.handle)) goto cleanup;
    TOKEN_ELEVATION elevation = {0}; TOKEN_ELEVATION_TYPE type; DWORD used = 0;
    if (!GetTokenInformation(process.handle, TokenElevation, &elevation, sizeof(elevation), &used) ||
        used != sizeof(elevation) || elevation.TokenIsElevated ||
        !GetTokenInformation(process.handle, TokenElevationType, &type, sizeof(type), &used) ||
        used != sizeof(type) || type != TokenElevationTypeDefault) goto cleanup;
    if (!GetTokenInformation(process.handle, TokenUser, user_bytes, sizeof(user_bytes), &used) ||
        used < sizeof(TOKEN_USER) || used > sizeof(user_bytes)) goto cleanup;
    PSID user = ((TOKEN_USER *)user_bytes)->User.Sid;
    if (!GetTokenInformation(process.handle, TokenOwner, owner_bytes, sizeof(owner_bytes), &used) ||
        used < sizeof(TOKEN_OWNER) || used > sizeof(owner_bytes)) goto cleanup;
    PSID owner = ((TOKEN_OWNER *)owner_bytes)->Owner;
    if (!IsValidSid(user) || !IsValidSid(owner) || !EqualSid(user, owner) ||
        IsWellKnownSid(user, WinLocalSystemSid) || IsWellKnownSid(user, WinLocalServiceSid) ||
        IsWellKnownSid(user, WinNetworkServiceSid) || IsWellKnownSid(owner, WinBuiltinAdministratorsSid)) goto cleanup;
    if (!GetTokenInformation(process.handle, TokenGroups, group_bytes, sizeof(group_bytes), &used) ||
        used < offsetof(TOKEN_GROUPS, Groups) || used > sizeof(group_bytes)) goto cleanup;
    TOKEN_GROUPS *groups = (TOKEN_GROUPS *)group_bytes;
    if (groups->GroupCount > (used - offsetof(TOKEN_GROUPS, Groups))/sizeof(SID_AND_ATTRIBUTES)) goto cleanup;
    for (DWORD i = 0; i < groups->GroupCount; ++i)
        if (!IsValidSid(groups->Groups[i].Sid) ||
            IsWellKnownSid(groups->Groups[i].Sid, WinBuiltinAdministratorsSid) ||
            IsWellKnownSid(groups->Groups[i].Sid, WinServiceSid)) goto cleanup;
    result = SMOKE_OK; /* Reject Administrators/Service membership regardless of group attributes. */
cleanup:
    if (!close_owned(&process)) result = SMOKE_CLEANUP_UNKNOWN;
    if (!close_owned(&thread)) result = SMOKE_CLEANUP_UNKNOWN;
    pwp_clear(user_bytes, sizeof(user_bytes)); pwp_clear(owner_bytes, sizeof(owner_bytes));
    pwp_clear(group_bytes, sizeof(group_bytes));
    return result;
}
static int no_existing_application_tree(void) {
    PWSTR known = NULL; owned_handle probe = {0}; int result = SMOKE_PREFLIGHT;
    WCHAR path[PWP_PATH_LIMIT] = {0}, extended[PWP_PATH_LIMIT] = {0};
    if (SHGetKnownFolderPath(&FOLDERID_LocalAppData, KF_FLAG_DONT_VERIFY, NULL, &known) != S_OK || !known)
        goto cleanup;
    size_t length = wcsnlen_s(known, PWP_PATH_LIMIT);
    if (!pwp_absolute_path((const uint16_t *)known, length)) goto cleanup;
    memcpy(path, known, (length+1)*sizeof(WCHAR));
    static const WCHAR component[] = L"P2pKit";
    if (!pwp_append_path((uint16_t *)path, PWP_PATH_LIMIT, (const uint16_t *)component,
                         sizeof(component)/sizeof(component[0])-1)) goto cleanup;
    length = wcslen(path);
    if (length+5 > PWP_PATH_LIMIT) goto cleanup;
    memcpy(extended, L"\\\\?\\", 4*sizeof(WCHAR));
    memcpy(extended+4, path, (length+1)*sizeof(WCHAR));
    probe.handle = CreateFileW(extended, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (probe.handle != INVALID_HANDLE_VALUE) {
        /* Any file, directory, alias or reparse object is a refusal, not an adopted fixture. */
        result = SMOKE_EXISTING;
    } else {
        DWORD error = GetLastError();
        result = error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND ? SMOKE_OK : SMOKE_PREFLIGHT;
    }
cleanup:
    if (!close_owned(&probe)) result = SMOKE_CLEANUP_UNKNOWN;
    if (known) CoTaskMemFree(known);
    pwp_clear(path, sizeof(path)); pwp_clear(extended, sizeof(extended));
    return result;
}
static int expected(const char *control, pwp_result actual, pwp_result want) {
    if (actual != want) {
        printf("FAIL %s actual=%d expected=%d\n", control, (int)actual, (int)want); return 0;
    }
    printf("PASS %s\n", control); return 1;
}
static int condition(const char *control, int value) {
    printf("%s %s\n", value ? "PASS" : "FAIL", control); return value;
}
typedef struct { unsigned calls; size_t expected_count; } bytes_control;
static pwp_result copy_synthetic(unsigned char *bytes, size_t count, void *opaque) {
    bytes_control *control = opaque; ++control->calls;
    if (count != control->expected_count || (count && !bytes)) return PWP_ARGUMENT;
    if (count) memset(bytes, 0xa5, count); /* Synthetic only: no profile/key/request/payload evidence. */
    return PWP_OK;
}
static pwp_result receive_empty(unsigned char *bytes, size_t count, void *opaque) {
    bytes_control *control = opaque; ++control->calls;
    return !bytes && count == 0 && control->expected_count == 0 ? PWP_OK : PWP_POLICY;
}
static pwp_result receive_synthetic(unsigned char *bytes, size_t count, void *opaque) {
    bytes_control *control = opaque; ++control->calls;
    if (count != control->expected_count || (count && !bytes)) return PWP_POLICY;
    for (size_t i = 0; i < count; ++i) if (bytes[i] != 0xa5) return PWP_POLICY;
    return PWP_OK;
}
static pwp_result reject_copy(unsigned char *bytes, size_t count, void *opaque) {
    (void)bytes; (void)count;
    bytes_control *control = opaque; ++control->calls;
    return PWP_OS;
}
static pwp_result reject_names(const pwp_directory_names *names, void *opaque) {
    (void)names;
    unsigned *calls = opaque; ++*calls;
    return PWP_POLICY;
}
/* The root is still synthetic and contains exactly these two ordinary members at this checkpoint.
 * The identity directory remains owned with sync rights; its original identity/leases must stay valid. */
static pwp_result receive_initial_root_names(const pwp_directory_names *names, void *opaque) {
    unsigned *calls = opaque; ++*calls;
    static const WCHAR expected[][13] = {L"profile.lock", L"identity"};
    unsigned seen = 0;
    if (!names || names->count != 2) return PWP_POLICY;
    for (size_t i = 0; i < names->count; ++i) {
        unsigned matched = 0;
        for (size_t j = 0; j < 2; ++j) {
            size_t length = wcslen(expected[j]);
            if (names->lengths[i] == length &&
                !memcmp(names->names[i], expected[j], length*sizeof(WCHAR))) matched = 1u << j;
        }
        if (!matched || (seen & matched)) return PWP_POLICY;
        seen |= matched;
    }
    return seen == 3u ? PWP_OK : PWP_POLICY;
}
static int directory_words(const uint64_t words[6]) {
    return words[0] == 1 && words[1] && (words[2] || words[3]) && words[4] == 0x1ff && words[5] == 1;
}
static const WCHAR stage_template[] = L"pwp-stage-00000000000000000000000000000000";
enum { STAGE_COMPONENT_CAPACITY = sizeof(stage_template)/sizeof(stage_template[0]) };
static int stage_component(WCHAR name[STAGE_COMPONENT_CAPACITY], unsigned sequence) {
    static const WCHAR hex[] = L"0123456789abcdef";
    if (sequence > 255u || wcscpy_s(name, STAGE_COMPONENT_CAPACITY, stage_template) != 0) return 0;
    name[STAGE_COMPONENT_CAPACITY-3] = hex[(sequence >> 4) & 15u];
    name[STAGE_COMPONENT_CAPACITY-2] = hex[sequence & 15u];
    return pwp_stage_name((const uint16_t *)name, STAGE_COMPONENT_CAPACITY-1);
}
static const WCHAR candidate_template[] = L"pwp-pending-00000000000000000000000000000000";
enum { CANDIDATE_COMPONENT_CAPACITY = sizeof(candidate_template)/sizeof(candidate_template[0]) };
static int candidate_component(WCHAR name[CANDIDATE_COMPONENT_CAPACITY], unsigned sequence) {
    static const WCHAR hex[] = L"0123456789abcdef";
    if (sequence > 255u || wcscpy_s(name, CANDIDATE_COMPONENT_CAPACITY, candidate_template) != 0) return 0;
    name[CANDIDATE_COMPONENT_CAPACITY-3] = hex[(sequence >> 4) & 15u];
    name[CANDIDATE_COMPONENT_CAPACITY-2] = hex[sequence & 15u];
    return pwp_candidate_name((const uint16_t *)name, CANDIDATE_COMPONENT_CAPACITY-1);
}
#define NAME(value) (const uint16_t *)(value), (sizeof(value)/sizeof((value)[0])-1)
#define EXPECT(label, call, want) do { \
    pwp_result observed_result = (call); \
    if (!expected(label, observed_result, (want))) { \
        if (observed_result == PWP_CLEANUP_UNKNOWN) result = SMOKE_CLEANUP_UNKNOWN; \
        goto failed; \
    } \
} while (0)
#define REQUIRE(label, value) do { if (!condition(label, (value))) goto failed; } while (0)
static int run_rename_controls(uint64_t root, uint64_t profile, uint64_t identity, uint64_t vault) {
    static const WCHAR header[] = L"profile.header", lock_name[] = L"profile.lock";
    static const WCHAR record[] =
        L"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.aesgcm";
    WCHAR pending[CANDIDATE_COMPONENT_CAPACITY];
    int result = SMOKE_CONTROL, exists = 0; uint64_t candidate = 0, observed[6] = {0};
    bytes_control copy = {0, 1}, read = {0, 1};
    REQUIRE("rename-root-pending-name", candidate_component(pending, 40));
    EXPECT("rename-root-prepare", pwp_win_prepare_record(root, NAME(pending), 1, copy_synthetic,
                                                         &copy, &candidate), PWP_OK);
    EXPECT("rename-root-lock-target-denial", pwp_win_rename_candidate(candidate, NAME(lock_name)), PWP_ARGUMENT);
    EXPECT("rename-root-vault-target-denial", pwp_win_rename_candidate(candidate, NAME(record)), PWP_ARGUMENT);
    EXPECT("rename-root-create-only", pwp_win_rename_candidate(candidate, NAME(header)), PWP_OK);
    EXPECT("rename-no-repeat", pwp_win_rename_candidate(candidate, NAME(header)), PWP_CLOSED);
    EXPECT("renamed-no-normal-identity", pwp_win_identity(candidate, observed), PWP_POLICY);
    EXPECT("renamed-no-normal-target-metadata", pwp_win_file_identity(root, NAME(header), observed), PWP_POLICY);
    EXPECT("renamed-no-normal-target-read", pwp_win_read(root, NAME(header), 1,
                                                         receive_synthetic, &read), PWP_POLICY);
    REQUIRE("renamed-no-receiver", read.calls == 0);
    EXPECT("renamed-not-stage", pwp_win_discard_stage(candidate), PWP_ARGUMENT);
    EXPECT("renamed-profile-retained", pwp_win_close(profile), PWP_BUSY);
    EXPECT("renamed-old-name-observation", pwp_win_exists(root, NAME(pending), &exists), PWP_OK);
    REQUIRE("renamed-old-name-absent-now", !exists);
    EXPECT("renamed-root-close", pwp_win_close(candidate), PWP_OK);
    EXPECT("renamed-root-close-idempotent", pwp_win_close(candidate), PWP_OK);
    EXPECT("renamed-header-bytes", pwp_win_read(root, NAME(header), 1, receive_synthetic, &read), PWP_OK);
    REQUIRE("renamed-header-read-once", read.calls == 1);

    /* Deliberately different length: an unsafe replacement/truncation cannot satisfy the old header read. */
    REQUIRE("rename-collision-pending-name", candidate_component(pending, 41));
    copy.calls = 0; copy.expected_count = 0;
    EXPECT("rename-collision-prepare", pwp_win_prepare_record(root, NAME(pending), 0, copy_synthetic,
                                                              &copy, &candidate), PWP_OK);
    EXPECT("rename-existing-target-early-denial", pwp_win_rename_candidate(candidate, NAME(header)), PWP_POLICY);
    EXPECT("rename-collision-candidate-close", pwp_win_close(candidate), PWP_OK);
    bytes_control empty = {0, 0};
    EXPECT("rename-collision-candidate-retained", pwp_win_read(root, NAME(pending), 0,
                                                              receive_empty, &empty), PWP_OK);
    EXPECT("rename-collision-preserves-header", pwp_win_read(root, NAME(header), 1,
                                                             receive_synthetic, &read), PWP_OK);
    REQUIRE("rename-collision-content-checked", empty.calls == 1 && read.calls == 2);

    REQUIRE("rename-identity-pending-name", candidate_component(pending, 42));
    copy.calls = 0; copy.expected_count = 4097;
    EXPECT("rename-identity-prepare", pwp_win_prepare_record(identity, NAME(pending), 4097,
                                                             copy_synthetic, &copy, &candidate), PWP_OK);
    EXPECT("rename-identity-header-denial", pwp_win_rename_candidate(candidate, NAME(header)), PWP_ARGUMENT);
    EXPECT("rename-identity-create-only", pwp_win_rename_candidate(candidate, NAME(record)), PWP_OK);
    EXPECT("renamed-vault-retained", pwp_win_close(vault), PWP_BUSY);
    EXPECT("renamed-identity-retained", pwp_win_close(identity), PWP_BUSY);
    EXPECT("renamed-identity-close", pwp_win_close(candidate), PWP_OK);
    bytes_control encrypted = {0, 4097};
    EXPECT("renamed-identity-bytes", pwp_win_read(identity, NAME(record), 4097,
                                                 receive_synthetic, &encrypted), PWP_OK);
    REQUIRE("renamed-identity-read-once", encrypted.calls == 1);
    result = SMOKE_OK;
failed:
    /* The caller's root drain owns all exact originals, including a still-live or uncertain candidate. */
    pwp_clear(observed, sizeof(observed));
    return result;
}
/* Deliberately unsafe synthetic fixture in this newly disposable account only. Normal inheritance (no
 * protected DACL) must not be repaired/adopted by replacement. Exact create/read handles close once;
 * no cleanup deletes or rewrites the fixture. Paths, owner SIDs and bytes are never printed. */
static int unsafe_record_fixture(const WCHAR *name, int create, uint64_t identity[3]) {
    PWSTR known = NULL; WCHAR path[PWP_PATH_LIMIT] = {0}, extended[PWP_PATH_LIMIT] = {0};
    _Alignas(void *) unsigned char security[4096] = {0};
    owned_handle file = {0}; int result = SMOKE_CONTROL;
    if (!pwp_candidate_replace_target((const uint16_t *)name, wcslen(name), 1) ||
        SHGetKnownFolderPath(&FOLDERID_LocalAppData, KF_FLAG_DONT_VERIFY, NULL, &known) != S_OK || !known)
        goto cleanup;
    size_t length = wcsnlen_s(known, PWP_PATH_LIMIT);
    if (!pwp_absolute_path((const uint16_t *)known, length)) goto cleanup;
    memcpy(path, known, (length+1)*sizeof(WCHAR));
    const WCHAR *parts[] = {L"P2pKit", L"RpcProfile", L"identity", name};
    for (size_t i = 0; i < sizeof(parts)/sizeof(parts[0]); ++i)
        if (!pwp_append_path((uint16_t *)path, PWP_PATH_LIMIT, (const uint16_t *)parts[i], wcslen(parts[i])))
            goto cleanup;
    length = wcslen(path);
    if (length+5 > PWP_PATH_LIMIT) goto cleanup;
    memcpy(extended, L"\\\\?\\", 4*sizeof(WCHAR));
    memcpy(extended+4, path, (length+1)*sizeof(WCHAR));
    file.handle = CreateFileW(extended, GENERIC_READ | (create ? GENERIC_WRITE : 0), 0, NULL,
        create ? CREATE_NEW : OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (file.handle == INVALID_HANDLE_VALUE) goto cleanup;
    /* Observe the actual DACL on this exact original handle both before and after refusal. A generic
     * policy error cannot establish its cause or prove the DACL was not repaired. No allocating retry. */
    DWORD security_size = 0, revision = 0; SECURITY_DESCRIPTOR_CONTROL control = 0;
    PACL acl = NULL; BOOL present = FALSE, defaulted = FALSE;
    if (!GetKernelObjectSecurity(file.handle, DACL_SECURITY_INFORMATION, security, sizeof(security), &security_size) ||
        security_size < SECURITY_DESCRIPTOR_MIN_LENGTH || security_size > sizeof(security) ||
        !IsValidSecurityDescriptor(security) ||
        !GetSecurityDescriptorControl(security, &control, &revision) || revision != SECURITY_DESCRIPTOR_REVISION ||
        !(control & SE_SELF_RELATIVE) || !(control & SE_DACL_PRESENT) || (control & SE_DACL_PROTECTED) ||
        !GetSecurityDescriptorDacl(security, &present, &acl, &defaulted) || !present || !acl || !IsValidAcl(acl))
        goto cleanup;
    unsigned char byte = 0x5a; DWORD count = 0;
    if (create && (!WriteFile(file.handle, &byte, 1, &count, NULL) || count != 1 ||
        !FlushFileBuffers(file.handle))) goto cleanup;
    LARGE_INTEGER zero = {0}, position = {0};
    if (!SetFilePointerEx(file.handle, zero, &position, FILE_BEGIN) || position.QuadPart != 0 ||
        !ReadFile(file.handle, &byte, 1, &count, NULL) || count != 1 || byte != 0x5a) goto cleanup;
    FILE_ID_INFO id; FILE_STANDARD_INFO standard;
    if (!GetFileInformationByHandleEx(file.handle, FileIdInfo, &id, sizeof(id)) ||
        !GetFileInformationByHandleEx(file.handle, FileStandardInfo, &standard, sizeof(standard)) ||
        standard.Directory || standard.DeletePending || standard.NumberOfLinks != 1 ||
        standard.EndOfFile.QuadPart != 1) goto cleanup;
    uint64_t observed[3] = {id.VolumeSerialNumber, 0, 0};
    memcpy(&observed[1], id.FileId.Identifier, 8); memcpy(&observed[2], id.FileId.Identifier+8, 8);
    if (!observed[0] || (!observed[1] && !observed[2])) goto cleanup;
    if (create) memcpy(identity, observed, sizeof(observed));
    else if (memcmp(identity, observed, sizeof(observed))) goto cleanup;
    result = SMOKE_OK;
cleanup:
    if (!close_owned(&file)) result = SMOKE_CLEANUP_UNKNOWN;
    if (known) CoTaskMemFree(known);
    pwp_clear(security, sizeof(security));
    pwp_clear(path, sizeof(path)); pwp_clear(extended, sizeof(extended));
    return result;
}
static int run_replace_controls(uint64_t root, uint64_t profile, uint64_t identity, uint64_t vault) {
    static const WCHAR header[] = L"profile.header", reserved[] = L"vault.lock";
    static const WCHAR record[] =
        L"1111111111111111111111111111111111111111111111111111111111111111.aesgcm";
    static const WCHAR unsafe[] =
        L"3333333333333333333333333333333333333333333333333333333333333333.aesgcm";
    WCHAR pending[CANDIDATE_COMPONENT_CAPACITY], blocked_name[CANDIDATE_COMPONENT_CAPACITY];
    uint64_t candidate = 0, blocked = 0, before[6] = {0}, after[6] = {0}, unsafe_id[3] = {0};
    int result = SMOKE_CONTROL, exists = 0; bytes_control copy = {0, 3}, read = {0, 3};
    EXPECT("replace-invalid-token", pwp_win_replace_candidate(0, NAME(record)), PWP_ARGUMENT);
    EXPECT("replace-directory-token-denial", pwp_win_replace_candidate(identity, NAME(record)), PWP_POLICY);
    EXPECT("replace-lease-token-denial", pwp_win_replace_candidate(vault, NAME(record)), PWP_POLICY);
    REQUIRE("replace-root-pending-name", candidate_component(pending, 49));
    EXPECT("replace-root-prepare", pwp_win_prepare_record(root, NAME(pending), 3,
                                                           copy_synthetic, &copy, &candidate), PWP_OK);
    EXPECT("replace-root-scope-denial", pwp_win_replace_candidate(candidate, NAME(record)), PWP_POLICY);
    EXPECT("replace-header-denial", pwp_win_replace_candidate(candidate, NAME(header)), PWP_ARGUMENT);
    EXPECT("replace-root-candidate-close", pwp_win_close(candidate), PWP_OK);
    bytes_control header_read = {0, 1};
    EXPECT("replace-header-unchanged", pwp_win_read(root, NAME(header), 1,
                                                     receive_synthetic, &header_read), PWP_OK);
    REQUIRE("replace-header-bytes-checked", header_read.calls == 1);
    REQUIRE("replace-absent-pending-name", candidate_component(pending, 50));
    EXPECT("replace-absent-prepare", pwp_win_prepare_record(identity, NAME(pending), 3,
                                                             copy_synthetic, &copy, &candidate), PWP_OK);
    EXPECT("replace-reserved-target-denial", pwp_win_replace_candidate(candidate, NAME(reserved)), PWP_ARGUMENT);
    EXPECT("replace-absent-create-only", pwp_win_replace_candidate(candidate, NAME(record)), PWP_OK);
    EXPECT("replace-no-repeat", pwp_win_replace_candidate(candidate, NAME(record)), PWP_CLOSED);
    EXPECT("replace-live-metadata-denial", pwp_win_file_identity(identity, NAME(record), after), PWP_POLICY);
    EXPECT("replace-live-read-denial", pwp_win_read(identity, NAME(record), 3,
                                                     receive_synthetic, &read), PWP_POLICY);
    REQUIRE("replace-no-premature-receiver", read.calls == 0);
    EXPECT("replace-profile-retained", pwp_win_close(profile), PWP_BUSY);
    EXPECT("replace-vault-retained", pwp_win_close(vault), PWP_BUSY);
    EXPECT("replace-identity-retained", pwp_win_close(identity), PWP_BUSY);
    REQUIRE("replace-owned-collision-name", candidate_component(blocked_name, 51));
    bytes_control blocked_copy = {0, 5}, blocked_read = {0, 5};
    EXPECT("replace-owned-collision-prepare", pwp_win_prepare_record(identity, NAME(blocked_name), 5,
        copy_synthetic, &blocked_copy, &blocked), PWP_OK);
    EXPECT("replace-owned-collision-denial", pwp_win_replace_candidate(blocked, NAME(record)), PWP_POLICY);
    EXPECT("replace-owned-collision-close", pwp_win_close(blocked), PWP_OK);
    EXPECT("replace-owned-collision-pending-retained", pwp_win_read(identity, NAME(blocked_name), 5,
        receive_synthetic, &blocked_read), PWP_OK);
    REQUIRE("replace-owned-collision-pending-checked", blocked_read.calls == 1);
    EXPECT("replace-owned-target-still-live", pwp_win_file_identity(identity, NAME(record), after), PWP_POLICY);
    EXPECT("replace-absent-directory-sync", pwp_win_sync_directory(identity), PWP_OK);
    EXPECT("replace-absent-candidate-close", pwp_win_close(candidate), PWP_OK);
    EXPECT("replace-absent-candidate-close-idempotent", pwp_win_close(candidate), PWP_OK);
    EXPECT("replace-absent-readback", pwp_win_read(identity, NAME(record), 3,
                                                   receive_synthetic, &read), PWP_OK);
    REQUIRE("replace-absent-bytes-checked", read.calls == 1);
    EXPECT("replace-absent-identity", pwp_win_file_identity(identity, NAME(record), before), PWP_OK);
    EXPECT("replace-absent-old-name", pwp_win_exists(identity, NAME(pending), &exists), PWP_OK);
    REQUIRE("replace-absent-old-name-absent-now", !exists);
    REQUIRE("replace-existing-pending-name", candidate_component(pending, 52));
    copy.expected_count = 7; read.expected_count = 7;
    EXPECT("replace-existing-prepare", pwp_win_prepare_record(identity, NAME(pending), 7,
                                                               copy_synthetic, &copy, &candidate), PWP_OK);
    EXPECT("replace-existing-original-handle", pwp_win_replace_candidate(candidate, NAME(record)), PWP_OK);
    EXPECT("replace-existing-directory-sync", pwp_win_sync_directory(identity), PWP_OK);
    EXPECT("replace-existing-candidate-close", pwp_win_close(candidate), PWP_OK);
    EXPECT("replace-existing-new-identity", pwp_win_file_identity(identity, NAME(record), after), PWP_OK);
    REQUIRE("replace-existing-distinct-file-id", before[1] == after[1] &&
        (before[2] != after[2] || before[3] != after[3]));
    EXPECT("replace-existing-new-bytes", pwp_win_read(identity, NAME(record), 7,
                                                      receive_synthetic, &read), PWP_OK);
    REQUIRE("replace-existing-bytes-checked", read.calls == 2);
    EXPECT("replace-existing-old-name", pwp_win_exists(identity, NAME(pending), &exists), PWP_OK);
    REQUIRE("replace-existing-old-name-absent-now", !exists);
    int fixture_result = unsafe_record_fixture(unsafe, 1, unsafe_id);
    if (!condition("replace-unsafe-fixture-created", fixture_result == SMOKE_OK)) {
        result = fixture_result; goto failed;
    }
    EXPECT("replace-unsafe-fixture-refused", pwp_win_file_identity(identity, NAME(unsafe), after), PWP_POLICY);
    REQUIRE("replace-unsafe-pending-name", candidate_component(pending, 53));
    copy.expected_count = 11; read.expected_count = 11;
    EXPECT("replace-unsafe-prepare", pwp_win_prepare_record(identity, NAME(pending), 11,
                                                             copy_synthetic, &copy, &candidate), PWP_OK);
    EXPECT("replace-unsafe-target-denial", pwp_win_replace_candidate(candidate, NAME(unsafe)), PWP_POLICY);
    EXPECT("replace-unsafe-candidate-close", pwp_win_close(candidate), PWP_OK);
    EXPECT("replace-unsafe-pending-preserved", pwp_win_read(identity, NAME(pending), 11,
                                                            receive_synthetic, &read), PWP_OK);
    REQUIRE("replace-unsafe-pending-bytes-checked", read.calls == 3);
    fixture_result = unsafe_record_fixture(unsafe, 0, unsafe_id);
    if (!condition("replace-unsafe-target-id-bytes-and-unprotected-dacl-preserved", fixture_result == SMOKE_OK)) {
        result = fixture_result; goto failed;
    }
    EXPECT("replace-unsafe-target-still-refused", pwp_win_file_identity(identity, NAME(unsafe), after), PWP_POLICY);
    result = SMOKE_OK;
failed:
    pwp_clear(before, sizeof(before)); pwp_clear(after, sizeof(after)); pwp_clear(unsafe_id, sizeof(unsafe_id));
    return result; /* Caller root owns all outstanding native originals; fixture is intentionally retained. */
}
typedef struct { uint64_t directory; const WCHAR *pending, *target; unsigned calls; } write_reentry;
static pwp_result copy_write_reentry(unsigned char *bytes, size_t count, void *opaque) {
    write_reentry *control = opaque; ++control->calls;
    bytes_control nested = {0, count}; uint64_t observed[6] = {0};
    if (control->calls != 1 || count != 1 || !bytes ||
        pwp_win_write_record(control->directory, (const uint16_t *)control->pending, wcslen(control->pending),
            (const uint16_t *)control->target, wcslen(control->target), count, copy_synthetic, &nested, 0) != PWP_BUSY ||
        pwp_win_identity(control->directory, observed) != PWP_BUSY || nested.calls) return PWP_POLICY;
    bytes[0] = 0xa5; return PWP_OK;
}
static int run_write_controls(uint64_t root, uint64_t profile, uint64_t identity, uint64_t *vault) {
    static const WCHAR header[] = L"profile.header", reserved[] = L"vault.lock";
    static const WCHAR record[] =
        L"4444444444444444444444444444444444444444444444444444444444444444.aesgcm";
    static const WCHAR create_only[] =
        L"5555555555555555555555555555555555555555555555555555555555555555.aesgcm";
    static const WCHAR unsafe[] =
        L"6666666666666666666666666666666666666666666666666666666666666666.aesgcm";
    static const WCHAR reentrant[] =
        L"7777777777777777777777777777777777777777777777777777777777777777.aesgcm";
    WCHAR pending[CANDIDATE_COMPONENT_CAPACITY];
    uint64_t before[6] = {0}, after[6] = {0}, profile_before[6] = {0}, vault_before[6] = {0}, unsafe_id[3] = {0};
    int result = SMOKE_CONTROL, exists = 0; bytes_control copy = {0, 3}, read = {0, 1};
    REQUIRE("write-initial-pending-name", candidate_component(pending, 70));
    EXPECT("write-invalid-token", pwp_win_write_record(0, NAME(pending), NAME(record), 3,
        copy_synthetic, &copy, 1), PWP_ARGUMENT);
    EXPECT("write-invalid-replace", pwp_win_write_record(identity, NAME(pending), NAME(record), 3,
        copy_synthetic, &copy, 2), PWP_ARGUMENT);
    EXPECT("write-invalid-pending", pwp_win_write_record(identity, NAME(stage_template), NAME(record), 3,
        copy_synthetic, &copy, 1), PWP_ARGUMENT);
    EXPECT("write-over-limit", pwp_win_write_record(identity, NAME(pending), NAME(record),
        (size_t)PWP_RECORD_LIMIT+1, copy_synthetic, &copy, 1), PWP_ARGUMENT);
    EXPECT("write-reserved-target", pwp_win_write_record(identity, NAME(pending), NAME(reserved), 3,
        copy_synthetic, &copy, 1), PWP_ARGUMENT);
    EXPECT("write-root-scope-denial", pwp_win_write_record(root, NAME(pending), NAME(record), 3,
        copy_synthetic, &copy, 0), PWP_ARGUMENT);
    EXPECT("write-identity-header-denial", pwp_win_write_record(identity, NAME(pending), NAME(header), 3,
        copy_synthetic, &copy, 0), PWP_ARGUMENT);
    EXPECT("write-header-replacement-denial", pwp_win_write_record(root, NAME(pending), NAME(header), 3,
        copy_synthetic, &copy, 1), PWP_ARGUMENT);
    EXPECT("write-lease-as-directory-denial", pwp_win_write_record(*vault, NAME(pending), NAME(record), 3,
        copy_synthetic, &copy, 1), PWP_POLICY);
    REQUIRE("write-invalid-inputs-no-payload-copy", copy.calls == 0);
    EXPECT("write-copy-failure", pwp_win_write_record(identity, NAME(pending), NAME(record), 3,
        reject_copy, &copy, 1), PWP_OS);
    REQUIRE("write-copy-failure-once", copy.calls == 1);
    EXPECT("write-copy-failure-no-pending", pwp_win_exists(identity, NAME(pending), &exists), PWP_OK);
    REQUIRE("write-copy-failure-pending-absent", !exists);
    EXPECT("write-copy-failure-no-target", pwp_win_exists(identity, NAME(record), &exists), PWP_OK);
    REQUIRE("write-copy-failure-target-absent", !exists);
    /* Earlier low-level root publication deliberately owns the fixture's one immutable header.
     * Keep that successful control intact; this composite call must preserve it, not reset the root. */
    REQUIRE("write-header-collision-name", candidate_component(pending, 71));
    EXPECT("write-header-create-only-collision", pwp_win_write_record(root, NAME(pending), NAME(header), 3,
        copy_synthetic, &copy, 0), PWP_POLICY);
    EXPECT("write-header-unchanged", pwp_win_read(root, NAME(header), 1, receive_synthetic, &read), PWP_OK);
    REQUIRE("write-header-checked", read.calls == 1);
    read.calls = 0; read.expected_count = 3;
    EXPECT("write-header-collision-pending-retained", pwp_win_read(root, NAME(pending), 3,
        receive_synthetic, &read), PWP_OK);
    REQUIRE("write-header-pending-owner-retired", read.calls == 1);
    EXPECT("write-profile-original-observation", pwp_win_identity(profile, profile_before), PWP_OK);
    EXPECT("write-vault-original-observation", pwp_win_identity(*vault, vault_before), PWP_OK);
    const size_t sizes[] = {0, 1, PWP_RECORD_LIMIT};
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
        REQUIRE("write-record-pending-name", candidate_component(pending, (unsigned)i+72));
        copy.calls = 0; copy.expected_count = sizes[i]; read.calls = 0; read.expected_count = sizes[i];
        printf("CASE write-record-size-index=%u\n", (unsigned)i);
        EXPECT("write-record-insert-or-replace", pwp_win_write_record(identity, NAME(pending), NAME(record),
            sizes[i], copy_synthetic, &copy, 1), PWP_OK);
        REQUIRE("write-record-copy-once", copy.calls == 1);
        EXPECT("write-record-immediate-identity", pwp_win_file_identity(identity, NAME(record), after), PWP_OK);
        if (i) REQUIRE("write-record-replacement-new-id", before[1] == after[1] &&
            (before[2] != after[2] || before[3] != after[3]));
        memcpy(before, after, sizeof(before));
        EXPECT("write-record-immediate-read", pwp_win_read(identity, NAME(record), sizes[i],
            receive_synthetic, &read), PWP_OK);
        REQUIRE("write-record-original-candidate-retired", read.calls == 1);
        EXPECT("write-record-pending-observation", pwp_win_exists(identity, NAME(pending), &exists), PWP_OK);
        REQUIRE("write-record-pending-absent-now", !exists);
        EXPECT("write-profile-remains-live", pwp_win_identity(profile, after), PWP_OK);
        REQUIRE("write-profile-same-original", memcmp(profile_before, after, sizeof(after)) == 0);
        EXPECT("write-vault-remains-live", pwp_win_identity(*vault, after), PWP_OK);
        REQUIRE("write-vault-same-original", memcmp(vault_before, after, sizeof(after)) == 0);
    }
    copy.calls = 0; copy.expected_count = 1; read.calls = 0; read.expected_count = 1;
    REQUIRE("write-create-only-name", candidate_component(pending, 75));
    EXPECT("write-create-only-success", pwp_win_write_record(identity, NAME(pending), NAME(create_only), 1,
        copy_synthetic, &copy, 0), PWP_OK);
    EXPECT("write-create-only-identity", pwp_win_file_identity(identity, NAME(create_only), before), PWP_OK);
    REQUIRE("write-create-only-collision-name", candidate_component(pending, 76)); copy.expected_count = 3;
    EXPECT("write-create-only-collision", pwp_win_write_record(identity, NAME(pending), NAME(create_only), 3,
        copy_synthetic, &copy, 0), PWP_POLICY);
    EXPECT("write-create-only-preserved-id", pwp_win_file_identity(identity, NAME(create_only), after), PWP_OK);
    REQUIRE("write-create-only-same-id", memcmp(before, after, sizeof(after)) == 0);
    EXPECT("write-create-only-preserved-bytes", pwp_win_read(identity, NAME(create_only), 1,
        receive_synthetic, &read), PWP_OK);
    REQUIRE("write-create-only-bytes-checked", read.calls == 1);
    copy.expected_count = 5;
    EXPECT("write-existing-pending-no-adoption", pwp_win_write_record(identity, NAME(pending), NAME(create_only),
        5, copy_synthetic, &copy, 1), PWP_OS);
    read.calls = 0; read.expected_count = 3;
    EXPECT("write-existing-pending-unchanged", pwp_win_read(identity, NAME(pending), 3,
        receive_synthetic, &read), PWP_OK);
    REQUIRE("write-existing-pending-checked", read.calls == 1);
    int fixture_result = unsafe_record_fixture(unsafe, 1, unsafe_id);
    if (fixture_result != SMOKE_OK) { result = fixture_result; goto failed; }
    REQUIRE("write-unsafe-target-pending-name", candidate_component(pending, 77)); copy.expected_count = 3;
    EXPECT("write-unsafe-target-denial", pwp_win_write_record(identity, NAME(pending), NAME(unsafe), 3,
        copy_synthetic, &copy, 1), PWP_POLICY);
    fixture_result = unsafe_record_fixture(unsafe, 0, unsafe_id);
    if (fixture_result != SMOKE_OK) { result = fixture_result; goto failed; }
    REQUIRE("write-unsafe-target-unchanged", fixture_result == SMOKE_OK);
    REQUIRE("write-reentry-pending-name", candidate_component(pending, 78));
    write_reentry reentry = {identity, pending, reentrant, 0};
    EXPECT("write-one-admission-reentry-refused", pwp_win_write_record(identity, NAME(pending), NAME(reentrant),
        1, copy_write_reentry, &reentry, 0), PWP_OK);
    REQUIRE("write-reentry-copy-once", reentry.calls == 1);
    EXPECT("write-vault-no-leaked-candidate-dependency", pwp_win_close(*vault), PWP_OK); *vault = 0;
    REQUIRE("write-no-vault-pending-name", candidate_component(pending, 79)); copy.calls = 0;
    EXPECT("write-no-vault-denial", pwp_win_write_record(identity, NAME(pending), NAME(record), 3,
        copy_synthetic, &copy, 1), PWP_POLICY);
    REQUIRE("write-no-vault-no-payload-copy", copy.calls == 0);
    EXPECT("write-vault-existing-reacquire", pwp_win_lock(identity, NAME(reserved), vault), PWP_OK);
    result = SMOKE_OK;
failed:
    /* The caller owns whole-root drain; composite calls never return a public candidate to guess/close. */
    pwp_clear(before, sizeof(before)); pwp_clear(after, sizeof(after));
    pwp_clear(profile_before, sizeof(profile_before)); pwp_clear(vault_before, sizeof(vault_before));
    pwp_clear(unsafe_id, sizeof(unsafe_id));
    return result;
}
static int run_delete_controls(uint64_t root, uint64_t profile, uint64_t identity, uint64_t *vault) {
    static const WCHAR header[] = L"profile.header", profile_name[] = L"profile.lock", vault_name[] = L"vault.lock";
    static const WCHAR record[] =
        L"8888888888888888888888888888888888888888888888888888888888888888.aesgcm";
    WCHAR pending[CANDIDATE_COMPONENT_CAPACITY]; uint64_t candidate = 0;
    uint64_t expected_id[6] = {0}, wrong[6] = {0}, observed[6] = {0};
    uint64_t profile_id[6] = {0}, vault_id[6] = {0}, directory_id[6] = {0};
    int result = SMOKE_CONTROL, exists = 0; bytes_control copy = {0, 3}, read = {0, 3};
    REQUIRE("delete-synthetic-pending-name", candidate_component(pending, 100));
    EXPECT("delete-synthetic-record-create", pwp_win_write_record(identity, NAME(pending), NAME(record), 3,
        copy_synthetic, &copy, 0), PWP_OK);
    REQUIRE("delete-synthetic-copy-once", copy.calls == 1);
    EXPECT("delete-synthetic-original-id", pwp_win_file_identity(identity, NAME(record), expected_id), PWP_OK);
    EXPECT("delete-original-profile", pwp_win_identity(profile, profile_id), PWP_OK);
    EXPECT("delete-original-vault", pwp_win_identity(*vault, vault_id), PWP_OK);
    EXPECT("delete-original-directory", pwp_win_identity(identity, directory_id), PWP_OK);
    EXPECT("delete-invalid-token", pwp_win_delete_record(0, NAME(record), expected_id, 6), PWP_ARGUMENT);
    EXPECT("delete-null-expected", pwp_win_delete_record(identity, NAME(record), NULL, 6), PWP_ARGUMENT);
    EXPECT("delete-invalid-expected-size", pwp_win_delete_record(identity, NAME(record), expected_id, 5), PWP_ARGUMENT);
    memcpy(wrong, expected_id, sizeof(wrong)); wrong[4] = 0x1ff;
    EXPECT("delete-invalid-expected-kind", pwp_win_delete_record(identity, NAME(record), wrong, 6), PWP_ARGUMENT);
    EXPECT("delete-lease-not-directory", pwp_win_delete_record(*vault, NAME(record), expected_id, 6), PWP_POLICY);
    EXPECT("delete-profile-not-borrowed", pwp_win_delete_record(root, NAME(profile_name), profile_id, 6), PWP_POLICY);
    EXPECT("delete-vault-not-borrowed", pwp_win_delete_record(identity, NAME(vault_name), vault_id, 6), PWP_POLICY);
    memcpy(wrong, expected_id, sizeof(wrong)); wrong[2] ^= UINT64_C(0x8000000000000000);
    if (!wrong[2] && !wrong[3]) wrong[3] = 1;
    EXPECT("delete-wrong-original-id", pwp_win_delete_record(identity, NAME(record), wrong, 6), PWP_POLICY);
    EXPECT("delete-wrong-id-preserves-identity", pwp_win_file_identity(identity, NAME(record), observed), PWP_OK);
    REQUIRE("delete-wrong-id-same-original", memcmp(expected_id, observed, sizeof(observed)) == 0);
    EXPECT("delete-wrong-id-preserves-bytes", pwp_win_read(identity, NAME(record), 3,
        receive_synthetic, &read), PWP_OK);
    REQUIRE("delete-wrong-id-bytes-checked", read.calls == 1);
    REQUIRE("delete-held-candidate-name", candidate_component(pending, 101));
    EXPECT("delete-held-candidate-prepare", pwp_win_prepare_record(identity, NAME(pending), 3,
        copy_synthetic, &copy, &candidate), PWP_OK);
    EXPECT("delete-candidate-not-borrowed", pwp_win_delete_record(identity, NAME(pending), expected_id, 6), PWP_POLICY);
    EXPECT("delete-candidate-vault-still-retained", pwp_win_close(*vault), PWP_BUSY);
    EXPECT("delete-candidate-close-only", pwp_win_close(candidate), PWP_OK); candidate = 0;
    read.calls = 0;
    EXPECT("delete-refused-candidate-bytes-retained", pwp_win_read(identity, NAME(pending), 3,
        receive_synthetic, &read), PWP_OK);
    REQUIRE("delete-refused-candidate-checked", read.calls == 1);
    EXPECT("delete-vault-release-for-authority-control", pwp_win_close(*vault), PWP_OK); *vault = 0;
    EXPECT("delete-without-vault-refused", pwp_win_delete_record(identity, NAME(record), expected_id, 6), PWP_POLICY);
    EXPECT("delete-without-vault-keeps-original", pwp_win_file_identity(identity, NAME(record), observed), PWP_OK);
    REQUIRE("delete-without-vault-id-preserved", memcmp(expected_id, observed, sizeof(observed)) == 0);
    EXPECT("delete-vault-existing-reacquire", pwp_win_lock(identity, NAME(vault_name), vault), PWP_OK);
    /* This is the sole successful ordinary-file deletion in the harness. It is not fixture cleanup:
     * original expected-ID disposition/readback/close, exact absence and original-parent sync compose natively. */
    EXPECT("delete-record-composed-success", pwp_win_delete_record(identity, NAME(record), expected_id, 6), PWP_OK);
    EXPECT("delete-record-current-existence", pwp_win_exists(identity, NAME(record), &exists), PWP_OK);
    REQUIRE("delete-record-currently-absent", !exists);
    EXPECT("delete-record-no-metadata", pwp_win_file_identity(identity, NAME(record), observed), PWP_NOT_FOUND);
    read.calls = 0;
    EXPECT("delete-record-no-read", pwp_win_read(identity, NAME(record), 3, receive_synthetic, &read), PWP_NOT_FOUND);
    REQUIRE("delete-record-no-receiver", read.calls == 0);
    EXPECT("delete-repeat-is-missing-error", pwp_win_delete_record(identity, NAME(record), expected_id, 6), PWP_NOT_FOUND);
    EXPECT("delete-low-level-missing-error", pwp_win_request_delete(identity, NAME(record), expected_id, 6), PWP_NOT_FOUND);
    EXPECT("delete-profile-remains-live", pwp_win_identity(profile, observed), PWP_OK);
    REQUIRE("delete-profile-original-preserved", memcmp(profile_id, observed, sizeof(observed)) == 0);
    EXPECT("delete-vault-remains-live", pwp_win_identity(*vault, observed), PWP_OK);
    REQUIRE("delete-vault-original-preserved", memcmp(vault_id, observed, sizeof(observed)) == 0);
    EXPECT("delete-directory-remains-live", pwp_win_identity(identity, observed), PWP_OK);
    REQUIRE("delete-directory-original-preserved", memcmp(directory_id, observed, sizeof(observed)) == 0);
    read.expected_count = 1;
    EXPECT("delete-immutable-header-preserved", pwp_win_read(root, NAME(header), 1,
        receive_synthetic, &read), PWP_OK);
    REQUIRE("delete-immutable-header-checked", read.calls == 1);
    result = SMOKE_OK;
failed:
    /* Root drain owns remaining handles; never retry, path-delete or reset any record after a failure. */
    pwp_clear(expected_id, sizeof(expected_id)); pwp_clear(wrong, sizeof(wrong)); pwp_clear(observed, sizeof(observed));
    pwp_clear(profile_id, sizeof(profile_id)); pwp_clear(vault_id, sizeof(vault_id));
    pwp_clear(directory_id, sizeof(directory_id));
    return result;
}
static int run_controls(void) {
    static const WCHAR profile[] = L"profile.lock", vault[] = L"vault.lock", identity[] = L"identity";
    static const WCHAR header[] = L"profile.header";
    static const WCHAR identity_alias[] = L"IDENTITY", other[] = L"other.lock", child_other[] = L"other";
    static const WCHAR denial_record[] =
        L"1111111111111111111111111111111111111111111111111111111111111111.aesgcm";
    WCHAR stage_name[STAGE_COMPONENT_CAPACITY], root_stage_name[STAGE_COMPONENT_CAPACITY];
    WCHAR candidate_name[CANDIDATE_COMPONENT_CAPACITY];
    uint64_t root = 0, p = 0, id = 0, v = 0, s = 0, outer = 0, rejected = 0;
    uint64_t root_words[6] = {0}, profile_words[6] = {0}, identity_words[6] = {0}, observed[6] = {0};
    int exists = 0, result = SMOKE_CONTROL; bytes_control copy = {0, 1}, read = {0, 0};
    REQUIRE("initial-stage-name", stage_component(stage_name, 0));
    REQUIRE("initial-root-stage-name", stage_component(root_stage_name, 10));
    REQUIRE("initial-candidate-name", candidate_component(candidate_name, 0));
    EXPECT("bootstrap", pwp_win_open_root(&root), PWP_OK);
    REQUIRE("root-token", pwp_token_valid(root));
    EXPECT("root-observation", pwp_win_identity(root, root_words), PWP_OK);
    REQUIRE("root-custody-shape", directory_words(root_words));
    /* Existing-but-empty fixed directories still require the complete ABI13 private bootstrap path.
     * This is a same-run ownership test, not a crash/disk-cache/power-loss qualification claim. */
    uint64_t empty_root = root;
    EXPECT("empty-bootstrap-close", pwp_win_close(root), PWP_OK); root = 0;
    EXPECT("empty-bootstrap-readmission", pwp_win_open_root(&root), PWP_OK);
    REQUIRE("empty-bootstrap-new-owner", root > empty_root);
    EXPECT("empty-bootstrap-same-object", pwp_win_identity(root, observed), PWP_OK);
    REQUIRE("empty-bootstrap-identity-preserved", memcmp(observed, root_words, sizeof(observed)) == 0);
    EXPECT("sync-invalid-token", pwp_win_sync_directory(0), PWP_ARGUMENT);
    EXPECT("pre-profile-sync-denial", pwp_win_sync_directory(root), PWP_POLICY);
    EXPECT("initial-profile-observation", pwp_win_exists(root, NAME(profile), &exists), PWP_OK);
    REQUIRE("initial-profile-absent", !exists);
    EXPECT("missing-profile-read0", pwp_win_read(root, NAME(profile), 0, receive_empty, &read), PWP_NOT_FOUND);
    REQUIRE("missing-read-no-receiver", read.calls == 0);
    EXPECT("pre-profile-child-denial", pwp_win_create_child(root, NAME(identity), &rejected), PWP_POLICY);
    REQUIRE("pre-profile-child-no-token", rejected == 0);
    EXPECT("pre-profile-child-absence", pwp_win_exists(root, NAME(identity), &exists), PWP_OK);
    REQUIRE("pre-profile-child-not-created", !exists);
    EXPECT("pre-profile-vault-denial", pwp_win_create_vault_lock(root, &rejected), PWP_POLICY);
    EXPECT("pre-profile-stage-denial",
        pwp_win_stage(root, NAME(stage_name), 1, copy_synthetic, &copy, &rejected), PWP_POLICY);
    REQUIRE("pre-profile-no-payload-copy", copy.calls == 0 && rejected == 0);
    EXPECT("pre-profile-candidate-denial",
        pwp_win_prepare_record(root, NAME(candidate_name), 1, copy_synthetic, &copy, &rejected), PWP_POLICY);
    REQUIRE("pre-profile-candidate-no-copy", copy.calls == 0 && rejected == 0);
    EXPECT("pre-profile-write-denial", pwp_win_write_record(root, NAME(candidate_name), NAME(header), 1,
        copy_synthetic, &copy, 0), PWP_POLICY);
    REQUIRE("pre-profile-write-no-copy", copy.calls == 0);
    EXPECT("wrong-lock-name", pwp_win_lock(root, NAME(other), &rejected), PWP_POLICY);
    EXPECT("wrong-vault-scope", pwp_win_lock(root, NAME(vault), &rejected), PWP_POLICY);
    EXPECT("open-missing-lock-no-create", pwp_win_lock(root, NAME(profile), &rejected), PWP_NOT_FOUND);
    EXPECT("profile-create", pwp_win_create_profile_lock(root, &p), PWP_OK);
    EXPECT("root-directory-sync", pwp_win_sync_directory(root), PWP_OK);
    EXPECT("root-independent-directory-sync", pwp_win_sync_directory(root), PWP_OK);
    EXPECT("profile-file-sync-denial", pwp_win_sync_directory(p), PWP_POLICY);
    EXPECT("duplicate-profile-denial", pwp_win_create_profile_lock(root, &rejected), PWP_BUSY);
    REQUIRE("duplicate-profile-no-token", rejected == 0);
    EXPECT("held-profile-exists", pwp_win_exists(root, NAME(profile), &exists), PWP_OK);
    REQUIRE("held-profile-present", exists);
    EXPECT("held-profile-identity", pwp_win_file_identity(root, NAME(profile), profile_words), PWP_OK);
    REQUIRE("held-profile-custody-shape", pwp_expected_lock_file(root_words, profile_words, 6));
    /* Identity/exists borrow the held handle; read never unlocks/reopens a share-none lease successfully. */
    EXPECT("held-read-does-not-unlock", pwp_win_read(root, NAME(profile), 0, receive_empty, &read), PWP_OS);
    REQUIRE("held-read-no-receiver", read.calls == 0);
    EXPECT("profile-close", pwp_win_close(p), PWP_OK);
    EXPECT("profile-close-idempotent", pwp_win_close(p), PWP_OK);
    EXPECT("released-profile-sync-denial", pwp_win_sync_directory(root), PWP_POLICY);
    EXPECT("no-profile-deletion-denial",
        pwp_win_request_delete(root, NAME(profile), profile_words, 6), PWP_POLICY);
    EXPECT("pre-lease-existing-read0", pwp_win_read(root, NAME(profile), 0, receive_empty, &read), PWP_OK);
    REQUIRE("empty-read-received-once", read.calls == 1);
    uint64_t old_profile = p;
    EXPECT("existing-profile-lease", pwp_win_lock(root, NAME(profile), &p), PWP_OK);
    REQUIRE("profile-token-not-reused", p > old_profile);
    EXPECT("profile-file-preserved", pwp_win_file_identity(root, NAME(profile), observed), PWP_OK);
    REQUIRE("profile-identity-preserved", memcmp(profile_words, observed, sizeof(observed)) == 0);
    EXPECT("identity-create", pwp_win_create_child(root, NAME(identity), &id), PWP_OK);
    EXPECT("identity-observation", pwp_win_identity(id, observed), PWP_OK);
    REQUIRE("identity-custody-shape", pwp_expected_child_directory(root_words, observed, 6));
    memcpy(identity_words, observed, sizeof(identity_words));
    unsigned initial_name_calls = 0;
    EXPECT("owned-identity-exists-before-vault", pwp_win_exists(root, NAME(identity), &exists), PWP_OK);
    REQUIRE("owned-identity-present-before-vault", exists);
    EXPECT("owned-identity-alias-exists", pwp_win_exists(root, NAME(identity_alias), &exists), PWP_OK);
    REQUIRE("owned-identity-alias-present", exists);
    EXPECT("owned-identity-root-inventory-before-vault",
        pwp_win_names(root, receive_initial_root_names, &initial_name_calls), PWP_OK);
    REQUIRE("owned-identity-inventory-once-before-vault", initial_name_calls == 1u);
    EXPECT("owned-identity-original-before-vault", pwp_win_identity(id, observed), PWP_OK);
    REQUIRE("owned-identity-id-before-vault", !memcmp(identity_words, observed, sizeof(observed)));
    EXPECT("pre-vault-identity-sync-denial", pwp_win_sync_directory(id), PWP_POLICY);
    EXPECT("root-sync-without-vault", pwp_win_sync_directory(root), PWP_OK);
    EXPECT("duplicate-identity-alias", pwp_win_child(root, NAME(identity_alias), &rejected), PWP_BUSY);
    REQUIRE("duplicate-identity-no-token", rejected == 0);
    EXPECT("alternate-child-denial", pwp_win_create_child(root, NAME(child_other), &rejected), PWP_POLICY);
    EXPECT("descendant-child-denial", pwp_win_create_child(id, NAME(identity), &rejected), PWP_POLICY);
    EXPECT("wrong-profile-scope", pwp_win_create_profile_lock(id, &rejected), PWP_POLICY);
    EXPECT("pre-vault-stage-denial",
        pwp_win_stage(id, NAME(stage_name), 1, copy_synthetic, &copy, &rejected), PWP_POLICY);
    REQUIRE("pre-vault-no-payload-copy", copy.calls == 0 && rejected == 0);
    EXPECT("pre-vault-candidate-denial",
        pwp_win_prepare_record(id, NAME(candidate_name), 1, copy_synthetic, &copy, &rejected), PWP_POLICY);
    REQUIRE("pre-vault-candidate-no-copy", copy.calls == 0 && rejected == 0);
    EXPECT("pre-vault-write-denial", pwp_win_write_record(id, NAME(candidate_name), NAME(denial_record), 1,
        copy_synthetic, &copy, 1), PWP_POLICY);
    REQUIRE("pre-vault-write-no-copy", copy.calls == 0);
    EXPECT("vault-create", pwp_win_create_vault_lock(id, &v), PWP_OK);
    EXPECT("owned-identity-exists-with-vault", pwp_win_exists(root, NAME(identity), &exists), PWP_OK);
    REQUIRE("owned-identity-present-with-vault", exists);
    EXPECT("owned-identity-root-inventory-with-vault",
        pwp_win_names(root, receive_initial_root_names, &initial_name_calls), PWP_OK);
    REQUIRE("owned-identity-inventory-once-with-vault", initial_name_calls == 2u);
    EXPECT("owned-identity-original-with-vault", pwp_win_identity(id, observed), PWP_OK);
    REQUIRE("owned-identity-id-with-vault", !memcmp(identity_words, observed, sizeof(observed)));
    EXPECT("owned-profile-original-after-inventory", pwp_win_file_identity(root, NAME(profile), observed), PWP_OK);
    REQUIRE("owned-profile-id-after-inventory", !memcmp(profile_words, observed, sizeof(observed)));
    EXPECT("identity-directory-sync", pwp_win_sync_directory(id), PWP_OK);
    EXPECT("identity-independent-directory-sync", pwp_win_sync_directory(id), PWP_OK);
    EXPECT("vault-file-sync-denial", pwp_win_sync_directory(v), PWP_POLICY);
    EXPECT("duplicate-vault-denial", pwp_win_create_vault_lock(id, &rejected), PWP_BUSY);
    EXPECT("profile-retained-for-vault", pwp_win_close(p), PWP_BUSY);
    EXPECT("identity-retained-for-vault", pwp_win_close(id), PWP_BUSY);
    const size_t sizes[] = {0, 1, PWP_RECORD_LIMIT};
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
        /* No name reuse after close: cleanup does not promise immediate/durable namespace absence. */
        REQUIRE("identity-stage-name", stage_component(stage_name, (unsigned)i+1));
        printf("CASE stage-size-index=%u\n", (unsigned)i);
        copy.calls = 0; copy.expected_count = sizes[i];
        EXPECT("identity-stage-fill",
            pwp_win_stage(id, NAME(stage_name), sizes[i], copy_synthetic, &copy, &s), PWP_OK);
        REQUIRE("identity-stage-copy-once", copy.calls == 1 && pwp_token_valid(s));
        EXPECT("stage-normal-identity-denial", pwp_win_identity(s, observed), PWP_POLICY);
        EXPECT("stage-cannot-publish", pwp_win_rename_candidate(s, NAME(profile)), PWP_POLICY);
        EXPECT("stage-cannot-replace", pwp_win_replace_candidate(s, NAME(denial_record)), PWP_POLICY);
        EXPECT("stage-file-identity-denial", pwp_win_file_identity(id, NAME(stage_name), observed), PWP_POLICY);
        EXPECT("stage-existence-denial", pwp_win_exists(id, NAME(stage_name), &exists), PWP_POLICY);
        unsigned old_calls = read.calls;
        EXPECT("stage-read-denial", pwp_win_read(id, NAME(stage_name), 0, receive_empty, &read), PWP_POLICY);
        REQUIRE("stage-read-no-receiver", read.calls == old_calls);
        EXPECT("vault-retained-for-stage", pwp_win_close(v), PWP_BUSY);
        EXPECT("profile-retained-for-stage", pwp_win_close(p), PWP_BUSY);
        EXPECT("identity-retained-for-stage", pwp_win_close(id), PWP_BUSY);
        EXPECT("stage-discard", pwp_win_discard_stage(s), PWP_OK);
        EXPECT("stage-discard-idempotent", pwp_win_discard_stage(s), PWP_OK); s = 0;
    }
    copy.calls = 0; copy.expected_count = 1;
    EXPECT("over-limit-stage-denial",
        pwp_win_stage(id, NAME(stage_name), (size_t)PWP_RECORD_LIMIT+1, copy_synthetic, &copy, &rejected),
        PWP_ARGUMENT);
    REQUIRE("over-limit-no-payload-copy", copy.calls == 0 && rejected == 0);
    EXPECT("over-limit-candidate-denial",
        pwp_win_prepare_record(id, NAME(candidate_name), (size_t)PWP_RECORD_LIMIT+1,
                               copy_synthetic, &copy, &rejected), PWP_ARGUMENT);
    REQUIRE("over-limit-candidate-no-copy", copy.calls == 0 && rejected == 0);
    EXPECT("stage-name-not-candidate",
        pwp_win_prepare_record(id, NAME(stage_name), 1, copy_synthetic, &copy, &rejected), PWP_ARGUMENT);
    REQUIRE("bad-candidate-name-no-copy", copy.calls == 0 && rejected == 0);
    REQUIRE("candidate-copy-failure-name", candidate_component(candidate_name, 20));
    EXPECT("candidate-copy-failure",
        pwp_win_prepare_record(id, NAME(candidate_name), 1, reject_copy, &copy, &rejected), PWP_OS);
    REQUIRE("candidate-copy-failure-no-token", rejected == 0 && copy.calls == 1);
    EXPECT("candidate-copy-failure-no-create", pwp_win_exists(id, NAME(candidate_name), &exists), PWP_OK);
    REQUIRE("candidate-copy-failure-absent", !exists);
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
        REQUIRE("persistent-candidate-name", candidate_component(candidate_name, (unsigned)i+1));
        printf("CASE candidate-size-index=%u\n", (unsigned)i);
        copy.calls = 0; copy.expected_count = sizes[i];
        EXPECT("candidate-prepare",
            pwp_win_prepare_record(id, NAME(candidate_name), sizes[i], copy_synthetic, &copy, &s), PWP_OK);
        REQUIRE("candidate-copy-once", copy.calls == 1 && pwp_token_valid(s));
        EXPECT("candidate-not-record-identity", pwp_win_identity(s, observed), PWP_POLICY);
        EXPECT("candidate-not-file-identity", pwp_win_file_identity(id, NAME(candidate_name), observed), PWP_POLICY);
        EXPECT("candidate-not-record-exists", pwp_win_exists(id, NAME(candidate_name), &exists), PWP_POLICY);
        unsigned name_calls = 0;
        EXPECT("candidate-not-record-inventory", pwp_win_names(id, reject_names, &name_calls), PWP_POLICY);
        REQUIRE("candidate-no-inventory-receiver", name_calls == 0);
        bytes_control candidate_read = {0, sizes[i]};
        EXPECT("candidate-not-record-read",
            pwp_win_read(id, NAME(candidate_name), sizes[i], receive_synthetic, &candidate_read), PWP_POLICY);
        REQUIRE("candidate-no-read-receiver", candidate_read.calls == 0);
        EXPECT("candidate-vault-dependent", pwp_win_close(v), PWP_BUSY);
        EXPECT("candidate-profile-dependent", pwp_win_close(p), PWP_BUSY);
        EXPECT("candidate-directory-dependent", pwp_win_close(id), PWP_BUSY);
        EXPECT("candidate-not-disposable-stage", pwp_win_discard_stage(s), PWP_ARGUMENT);
        EXPECT("candidate-close-only", pwp_win_close(s), PWP_OK);
        EXPECT("candidate-close-idempotent", pwp_win_close(s), PWP_OK); s = 0;
        EXPECT("candidate-retained", pwp_win_exists(id, NAME(candidate_name), &exists), PWP_OK);
        REQUIRE("candidate-retained-present", exists);
        EXPECT("candidate-retained-bytes",
            pwp_win_read(id, NAME(candidate_name), sizes[i], receive_synthetic, &candidate_read), PWP_OK);
        REQUIRE("candidate-retained-receiver", candidate_read.calls == 1);
        /* Same-name create must never adopt or truncate the retained candidate. */
        EXPECT("candidate-collision",
            pwp_win_prepare_record(id, NAME(candidate_name), sizes[i], copy_synthetic, &copy, &rejected), PWP_OS);
        REQUIRE("candidate-collision-no-token", rejected == 0);
        EXPECT("candidate-collision-preserves-bytes",
            pwp_win_read(id, NAME(candidate_name), sizes[i], receive_synthetic, &candidate_read), PWP_OK);
        REQUIRE("candidate-collision-receiver", candidate_read.calls == 2);
    }
    copy.calls = 0; copy.expected_count = 1;
    EXPECT("root-stage-fill", pwp_win_stage(root, NAME(root_stage_name), 1, copy_synthetic, &copy, &outer), PWP_OK);
    EXPECT("vault-close-independent-of-root-stage", pwp_win_close(v), PWP_OK); v = 0;
    EXPECT("profile-retained-for-root-stage", pwp_win_close(p), PWP_BUSY);
    EXPECT("root-stage-discard", pwp_win_discard_stage(outer), PWP_OK); outer = 0;
    REQUIRE("root-candidate-name", candidate_component(candidate_name, 25));
    EXPECT("root-candidate-without-vault",
        pwp_win_prepare_record(root, NAME(candidate_name), 1, copy_synthetic, &copy, &outer), PWP_OK);
    EXPECT("root-candidate-profile-dependent", pwp_win_close(p), PWP_BUSY);
    EXPECT("root-candidate-close-only", pwp_win_close(outer), PWP_OK); outer = 0;
    EXPECT("vault-existing-lease", pwp_win_lock(id, NAME(vault), &v), PWP_OK);
    int rename_result = run_rename_controls(root, p, id, v);
    if (rename_result != SMOKE_OK) { result = rename_result; goto failed; }
    int replace_result = run_replace_controls(root, p, id, v);
    if (replace_result != SMOKE_OK) { result = replace_result; goto failed; }
    int write_result = run_write_controls(root, p, id, &v);
    if (write_result != SMOKE_OK) { result = write_result; goto failed; }
    int delete_result = run_delete_controls(root, p, id, &v);
    if (delete_result != SMOKE_OK) { result = delete_result; goto failed; }
    EXPECT("renamed-root-directory-sync", pwp_win_sync_directory(root), PWP_OK);
    EXPECT("renamed-identity-directory-sync", pwp_win_sync_directory(id), PWP_OK);
    REQUIRE("terminal-root-stage-name", stage_component(root_stage_name, 11));
    REQUIRE("terminal-identity-stage-name", stage_component(stage_name, 12));
    EXPECT("terminal-root-stage",
        pwp_win_stage(root, NAME(root_stage_name), 1, copy_synthetic, &copy, &outer), PWP_OK);
    EXPECT("terminal-identity-stage",
        pwp_win_stage(id, NAME(stage_name), 1, copy_synthetic, &copy, &s), PWP_OK);
    REQUIRE("terminal-candidate-name", candidate_component(candidate_name, 30));
    EXPECT("terminal-candidate",
        pwp_win_prepare_record(id, NAME(candidate_name), 1, copy_synthetic, &copy, &rejected), PWP_OK);
    EXPECT("root-live-dependency-drain", pwp_win_close(root), PWP_OK);
    EXPECT("root-close-idempotent", pwp_win_close(root), PWP_OK);
    EXPECT("closed-session-denial", pwp_win_exists(root, NAME(profile), &exists), PWP_CLOSED);
    EXPECT("closed-session-sync-denial", pwp_win_sync_directory(root), PWP_CLOSED);
    EXPECT("closed-session-write-denial", pwp_win_write_record(id, NAME(candidate_name), NAME(denial_record), 1,
        copy_synthetic, &copy, 1), PWP_CLOSED);
    EXPECT("closed-session-delete-denial", pwp_win_delete_record(id, NAME(denial_record), profile_words, 6), PWP_CLOSED);
    uint64_t old_root = root; root = 0;
    EXPECT("owned-session-reopen", pwp_win_open_root(&root), PWP_OK);
    REQUIRE("root-token-not-reused", root > old_root);
    EXPECT("reopened-root-observation", pwp_win_identity(root, observed), PWP_OK);
    REQUIRE("same-owned-root-preserved", memcmp(observed, root_words, sizeof(observed)) == 0);
    EXPECT("reopened-pre-profile-sync-denial", pwp_win_sync_directory(root), PWP_POLICY);
    EXPECT("reopened-pre-lease-read0", pwp_win_read(root, NAME(profile), 0, receive_empty, &read), PWP_OK);
    REQUIRE("reopened-empty-read-received", read.calls == 2);
    EXPECT("reopened-identity", pwp_win_child(root, NAME(identity), &id), PWP_OK);
    bytes_control retained = {0, 1};
    EXPECT("terminal-candidate-retained",
        pwp_win_read(id, NAME(candidate_name), 1, receive_synthetic, &retained), PWP_OK);
    REQUIRE("terminal-candidate-retained-bytes", retained.calls == 1);
    EXPECT("reopened-clean-close", pwp_win_close(root), PWP_OK); root = 0;
    result = SMOKE_OK;
failed:
    if (root) {
        /* Root owns every original role/stage, including unpublished failures. */
        pwp_result cleanup = pwp_win_close(root);
        if (!expected("terminal-cleanup", cleanup, PWP_OK)) result = SMOKE_CLEANUP_UNKNOWN;
    }
    pwp_clear(root_words, sizeof(root_words)); pwp_clear(profile_words, sizeof(profile_words));
    pwp_clear(identity_words, sizeof(identity_words)); pwp_clear(observed, sizeof(observed));
    return result;
}
typedef struct { const WCHAR *const *names; size_t count; unsigned calls; } restart_inventory;
static pwp_result receive_restart_inventory(const pwp_directory_names *names, void *opaque) {
    restart_inventory *control = opaque; ++control->calls;
    if (!names || control->count > 3 || names->count != control->count) return PWP_POLICY;
    unsigned seen = 0;
    for (size_t i = 0; i < names->count; ++i) {
        size_t match = control->count;
        for (size_t j = 0; j < control->count; ++j) {
            size_t length = wcslen(control->names[j]);
            if (length == names->lengths[i] &&
                memcmp(names->names[i], control->names[j], length*sizeof(WCHAR)) == 0) { match = j; break; }
        }
        if (match == control->count || (seen & (1u << match))) return PWP_POLICY;
        seen |= 1u << match;
    }
    return seen == (1u << control->count)-1u ? PWP_OK : PWP_POLICY;
}
/* A separate cold fixture is necessary: the original mode already owns an immutable header before
 * its composite-write controls. This mode performs orderly same-process session retirement/reopen,
 * not a process restart, interrupted-state repair, cryptographic profile or durability qualification. */
static int run_restart_controls(void) {
    static const WCHAR profile[] = L"profile.lock", vault[] = L"vault.lock", identity[] = L"identity";
    static const WCHAR header[] = L"profile.header";
    static const WCHAR record[] =
        L"6666666666666666666666666666666666666666666666666666666666666666.aesgcm";
    const WCHAR *root_names[] = {profile, header, identity}, *identity_names[] = {vault, record};
    restart_inventory root_inventory = {root_names, 3, 0}, identity_inventory = {identity_names, 2, 0};
    WCHAR header_pending[CANDIDATE_COMPONENT_CAPACITY], record_pending[CANDIDATE_COMPONENT_CAPACITY];
    uint64_t root = 0, p = 0, id = 0, v = 0;
    uint64_t root_words[6] = {0}, profile_words[6] = {0}, header_words[6] = {0};
    uint64_t identity_words[6] = {0}, vault_words[6] = {0}, record_words[6] = {0}, observed[6] = {0};
    uint64_t previous_root = 0, previous_profile = 0, previous_identity = 0, previous_vault = 0, inventory_vault = 0;
    int exists = 0, result = SMOKE_CONTROL, root_close_attempted = 0;
    bytes_control header_copy = {0, 41}, record_copy = {0, 37};
    bytes_control header_read = {0, 41}, record_read = {0, 37}, empty_read = {0, 0};
    REQUIRE("restart-header-pending-name", candidate_component(header_pending, 200));
    REQUIRE("restart-record-pending-name", candidate_component(record_pending, 201));
    EXPECT("restart-cold-bootstrap", pwp_win_open_root(&root), PWP_OK);
    EXPECT("restart-root-identity", pwp_win_identity(root, root_words), PWP_OK);
    REQUIRE("restart-root-custody", directory_words(root_words));
    EXPECT("restart-new-profile-lock", pwp_win_create_profile_lock(root, &p), PWP_OK);
    EXPECT("restart-profile-identity", pwp_win_file_identity(root, NAME(profile), profile_words), PWP_OK);
    REQUIRE("restart-profile-custody", pwp_expected_file(profile_words, 6, root_words[1]));
    EXPECT("restart-composite-first-header",
        pwp_win_write_record(root, NAME(header_pending), NAME(header), header_copy.expected_count,
            copy_synthetic, &header_copy, 0), PWP_OK);
    REQUIRE("restart-header-copy-once", header_copy.calls == 1);
    EXPECT("restart-header-identity", pwp_win_file_identity(root, NAME(header), header_words), PWP_OK);
    REQUIRE("restart-header-custody", pwp_expected_file(header_words, 6, root_words[1]));
    EXPECT("restart-header-immediate-read", pwp_win_read(root, NAME(header), header_read.expected_count,
        receive_synthetic, &header_read), PWP_OK);
    REQUIRE("restart-header-immediate-bytes", header_read.calls == 1);
    EXPECT("restart-header-pending-observation", pwp_win_exists(root, NAME(header_pending), &exists), PWP_OK);
    REQUIRE("restart-header-pending-absent", !exists);
    EXPECT("restart-new-identity", pwp_win_create_child(root, NAME(identity), &id), PWP_OK);
    EXPECT("restart-identity-observation", pwp_win_identity(id, identity_words), PWP_OK);
    REQUIRE("restart-identity-custody", pwp_expected_child_directory(root_words, identity_words, 6));
    EXPECT("restart-new-vault-lock", pwp_win_create_vault_lock(id, &v), PWP_OK);
    EXPECT("restart-vault-identity", pwp_win_file_identity(id, NAME(vault), vault_words), PWP_OK);
    REQUIRE("restart-vault-custody", pwp_expected_file(vault_words, 6, identity_words[1]));
    EXPECT("restart-composite-first-record",
        pwp_win_write_record(id, NAME(record_pending), NAME(record), record_copy.expected_count,
            copy_synthetic, &record_copy, 0), PWP_OK);
    REQUIRE("restart-record-copy-once", record_copy.calls == 1);
    EXPECT("restart-record-identity", pwp_win_file_identity(id, NAME(record), record_words), PWP_OK);
    REQUIRE("restart-record-custody", pwp_expected_file(record_words, 6, identity_words[1]));
    EXPECT("restart-record-immediate-read", pwp_win_read(id, NAME(record), record_read.expected_count,
        receive_synthetic, &record_read), PWP_OK);
    REQUIRE("restart-record-immediate-bytes", record_read.calls == 1);
    EXPECT("restart-record-pending-observation", pwp_win_exists(id, NAME(record_pending), &exists), PWP_OK);
    REQUIRE("restart-record-pending-absent", !exists);
    EXPECT("restart-cold-identity-inventory", pwp_win_names(id, receive_restart_inventory, &identity_inventory), PWP_OK);
    REQUIRE("restart-cold-identity-inventory-once", identity_inventory.calls == 1);
    previous_root = root; previous_profile = p; previous_identity = id; previous_vault = v;
    EXPECT("restart-cold-vault-retirement", pwp_win_close(v), PWP_OK); v = 0;
    EXPECT("restart-cold-identity-retirement", pwp_win_close(id), PWP_OK); id = 0;
    EXPECT("restart-cold-root-inventory", pwp_win_names(root, receive_restart_inventory, &root_inventory), PWP_OK);
    REQUIRE("restart-cold-root-inventory-once", root_inventory.calls == 1);
    EXPECT("restart-cold-profile-retirement", pwp_win_close(p), PWP_OK); p = 0;
    root_close_attempted = 1;
    EXPECT("restart-cold-root-retirement", pwp_win_close(root), PWP_OK); root = 0;
    root_close_attempted = 0;

    EXPECT("restart-existing-bootstrap", pwp_win_open_root(&root), PWP_OK);
    REQUIRE("restart-fresh-root-owner", root > previous_root && root > previous_vault);
    EXPECT("restart-existing-root-identity", pwp_win_identity(root, observed), PWP_OK);
    REQUIRE("restart-same-root", memcmp(observed, root_words, sizeof(observed)) == 0);
    /* Read each empty lock before acquiring its share-none lease; never release/reopen a live lease for data. */
    EXPECT("restart-existing-profile-empty", pwp_win_read(root, NAME(profile), 0, receive_empty, &empty_read), PWP_OK);
    REQUIRE("restart-profile-empty-read-once", empty_read.calls == 1);
    EXPECT("restart-existing-profile-lock", pwp_win_lock(root, NAME(profile), &p), PWP_OK);
    REQUIRE("restart-fresh-profile-owner", p > previous_profile);
    EXPECT("restart-existing-profile-identity", pwp_win_file_identity(root, NAME(profile), observed), PWP_OK);
    REQUIRE("restart-same-profile-lock", memcmp(observed, profile_words, sizeof(observed)) == 0);
    EXPECT("restart-existing-root-inventory", pwp_win_names(root, receive_restart_inventory, &root_inventory), PWP_OK);
    REQUIRE("restart-existing-root-inventory-once", root_inventory.calls == 2);
    EXPECT("restart-existing-header-pending", pwp_win_exists(root, NAME(header_pending), &exists), PWP_OK);
    REQUIRE("restart-existing-header-pending-absent", !exists);
    EXPECT("restart-existing-identity", pwp_win_child(root, NAME(identity), &id), PWP_OK);
    REQUIRE("restart-fresh-identity-owner", id > previous_identity);
    EXPECT("restart-existing-identity-observation", pwp_win_identity(id, observed), PWP_OK);
    REQUIRE("restart-same-identity", memcmp(observed, identity_words, sizeof(observed)) == 0);
    EXPECT("restart-existing-vault-empty", pwp_win_read(id, NAME(vault), 0, receive_empty, &empty_read), PWP_OK);
    REQUIRE("restart-vault-empty-read-once", empty_read.calls == 2);
    EXPECT("restart-existing-vault-lock", pwp_win_lock(id, NAME(vault), &v), PWP_OK);
    REQUIRE("restart-fresh-vault-owner", v > previous_vault);
    EXPECT("restart-existing-vault-identity", pwp_win_file_identity(id, NAME(vault), observed), PWP_OK);
    REQUIRE("restart-same-vault-lock", memcmp(observed, vault_words, sizeof(observed)) == 0);
    EXPECT("restart-existing-identity-inventory", pwp_win_names(id, receive_restart_inventory, &identity_inventory), PWP_OK);
    REQUIRE("restart-existing-identity-inventory-once", identity_inventory.calls == 2);
    EXPECT("restart-existing-record-pending", pwp_win_exists(id, NAME(record_pending), &exists), PWP_OK);
    REQUIRE("restart-existing-record-pending-absent", !exists);
    EXPECT("restart-existing-identity-sync", pwp_win_sync_directory(id), PWP_OK);
    EXPECT("restart-post-sync-identity", pwp_win_identity(id, observed), PWP_OK);
    REQUIRE("restart-post-sync-same-identity", memcmp(observed, identity_words, sizeof(observed)) == 0);
    EXPECT("restart-post-sync-root", pwp_win_identity(root, observed), PWP_OK);
    REQUIRE("restart-post-sync-same-root", memcmp(observed, root_words, sizeof(observed)) == 0);
    inventory_vault = v;
    EXPECT("restart-inventory-vault-retirement", pwp_win_close(v), PWP_OK); v = 0;
    EXPECT("restart-existing-header-identity", pwp_win_file_identity(root, NAME(header), observed), PWP_OK);
    REQUIRE("restart-same-header", memcmp(observed, header_words, sizeof(observed)) == 0);
    EXPECT("restart-existing-header-read", pwp_win_read(root, NAME(header), header_read.expected_count,
        receive_synthetic, &header_read), PWP_OK);
    REQUIRE("restart-retained-header-bytes", header_read.calls == 2);
    EXPECT("restart-record-vault-empty", pwp_win_read(id, NAME(vault), 0, receive_empty, &empty_read), PWP_OK);
    REQUIRE("restart-record-vault-empty-read-once", empty_read.calls == 3);
    EXPECT("restart-record-vault-lock", pwp_win_lock(id, NAME(vault), &v), PWP_OK);
    REQUIRE("restart-fresh-record-vault-owner", v > inventory_vault);
    EXPECT("restart-record-vault-identity", pwp_win_file_identity(id, NAME(vault), observed), PWP_OK);
    REQUIRE("restart-same-record-vault-lock", memcmp(observed, vault_words, sizeof(observed)) == 0);
    EXPECT("restart-existing-record-identity", pwp_win_file_identity(id, NAME(record), observed), PWP_OK);
    REQUIRE("restart-same-record", memcmp(observed, record_words, sizeof(observed)) == 0);
    EXPECT("restart-existing-record-read", pwp_win_read(id, NAME(record), record_read.expected_count,
        receive_synthetic, &record_read), PWP_OK);
    REQUIRE("restart-retained-record-bytes", record_read.calls == 2);
    EXPECT("restart-existing-vault-retirement", pwp_win_close(v), PWP_OK); v = 0;
    EXPECT("restart-existing-identity-retirement", pwp_win_close(id), PWP_OK); id = 0;
    EXPECT("restart-existing-profile-retirement", pwp_win_close(p), PWP_OK); p = 0;
    root_close_attempted = 1;
    EXPECT("restart-existing-root-retirement", pwp_win_close(root), PWP_OK); root = 0;
    result = SMOKE_OK;
failed:
    if (root && !root_close_attempted) {
        /* One terminal drain owns all remaining original roles and unpublished results. No retry/reset. */
        root_close_attempted = 1;
        if (!expected("restart-terminal-cleanup", pwp_win_close(root), PWP_OK)) result = SMOKE_CLEANUP_UNKNOWN;
    }
    pwp_clear(root_words, sizeof(root_words)); pwp_clear(profile_words, sizeof(profile_words));
    pwp_clear(header_words, sizeof(header_words)); pwp_clear(identity_words, sizeof(identity_words));
    pwp_clear(vault_words, sizeof(vault_words)); pwp_clear(record_words, sizeof(record_words));
    pwp_clear(observed, sizeof(observed));
    return result;
}
int wmain(int argc, wchar_t **argv) {
    int restart = argc == 2 && wcscmp(argv[1], L"--disposable-custody-restart-smoke") == 0;
    if (argc != 2 || (!restart && wcscmp(argv[1], L"--disposable-custody-smoke") != 0)) {
        fputs("REFUSED explicit-disposable-custody-scope-required\n", stderr); return SMOKE_SCOPE;
    }
    (void)setvbuf(stdout, NULL, _IONBF, 0);
    watchdog owner;
    if (!watchdog_start(&owner, restart ? RESTART_SMOKE_DEADLINE_MS : SMOKE_DEADLINE_MS)) return SMOKE_CLEANUP_UNKNOWN;
    int result = standard_user();
    if (result == SMOKE_OK) result = no_existing_application_tree();
    if (result == SMOKE_OK) {
        if (restart) {
            puts("SCOPE cold-composite-write-session-reopen-only; NOT crash/encrypted-profile/JNI/loader/MSI qualification");
            result = run_restart_controls();
        } else {
            puts("SCOPE real-native-custody-smoke-only; NOT transactions/JNI/loader/MSI qualification");
            result = run_controls();
        }
    } else printf("REFUSED preflight-code=%d\n", result);
    printf("RESULT code=%d; canonical-fixtures-retained; exit-zero-required\n", result);
    if (!watchdog_finish(&owner)) return SMOKE_CLEANUP_UNKNOWN;
    return result;
}
