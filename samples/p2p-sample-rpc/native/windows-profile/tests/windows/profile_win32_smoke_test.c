/* Test-only real Windows custody smoke. Never compile against fake Windows headers or a mock backend.
 * EXTERNAL prerequisite: a newly disposable standard-user account/VM, with no concurrent P2pKit activity.
 * The flag/preflight cannot prove disposability. No canonical fixture is deleted/reset/repaired afterward. */
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
typedef struct { owned_handle event, thread; ULONGLONG started; } watchdog;
static void deadline_exit(void) {
    /* No stdio/locks before termination: even logging to a blocked pipe must not defeat this deadline.
     * Exit125 is failed, unproven cleanup, NOT successful native cancellation or a cleanup receipt. */
    (void)TerminateProcess(GetCurrentProcess(), SMOKE_DEADLINE_UNKNOWN);
    __fastfail(FAST_FAIL_FATAL_APP_EXIT);
}
static DWORD WINAPI watchdog_wait(void *opaque) {
    watchdog *owner = opaque;
    ULONGLONG elapsed = GetTickCount64()-owner->started;
    if (elapsed >= SMOKE_DEADLINE_MS) deadline_exit();
    DWORD result = WaitForSingleObject(owner->event.handle, (DWORD)(SMOKE_DEADLINE_MS-elapsed));
    if (result != WAIT_OBJECT_0 || GetTickCount64()-owner->started >= SMOKE_DEADLINE_MS) deadline_exit();
    return 0;
}
static int watchdog_start(watchdog *owner) {
    memset(owner, 0, sizeof(*owner)); owner->started = GetTickCount64();
    owner->event.handle = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!owner->event.handle) return 0;
    owner->thread.handle = CreateThread(NULL, 0, watchdog_wait, owner, 0, NULL);
    if (!owner->thread.handle) { (void)close_owned(&owner->event); return 0; }
    return 1;
}
static int watchdog_finish(watchdog *owner) {
    ULONGLONG elapsed = GetTickCount64()-owner->started;
    if (elapsed >= SMOKE_DEADLINE_MS || !SetEvent(owner->event.handle)) deadline_exit();
    DWORD waited = WaitForSingleObject(owner->thread.handle, (DWORD)(SMOKE_DEADLINE_MS-elapsed));
    if (waited != WAIT_OBJECT_0 || GetTickCount64()-owner->started >= SMOKE_DEADLINE_MS) deadline_exit();
    /* The required external owner bounds these final closes and CRT/process exit after this thread joined. */
    int thread_closed = close_owned(&owner->thread);
    int event_closed = close_owned(&owner->event); /* Independent release despite earlier uncertainty. */
    if (GetTickCount64()-owner->started >= SMOKE_DEADLINE_MS) deadline_exit();
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
static int run_controls(void) {
    static const WCHAR profile[] = L"profile.lock", vault[] = L"vault.lock", identity[] = L"identity";
    static const WCHAR identity_alias[] = L"IDENTITY", other[] = L"other.lock", child_other[] = L"other";
    WCHAR stage_name[STAGE_COMPONENT_CAPACITY], root_stage_name[STAGE_COMPONENT_CAPACITY];
    WCHAR candidate_name[CANDIDATE_COMPONENT_CAPACITY];
    uint64_t root = 0, p = 0, id = 0, v = 0, s = 0, outer = 0, rejected = 0;
    uint64_t root_words[6] = {0}, profile_words[6] = {0}, observed[6] = {0};
    int exists = 0, result = SMOKE_CONTROL; bytes_control copy = {0, 1}, read = {0, 0};
    REQUIRE("initial-stage-name", stage_component(stage_name, 0));
    REQUIRE("initial-root-stage-name", stage_component(root_stage_name, 10));
    REQUIRE("initial-candidate-name", candidate_component(candidate_name, 0));
    EXPECT("bootstrap", pwp_win_open_root(&root), PWP_OK);
    REQUIRE("root-token", pwp_token_valid(root));
    EXPECT("root-observation", pwp_win_identity(root, root_words), PWP_OK);
    REQUIRE("root-custody-shape", directory_words(root_words));
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
    EXPECT("wrong-lock-name", pwp_win_lock(root, NAME(other), &rejected), PWP_POLICY);
    EXPECT("wrong-vault-scope", pwp_win_lock(root, NAME(vault), &rejected), PWP_POLICY);
    EXPECT("open-missing-lock-no-create", pwp_win_lock(root, NAME(profile), &rejected), PWP_NOT_FOUND);
    EXPECT("profile-create", pwp_win_create_profile_lock(root, &p), PWP_OK);
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
    EXPECT("vault-create", pwp_win_create_vault_lock(id, &v), PWP_OK);
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
    uint64_t old_root = root; root = 0;
    EXPECT("owned-session-reopen", pwp_win_open_root(&root), PWP_OK);
    REQUIRE("root-token-not-reused", root > old_root);
    EXPECT("reopened-root-observation", pwp_win_identity(root, observed), PWP_OK);
    REQUIRE("same-owned-root-preserved", memcmp(observed, root_words, sizeof(observed)) == 0);
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
    pwp_clear(observed, sizeof(observed));
    return result;
}
int wmain(int argc, wchar_t **argv) {
    if (argc != 2 || wcscmp(argv[1], L"--disposable-custody-smoke") != 0) {
        fputs("REFUSED explicit-disposable-custody-scope-required\n", stderr); return SMOKE_SCOPE;
    }
    (void)setvbuf(stdout, NULL, _IONBF, 0);
    watchdog owner;
    if (!watchdog_start(&owner)) return SMOKE_CLEANUP_UNKNOWN;
    int result = standard_user();
    if (result == SMOKE_OK) result = no_existing_application_tree();
    if (result == SMOKE_OK) {
        puts("SCOPE real-native-custody-smoke-only; NOT transactions/JNI/loader/MSI qualification");
        result = run_controls();
    } else printf("REFUSED preflight-code=%d\n", result);
    printf("RESULT code=%d; canonical-fixtures-retained; exit-zero-required\n", result);
    if (!watchdog_finish(&owner)) return SMOKE_CLEANUP_UNKNOWN;
    return result;
}
