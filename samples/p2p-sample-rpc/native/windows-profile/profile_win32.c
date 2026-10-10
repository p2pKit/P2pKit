/* Windows x64 only. This file must be built with the real Windows SDK, never fake Windows headers. */
#if !defined(_WIN32) || !defined(_M_X64)
#error Windows x64 SDK/compiler required; no host emulation or portable filesystem fallback.
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winternl.h>
#include <aclapi.h>
#include <shlobj.h>
#include <stdint.h>
#include <string.h>
#include "profile_win32.h"

/* Static imports are exclusively Windows system KnownDLLs; no cwd search or dynamically named DLL. */
#pragma comment(lib, "advapi32.lib")
#pragma comment(lib, "kernel32.lib")
#pragma comment(lib, "ntdll.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "uuid.lib")

_Static_assert(sizeof(void *) == 8 && sizeof(WCHAR) == 2, "Windows x64 ABI required");
_Static_assert(sizeof(FILE_ID_INFO) == 24 && sizeof(IO_STATUS_BLOCK) == 16, "Unexpected Windows SDK ABI");
_Static_assert(sizeof(FILE_CASE_SENSITIVE_INFO) == 4 && offsetof(FILE_CASE_SENSITIVE_INFO, Flags) == 0,
               "Unexpected directory case-policy ABI");
_Static_assert(offsetof(FILE_ID_BOTH_DIR_INFO, FileName) == 104 &&
               offsetof(FILE_ID_BOTH_DIR_INFO, FileNameLength) == 60 &&
               offsetof(FILE_ID_BOTH_DIR_INFO, EndOfFile) == 40, "Unexpected directory-buffer ABI");
#define PWP_FILE_OPEN 1u
#define PWP_FILE_CREATE 2u
#define PWP_FILE_DIRECTORY 1u
#define PWP_FILE_NON_DIRECTORY 0x40u
#define PWP_FILE_SYNCHRONOUS 0x20u
#define PWP_FILE_REPARSE 0x00200000u
#define PWP_FILE_DELETE_ON_CLOSE 0x00001000u

typedef struct {
    uint64_t token, parent;
    WCHAR path[PWP_PATH_LIMIT];
    uint64_t identity[PWP_IDENTITY_WORDS];
    int directory, public_handle;
    pwp_stage stage;
    int stage_created, stage_validated;
} pwp_entry;
typedef struct {
    pwp_owner owner;
    pwp_entry entries[PWP_HANDLE_LIMIT];
    unsigned char user[SECURITY_MAX_SID_SIZE], system[SECURITY_MAX_SID_SIZE];
    DWORD user_length;
    uint64_t root;
    PSECURITY_DESCRIPTOR failed_security_descriptor;
    pwp_result terminal;
    int initialized, active, failed;
} pwp_context;
static SRWLOCK gate = SRWLOCK_INIT;
static pwp_context state;

static int close_os(uintptr_t raw, void *unused);
static pwp_result retire(uint64_t token) {
    pwp_result r = pwp_retire(&state.owner, token, close_os, NULL);
    if (r != PWP_OK) state.failed = 1;
    return r;
}
static pwp_result end(pwp_result result) { ReleaseSRWLockExclusive(&gate); return result; }
static pwp_result begin(void) {
    if (!TryAcquireSRWLockExclusive(&gate)) return PWP_BUSY;
    if (!state.active || state.failed || state.owner.poisoned) return end(PWP_CLOSED);
    return PWP_OK;
}
static pwp_entry *entry(uint64_t token) {
    pwp_owned_handle *h = pwp_lookup(&state.owner, token);
    if (!h || h->state != 2) return NULL;
    size_t slot = (size_t)(h-state.owner.slots);
    return state.entries[slot].token == token ? &state.entries[slot] : NULL;
}
static HANDLE raw(uint64_t token) {
    pwp_owned_handle *h = pwp_lookup(&state.owner, token);
    return h && h->state == 2 ? (HANDLE)h->resource : NULL;
}
static pwp_result reserve(uint64_t *token) {
    pwp_result r = pwp_reserve(&state.owner, token);
    if (r == PWP_OK) {
        pwp_owned_handle *h = pwp_lookup(&state.owner, *token);
        memset(&state.entries[h-state.owner.slots], 0, sizeof(pwp_entry));
    }
    return r;
}
/* Reserve before allocation, so every unpublished/failed result remains in the owning registry. */
static pwp_result attach(uint64_t token, HANDLE handle) {
    if (!handle || handle == INVALID_HANDLE_VALUE) return PWP_OS;
    return pwp_attach(&state.owner, token, (uintptr_t)handle);
}
static int no_impersonation(void) {
    HANDLE token = NULL;
    uint64_t owned = 0;
    if (reserve(&owned) != PWP_OK) return 0;
    if (OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, TRUE, &token)) {
        if (attach(owned, token) != PWP_OK) state.failed = 1;
        (void)retire(owned);
        return 0;
    }
    DWORD error = GetLastError();
    return retire(owned) == PWP_OK && error == ERROR_NO_TOKEN;
}
static int process_user(void) {
    if (!no_impersonation()) return 0;
    USHORT process_machine = 0, native_machine = 0;
    if (!IsWow64Process2(GetCurrentProcess(), &process_machine, &native_machine) ||
        process_machine != IMAGE_FILE_MACHINE_UNKNOWN || native_machine != IMAGE_FILE_MACHINE_AMD64) return 0;
    uint64_t owned = 0;
    HANDLE token = NULL;
    if (reserve(&owned) != PWP_OK) return 0;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) { (void)retire(owned); return 0; }
    if (attach(owned, token) != PWP_OK) { state.failed = 1; return 0; }
    _Alignas(void *) unsigned char user_buffer[4096], owner_buffer[4096];
    DWORD user_size = 0, owner_size = 0;
    int ok = GetTokenInformation(token, TokenUser, user_buffer, sizeof(user_buffer), &user_size) &&
        GetTokenInformation(token, TokenOwner, owner_buffer, sizeof(owner_buffer), &owner_size);
    if (ok) {
        PSID user = ((TOKEN_USER *)user_buffer)->User.Sid, owner = ((TOKEN_OWNER *)owner_buffer)->Owner;
        ok = IsValidSid(user) && IsValidSid(owner) && EqualSid(user, owner) &&
            !IsWellKnownSid(user, WinLocalSystemSid) && !IsWellKnownSid(user, WinBuiltinAdministratorsSid) &&
            GetLengthSid(user) <= sizeof(state.user);
        if (ok) {
            state.user_length = GetLengthSid(user);
            ok = CopySid(sizeof(state.user), state.user, user);
        }
    }
    DWORD system_size = sizeof(state.system);
    if (ok) ok = CreateWellKnownSid(WinLocalSystemSid, NULL, state.system, &system_size);
    pwp_clear(user_buffer, sizeof(user_buffer)); pwp_clear(owner_buffer, sizeof(owner_buffer));
    return retire(owned) == PWP_OK && ok;
}
static int security_descriptor(SECURITY_DESCRIPTOR *sd, ACL *acl, DWORD size, int directory) {
    DWORD inheritance = directory ? OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE : 0;
    return InitializeSecurityDescriptor(sd, SECURITY_DESCRIPTOR_REVISION) &&
        SetSecurityDescriptorOwner(sd, state.user, FALSE) && InitializeAcl(acl, size, ACL_REVISION) &&
        AddAccessAllowedAceEx(acl, ACL_REVISION, inheritance, FILE_ALL_ACCESS, state.user) &&
        AddAccessAllowedAceEx(acl, ACL_REVISION, inheritance, FILE_ALL_ACCESS, state.system) &&
        SetSecurityDescriptorDacl(sd, TRUE, acl, FALSE) &&
        SetSecurityDescriptorControl(sd, SE_DACL_PROTECTED, SE_DACL_PROTECTED);
}
static int private_security(HANDLE handle, int directory) {
    PSECURITY_DESCRIPTOR sd = NULL;
    PSID owner = NULL;
    PACL acl = NULL;
    if (GetSecurityInfo(handle, SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
                        &owner, NULL, &acl, NULL, &sd) != ERROR_SUCCESS) return 0;
    SECURITY_DESCRIPTOR_CONTROL control = 0;
    DWORD revision = 0;
    ACL_SIZE_INFORMATION size = {0};
    int ok = owner && acl && IsValidSid(owner) && IsValidAcl(acl) &&
        GetSecurityDescriptorControl(sd, &control, &revision) &&
        GetAclInformation(acl, &size, sizeof(size), AclSizeInformation) &&
        size.AceCount == 2 && size.AclBytesInUse <= 1024;
    uint8_t types[2] = {0}, flags[2] = {0}; uint32_t masks[2] = {0}; int sid_kind[2] = {0};
    for (DWORD i = 0; ok && i < 2; ++i) {
        ACCESS_ALLOWED_ACE *ace = NULL;
        ok = GetAce(acl, i, (void **)&ace) && ace && ace->Header.AceType == ACCESS_ALLOWED_ACE_TYPE &&
            ace->Header.AceSize >= 16 && ace->Header.AceSize <= 8+SECURITY_MAX_SID_SIZE;
        if (!ok) break;
        PSID sid = &ace->SidStart;
        ok = IsValidSid(sid) && GetLengthSid(sid)+8 == ace->Header.AceSize;
        if (!ok) break;
        types[i] = ace->Header.AceType; flags[i] = ace->Header.AceFlags; masks[i] = ace->Mask;
        sid_kind[i] = EqualSid(sid, state.user) ? 1 : EqualSid(sid, state.system) ? 2 : 0;
    }
    if (ok) ok = pwp_acl_shape(control, revision, size.AceCount, types, flags, masks,
                               EqualSid(owner, state.user), sid_kind, directory);
    /* LocalFree failure is unexpected; retain the pointer and poison rather than report safe cleanup. */
    if (LocalFree(sd)) { state.failed_security_descriptor = sd; state.failed = 1; return 0; }
    return ok;
}
static int inspect_mode(HANDLE handle, const WCHAR *path, int directory, int private_file,
                         int disposable_stage, uint64_t words[6]) {
    FILE_ID_INFO id; FILE_BASIC_INFO basic; FILE_STANDARD_INFO standard; DWORD flags = 0;
    if (GetFileType(handle) != FILE_TYPE_DISK || !GetHandleInformation(handle, &flags) ||
        (flags & HANDLE_FLAG_INHERIT) ||
        !GetFileInformationByHandleEx(handle, FileIdInfo, &id, sizeof(id)) ||
        !GetFileInformationByHandleEx(handle, FileBasicInfo, &basic, sizeof(basic)) ||
        !GetFileInformationByHandleEx(handle, FileStandardInfo, &standard, sizeof(standard)) ||
        (standard.DeletePending && !disposable_stage) || !!standard.Directory != directory ||
        !!(basic.FileAttributes & FILE_ATTRIBUTE_DIRECTORY) != directory ||
        (basic.FileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE)) ||
        standard.EndOfFile.QuadPart < 0 || (private_file && standard.NumberOfLinks != 1) ||
        !id.VolumeSerialNumber || (private_file && !directory &&
            (uint64_t)standard.EndOfFile.QuadPart > PWP_RECORD_LIMIT)) return 0;
    if (directory) {
        /* ASCII-folded final paths and borrowed owned-file metadata require an insensitive namespace.
         * Query this exact held handle on every admission/readback, including all pinned ancestors.
         * Unsupported/query failure and every nonzero flag reject; never change directory settings. */
        FILE_CASE_SENSITIVE_INFO case_info = {0};
        int queried = GetFileInformationByHandleEx(handle, FileCaseSensitiveInfo,
                                                   &case_info, sizeof(case_info)) != 0;
        if (!pwp_directory_case_policy(queried, case_info.Flags)) return 0;
    }
    WCHAR final[PWP_PATH_LIMIT];
    DWORD length = GetFinalPathNameByHandleW(handle, final, PWP_PATH_LIMIT, FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
    if (!length || length >= PWP_PATH_LIMIT ||
        !pwp_final_path((const uint16_t *)path, wcslen(path), (const uint16_t *)final, length)) return 0;
    WCHAR filesystem[32]; DWORD volume_flags = 0;
    if (!GetVolumeInformationByHandleW(handle, NULL, 0, NULL, NULL, &volume_flags, filesystem, 32) ||
        wcscmp(filesystem, L"NTFS") || !(volume_flags & FILE_PERSISTENT_ACLS) ||
        !(volume_flags & FILE_NAMED_STREAMS)) return 0;
    if (private_file) {
        if (!private_security(handle, directory)) return 0;
        _Alignas(8) unsigned char streams[4096];
        if (!GetFileInformationByHandleEx(handle, FileStreamInfo, streams, sizeof(streams))) {
            if (GetLastError() != ERROR_HANDLE_EOF || !directory || standard.EndOfFile.QuadPart != 0) return 0;
        } else if (!pwp_stream_record(streams, sizeof(streams), (uint64_t)standard.EndOfFile.QuadPart, directory)) return 0;
    }
    uint64_t high = 0, low = 0;
    memcpy(&low, id.FileId.Identifier, 8); memcpy(&high, id.FileId.Identifier+8, 8);
    if (!low && !high) return 0;
    words[0] = 1; words[1] = id.VolumeSerialNumber; words[2] = high; words[3] = low;
    /* Disposable-stage/deletion-pending inspection has no normal-record claims. Zero flags are internal only. */
    words[4] = disposable_stage ? 0 : directory ? 0x1ff : 0x2ff; words[5] = standard.NumberOfLinks;
    return 1;
}
static int inspect(HANDLE handle, const WCHAR *path, int directory, int private_file, uint64_t words[6]) {
    return inspect_mode(handle, path, directory, private_file, 0, words);
}
static pwp_result open_relative_access(uint64_t parent, const WCHAR *name, size_t length,
                                 const WCHAR *path, int directory, int create, int lock_file,
                                 int private_file, int delete_file, uint64_t *output) {
    if ((delete_file && (directory != 0 || create || lock_file || !private_file)) ||
        !path || !name || !length || length > 255 || (directory < 0 && create) ||
        wcsnlen_s(path, PWP_PATH_LIMIT) >= PWP_PATH_LIMIT)
        return PWP_ARGUMENT;
    uint64_t owned = 0;
    pwp_result r = reserve(&owned);
    if (r != PWP_OK) return r;
    HANDLE handle = NULL;
    UNICODE_STRING text = {(USHORT)(length*2), (USHORT)(length*2), (PWSTR)name};
    _Alignas(void *) unsigned char acl_buffer[256];
    SECURITY_DESCRIPTOR sd;
    if (create && !security_descriptor(&sd, (ACL *)acl_buffer, sizeof(acl_buffer), directory))
        return retire(owned) == PWP_OK ? PWP_OS : PWP_CLEANUP_UNKNOWN;
    OBJECT_ATTRIBUTES attributes;
    InitializeObjectAttributes(&attributes, &text, OBJ_CASE_INSENSITIVE, raw(parent), create ? &sd : NULL);
    IO_STATUS_BLOCK io = {0};
    ACCESS_MASK access = READ_CONTROL | FILE_READ_ATTRIBUTES | SYNCHRONIZE |
        (directory < 0 ? 0 : directory ? FILE_LIST_DIRECTORY | FILE_TRAVERSE : FILE_READ_DATA) |
        (lock_file ? FILE_WRITE_DATA : 0) | (delete_file ? DELETE : 0);
    NTSTATUS status = NtCreateFile(&handle, access, &attributes, &io, NULL, FILE_ATTRIBUTE_NORMAL,
        (lock_file || delete_file) ? 0 : FILE_SHARE_READ, create ? PWP_FILE_CREATE : PWP_FILE_OPEN,
        PWP_FILE_REPARSE | PWP_FILE_SYNCHRONOUS |
        (directory < 0 ? 0 : directory ? PWP_FILE_DIRECTORY : PWP_FILE_NON_DIRECTORY), NULL, 0);
    if (handle && handle != INVALID_HANDLE_VALUE && attach(owned, handle) != PWP_OK) {
        state.failed = 1; return PWP_CLEANUP_UNKNOWN;
    }
    if (status != 0 || io.Information != (create ? 2u : 1u) || !raw(owned)) {
        DWORD error = RtlNtStatusToDosError(status);
        if (retire(owned) != PWP_OK) return PWP_CLEANUP_UNKNOWN;
        return error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND ? PWP_NOT_FOUND : PWP_OS;
    }
    if (directory < 0) {
        FILE_STANDARD_INFO kind;
        if (!GetFileInformationByHandleEx(handle, FileStandardInfo, &kind, sizeof(kind)))
            return retire(owned) == PWP_OK ? PWP_OS : PWP_CLEANUP_UNKNOWN;
        directory = !!kind.Directory;
    }
    pwp_owned_handle *h = pwp_lookup(&state.owner, owned);
    pwp_entry *e = &state.entries[h-state.owner.slots];
    e->token = owned; e->parent = parent; e->directory = directory;
    wcscpy_s(e->path, PWP_PATH_LIMIT, path);
    if (!inspect(handle, path, directory, private_file, e->identity)) {
        if (retire(owned) != PWP_OK) return PWP_CLEANUP_UNKNOWN;
        return PWP_POLICY;
    }
    *output = owned; return PWP_OK;
}
/* Preserve all existing callers' exact access/share/create semantics. */
static pwp_result open_relative(uint64_t parent, const WCHAR *name, size_t length,
                                 const WCHAR *path, int directory, int create, int lock_file,
                                 int private_file, uint64_t *output) {
    return open_relative_access(parent, name, length, path, directory, create, lock_file, private_file, 0, output);
}
static int verify(pwp_entry *e) {
    uint64_t observed[6];
    return e && pwp_regular_metadata(e->stage.phase) && no_impersonation() &&
        inspect(raw(e->token), e->path, e->directory, 1, observed) &&
        memcmp(observed, e->identity, sizeof(observed)) == 0;
}
static int same_path(const WCHAR *a, const WCHAR *b) {
    for (size_t i = 0; i < PWP_PATH_LIMIT; ++i) {
        WCHAR x = a[i], y = b[i];
        if (x >= L'A' && x <= L'Z') x = (WCHAR)(x+32);
        if (y >= L'A' && y <= L'Z') y = (WCHAR)(y+32);
        if (x != y) return 0;
        if (!x) return 1;
    }
    return 0;
}
/* Do not reopen a share-none lease against ourselves, and never temporarily release it for metadata. */
static pwp_entry *owned_file(uint64_t parent, const WCHAR *path) {
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        pwp_entry *e = &state.entries[i];
        if (state.owner.slots[i].state == 2 && e->public_handle && !e->directory &&
            e->parent == parent && same_path(e->path, path)) return e;
    }
    return NULL;
}
static int join_name(pwp_entry *parent, const uint16_t *name, size_t length, WCHAR *path) {
    if (!parent || !parent->directory || !pwp_component(name, length)) return 0;
    size_t count = wcslen(parent->path);
    if (count+length+2 > PWP_PATH_LIMIT) return 0;
    memcpy(path, parent->path, count*sizeof(WCHAR)); path[count++] = L'\\';
    memcpy(path+count, name, length*sizeof(WCHAR)); path[count+length] = 0; return 1;
}
typedef struct { pwp_entry *entry; HANDLE handle; } pwp_stage_context;
static int stage_check(size_t expected_size, void *context) {
    pwp_stage_context *c = context; uint64_t observed[6]; FILE_STANDARD_INFO size;
    pwp_entry *parent = entry(c->entry->parent);
    return c->entry->stage_created && c->entry->stage_validated && verify(parent) && no_impersonation() &&
        inspect_mode(c->handle, c->entry->path, 0, 1, 1, observed) &&
        memcmp(observed, c->entry->identity, sizeof(observed)) == 0 &&
        GetFileInformationByHandleEx(c->handle, FileStandardInfo, &size, sizeof(size)) &&
        size.EndOfFile.QuadPart >= 0 && (uint64_t)size.EndOfFile.QuadPart == expected_size;
}
static int stage_write(const unsigned char *bytes, size_t length, size_t *written, void *context) {
    pwp_stage_context *c = context; DWORD actual = 0;
    if (!written || !length || length > 65536) return 0;
    int ok = WriteFile(c->handle, bytes, (DWORD)length, &actual, NULL) != 0;
    *written = actual; return ok;
}
static int stage_flush(void *context) {
    pwp_stage_context *c = context; return FlushFileBuffers(c->handle) != 0;
}
static int stage_mark_delete(void *context) {
    pwp_stage_context *c = context;
    /* Before publication, FILE_CREATE + FILE_CREATED is custody of this exact newly allocated object.
     * After validation, also re-prove its original ID/ACL. Never open/delete an existing path for cleanup. */
    /* A prior custody failure must not allocate/reinspect more security descriptors during cleanup.
     * CloseHandle still runs on the original delete-on-close handle, but cleanup stays unproven. */
    if (!c->entry->stage_created || state.failed || state.owner.poisoned) return 0;
    if (c->entry->stage_validated) {
        uint64_t observed[6];
        if (!no_impersonation() || !inspect_mode(c->handle, c->entry->path, 0, 1, 1, observed) ||
            memcmp(observed, c->entry->identity, sizeof(observed)) != 0) return 0;
    }
    FILE_DISPOSITION_INFO disposition = {TRUE}; FILE_STANDARD_INFO after;
    return SetFileInformationByHandle(c->handle, FileDispositionInfo, &disposition, sizeof(disposition)) &&
        GetFileInformationByHandleEx(c->handle, FileStandardInfo, &after, sizeof(after)) && after.DeletePending;
}
static int stage_close_handle(void *context) {
    pwp_stage_context *c = context; return CloseHandle(c->handle) != 0;
}
static int close_os(uintptr_t resource, void *unused) {
    (void)unused;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        pwp_entry *e = &state.entries[i];
        if (state.owner.slots[i].resource == resource && state.owner.slots[i].state == 4 &&
            e->token == state.owner.slots[i].token && e->stage.phase != PWP_STAGE_EMPTY) {
            pwp_stage_context context = {e, (HANDLE)resource};
            return pwp_stage_discard(&e->stage, stage_mark_delete, stage_close_handle, &context) == PWP_OK;
        }
    }
    return CloseHandle((HANDLE)resource) != 0;
}
static pwp_result end_stage(pwp_result result) {
    /* Security-descriptor/other custody cleanup can fail independently of the stage's CloseHandle. */
    return end(state.failed || state.owner.poisoned ? PWP_CLEANUP_UNKNOWN : result);
}
/* This is NOT a record write/commit. The original handle is delete-on-close from creation, share-none,
 * never renameable by this component, and remains registered until explicit discard or session close. */
pwp_result pwp_win_stage(uint64_t directory, const uint16_t *name, size_t length,
                         const unsigned char *bytes, size_t count, uint64_t *output) {
    if (!output) return PWP_ARGUMENT;
    *output = 0;
    if ((!bytes && count) || count > PWP_RECORD_LIMIT || !pwp_stage_name(name, length)) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *parent = entry(directory); WCHAR path[PWP_PATH_LIMIT];
    if (!parent || !parent->public_handle || !verify(parent) || !join_name(parent, name, length, path))
        return end_stage(PWP_POLICY);
    if (pwp_public_count(&state.owner) >= PWP_PUBLIC_HANDLE_LIMIT) return end_stage(PWP_LIMIT);
    uint64_t token = 0; r = reserve(&token); if (r != PWP_OK) return end_stage(r);
    _Alignas(void *) unsigned char acl_buffer[256]; SECURITY_DESCRIPTOR sd;
    if (!security_descriptor(&sd, (ACL *)acl_buffer, sizeof(acl_buffer), 0)) {
        r = retire(token); return end_stage(r == PWP_OK ? PWP_OS : r);
    }
    UNICODE_STRING text = {(USHORT)(length*2), (USHORT)(length*2), (PWSTR)name};
    OBJECT_ATTRIBUTES attributes;
    InitializeObjectAttributes(&attributes, &text, OBJ_CASE_INSENSITIVE, raw(directory), &sd);
    IO_STATUS_BLOCK io = {0}; HANDLE handle = NULL;
    NTSTATUS status = NtCreateFile(&handle, READ_CONTROL | FILE_READ_ATTRIBUTES | FILE_READ_DATA |
        FILE_WRITE_DATA | DELETE | SYNCHRONIZE, &attributes, &io, NULL, FILE_ATTRIBUTE_NORMAL, 0,
        PWP_FILE_CREATE, PWP_FILE_REPARSE | PWP_FILE_SYNCHRONOUS | PWP_FILE_NON_DIRECTORY |
        PWP_FILE_DELETE_ON_CLOSE, NULL, 0);
    if (handle && handle != INVALID_HANDLE_VALUE && attach(token, handle) != PWP_OK) {
        state.failed = 1; return end_stage(PWP_CLEANUP_UNKNOWN);
    }
    if (raw(token)) {
        pwp_owned_handle *h = pwp_lookup(&state.owner, token);
        pwp_entry *e = &state.entries[h-state.owner.slots];
        e->token = token; e->parent = directory; wcscpy_s(e->path, PWP_PATH_LIMIT, path);
        (void)pwp_stage_init(&e->stage);
        e->stage_created = status == 0 && io.Information == 2;
    }
    if (status != 0 || io.Information != 2 || !raw(token)) {
        r = retire(token); return end_stage(r == PWP_OK ? PWP_OS : r);
    }
    pwp_entry *e = entry(token);
    if (!inspect_mode(handle, path, 0, 1, 1, e->identity)) {
        r = retire(token); return end_stage(r == PWP_OK ? PWP_POLICY : r);
    }
    e->stage_validated = 1;
    pwp_stage_context context = {e, handle};
    r = pwp_stage_fill(&e->stage, bytes, count, stage_write, stage_flush, stage_check, &context);
    if (r == PWP_OK) r = pwp_publish(&state.owner, token);
    if (r != PWP_OK) {
        pwp_result cleanup = retire(token); return end_stage(cleanup == PWP_OK ? r : cleanup);
    }
    e->public_handle = 1; *output = token; return end_stage(PWP_OK);
}
pwp_result pwp_win_discard_stage(uint64_t token) {
    if (!pwp_token_valid(token)) return PWP_ARGUMENT;
    AcquireSRWLockExclusive(&gate); /* Exact close must join the original operation even after ordinary admission seals. */
    pwp_owned_handle *h = pwp_lookup(&state.owner, token);
    if (!h || state.entries[h-state.owner.slots].token != token ||
        state.entries[h-state.owner.slots].stage.phase == PWP_STAGE_EMPTY) return end(PWP_ARGUMENT);
    return end(retire(token));
}
pwp_result pwp_win_open_root(uint64_t *output) {
    if (!output) return PWP_ARGUMENT;
    *output = 0;
    if (!TryAcquireSRWLockExclusive(&gate)) return PWP_BUSY;
    if (!state.initialized) { pwp_owner_init(&state.owner); state.initialized = 1; }
    if (state.active || state.failed || state.owner.poisoned) return end(PWP_CLOSED);
    pwp_result result = PWP_POLICY;
    PWSTR known = NULL;
    if (!process_user()) goto failed;
    if (SHGetKnownFolderPath(&FOLDERID_LocalAppData, KF_FLAG_DONT_VERIFY, NULL, &known) != S_OK || !known) goto failed;
    size_t length = wcsnlen_s(known, PWP_PATH_LIMIT);
    if (!pwp_absolute_path((const uint16_t *)known, length)) goto failed;
    WCHAR drive[] = {known[0], L':', L'\\', 0};
    if (GetDriveTypeW(drive) != DRIVE_FIXED) goto failed;
    WCHAR drive_path[] = {L'\\', L'\\', L'?', L'\\', known[0], L':', L'\\', 0};
    uint64_t parent = 0;
    if (reserve(&parent) != PWP_OK) goto failed;
    HANDLE volume = CreateFileW(drive_path, READ_CONTROL | FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY |
        FILE_TRAVERSE | SYNCHRONIZE, FILE_SHARE_READ, NULL, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (attach(parent, volume) != PWP_OK) goto failed;
    uint64_t ignored[6];
    if (!inspect(volume, drive, 1, 0, ignored)) goto failed;
    WCHAR current[PWP_PATH_LIMIT]; wcscpy_s(current, PWP_PATH_LIMIT, drive);
    size_t start = 3;
    for (size_t i = 3; i <= length; ++i) if (i == length || known[i] == L'\\') {
        memcpy(current, known, i*sizeof(WCHAR)); current[i] = 0;
        uint64_t child = 0;
        result = open_relative(parent, known+start, i-start, current, 1, 0, 0, 0, &child);
        if (result != PWP_OK) goto failed;
        parent = child; start = i+1;
    }
    const WCHAR *parts[2] = {L"P2pKit", L"RpcProfile"};
    for (size_t i = 0; i < 2; ++i) {
        if (!pwp_append_path((uint16_t *)current, PWP_PATH_LIMIT,
                             (const uint16_t *)parts[i], wcslen(parts[i]))) { result = PWP_LIMIT; goto failed; }
        uint64_t child = 0;
        result = open_relative(parent, parts[i], wcslen(parts[i]), current, 1, 0, 0, 1, &child);
        if (result == PWP_NOT_FOUND)
            result = open_relative(parent, parts[i], wcslen(parts[i]), current, 1, 1, 0, 1, &child);
        if (result != PWP_OK) goto failed;
        parent = child;
    }
    CoTaskMemFree(known); known = NULL;
    result = pwp_publish(&state.owner, parent);
    if (result != PWP_OK) goto failed;
    state.root = parent; state.active = 1; entry(parent)->public_handle = 1;
    *output = parent; return end(PWP_OK);
failed:
    if (known) CoTaskMemFree(known);
    if (pwp_retire_all(&state.owner, close_os, NULL) != PWP_OK) { state.failed = 1; result = PWP_CLEANUP_UNKNOWN; }
    if (state.failed && result != PWP_CLEANUP_UNKNOWN) result = PWP_CLEANUP_UNKNOWN;
    return end(result == PWP_OK ? PWP_POLICY : result);
}
pwp_result pwp_win_child(uint64_t parent, const uint16_t *name, size_t length, uint64_t *child) {
    if (!child) return PWP_ARGUMENT;
    *child = 0;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(parent); WCHAR path[PWP_PATH_LIMIT];
    if (!p || !p->public_handle || !verify(p) || !join_name(p, name, length, path)) return end(PWP_POLICY);
    if (pwp_public_count(&state.owner) >= PWP_PUBLIC_HANDLE_LIMIT) return end(PWP_LIMIT);
    r = open_relative(parent, (const WCHAR *)name, length, path, 1, 0, 0, 1, child);
    if (r == PWP_OK) {
        r = pwp_publish(&state.owner, *child);
        if (r == PWP_OK) entry(*child)->public_handle = 1;
        else { if (retire(*child) != PWP_OK) r = PWP_CLEANUP_UNKNOWN; *child = 0; }
    }
    return end(r);
}
pwp_result pwp_win_identity(uint64_t token, uint64_t words[6]) {
    if (!words) return PWP_ARGUMENT;
    pwp_clear(words, 6*sizeof(uint64_t));
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *e = entry(token);
    if (!e || !e->public_handle || !verify(e)) return end(PWP_POLICY);
    memcpy(words, e->identity, 6*sizeof(uint64_t)); return end(PWP_OK);
}
pwp_result pwp_win_file_identity(uint64_t directory, const uint16_t *name, size_t length, uint64_t words[6]) {
    if (!words) return PWP_ARGUMENT;
    pwp_clear(words, 6*sizeof(uint64_t));
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(directory); WCHAR path[PWP_PATH_LIMIT]; uint64_t token = 0;
    if (!p || !p->public_handle || !verify(p) || !join_name(p, name, length, path)) return end(PWP_POLICY);
    pwp_entry *held = owned_file(directory, path);
    if (held) {
        if (!verify(held)) return end(PWP_POLICY);
        memcpy(words, held->identity, 6*sizeof(uint64_t)); return end(PWP_OK);
    }
    r = open_relative(directory, (const WCHAR *)name, length, path, 0, 0, 0, 1, &token);
    if (r != PWP_OK) return end(r);
    uint64_t observed[6]; memcpy(observed, entry(token)->identity, sizeof(observed));
    r = retire(token);
    if (r == PWP_OK) memcpy(words, observed, sizeof(observed));
    return end(r);
}
pwp_result pwp_win_exists(uint64_t directory, const uint16_t *name, size_t length, int *exists) {
    if (!exists) return PWP_ARGUMENT;
    *exists = 0;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(directory); WCHAR path[PWP_PATH_LIMIT]; uint64_t token = 0;
    if (!p || !p->public_handle || !verify(p) || !join_name(p, name, length, path)) return end(PWP_POLICY);
    pwp_entry *held = owned_file(directory, path);
    if (held) {
        if (!verify(held)) return end(PWP_POLICY);
        *exists = 1; return end(PWP_OK);
    }
    /* Unknown kind is queried on the actual opened handle; a failed file open is never inferred as a directory. */
    r = open_relative(directory, (const WCHAR *)name, length, path, -1, 0, 0, 1, &token);
    if (r == PWP_NOT_FOUND) return end(PWP_OK);
    if (r != PWP_OK) return end(r);
    r = retire(token);
    if (r == PWP_OK) *exists = 1;
    return end(r);
}
pwp_result pwp_win_names(uint64_t directory, pwp_directory_names *names) {
    if (!names) return PWP_ARGUMENT;
    pwp_clear(names, sizeof(*names));
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(directory);
    if (!p || !p->public_handle || !p->directory || !verify(p)) return end(PWP_POLICY);
    /* Delete-on-close stages may be omitted by OS enumeration; do not infer an ordinary namespace around them. */
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i)
        if (state.owner.slots[i].state == 2 && state.entries[i].parent == directory &&
            !pwp_regular_metadata(state.entries[i].stage.phase)) return end(PWP_POLICY);
    _Alignas(8) unsigned char buffer[PWP_DIRECTORY_BUFFER_LIMIT];
    int complete = 0;
    for (size_t batch = 0; batch <= PWP_DIRECTORY_LIMIT+2; ++batch) {
        memset(buffer, 0, sizeof(buffer));
        FILE_INFO_BY_HANDLE_CLASS kind = batch == 0 ? FileIdBothDirectoryRestartInfo : FileIdBothDirectoryInfo;
        if (!GetFileInformationByHandleEx(raw(directory), kind, buffer, sizeof(buffer))) {
            if (GetLastError() == ERROR_NO_MORE_FILES) { complete = 1; break; }
            r = PWP_OS; break;
        }
        r = pwp_directory_decode(buffer, sizeof(buffer), names);
        if (r != PWP_OK) break;
    }
    if (r == PWP_OK && !complete) r = PWP_LIMIT;
    if (r == PWP_OK && !verify(p)) r = PWP_POLICY;
    /* Directory rows are not file custody. Independently open/read back each returned member before publication. */
    for (size_t i = 0; r == PWP_OK && i < names->count; ++i) {
        WCHAR path[PWP_PATH_LIMIT]; uint64_t token = 0;
        if (!join_name(p, names->names[i], names->lengths[i], path)) { r = PWP_POLICY; break; }
        pwp_entry *held = owned_file(directory, path);
        if (held) {
            if (!verify(held)) r = PWP_POLICY;
        } else {
            r = open_relative(directory, (const WCHAR *)names->names[i], names->lengths[i], path, -1, 0, 0, 1, &token);
            if (r == PWP_OK) r = retire(token);
        }
    }
    pwp_clear(buffer, sizeof(buffer));
    if (r != PWP_OK) pwp_clear(names, sizeof(*names));
    return end(r);
}
pwp_result pwp_win_read(uint64_t directory, const uint16_t *name, size_t length,
                        unsigned char *output, size_t maximum, size_t *written) {
    if (!written || maximum > PWP_RECORD_LIMIT || (!output && maximum)) return PWP_ARGUMENT;
    *written = 0;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(directory); WCHAR path[PWP_PATH_LIMIT]; uint64_t token = 0;
    if (!p || !p->public_handle || !verify(p) || !join_name(p, name, length, path)) return end(PWP_POLICY);
    pwp_entry *held = owned_file(directory, path);
    if (held && !pwp_regular_metadata(held->stage.phase)) return end(PWP_POLICY);
    r = open_relative(directory, (const WCHAR *)name, length, path, 0, 0, 0, 1, &token);
    if (r != PWP_OK) return end(r);
    FILE_STANDARD_INFO info;
    if (!GetFileInformationByHandleEx(raw(token), FileStandardInfo, &info, sizeof(info)) ||
        info.EndOfFile.QuadPart < 0 || (uint64_t)info.EndOfFile.QuadPart > maximum) r = PWP_LIMIT;
    size_t offset = 0;
    while (r == PWP_OK && offset < (size_t)info.EndOfFile.QuadPart) {
        DWORD actual = 0;
        DWORD count = (DWORD)((size_t)info.EndOfFile.QuadPart-offset);
        if (count > 65536) count = 65536;
        if (!ReadFile(raw(token), output+offset, count, &actual, NULL) || !actual || actual > count) r = PWP_OS;
        else offset += actual;
    }
    FILE_STANDARD_INFO after;
    if (r == PWP_OK && (!verify(entry(token)) ||
        !GetFileInformationByHandleEx(raw(token), FileStandardInfo, &after, sizeof(after)) ||
        after.EndOfFile.QuadPart != info.EndOfFile.QuadPart)) r = PWP_POLICY;
    pwp_result cleanup = retire(token);
    if (cleanup != PWP_OK) r = cleanup;
    if (r == PWP_OK) *written = offset; else pwp_clear(output, maximum);
    return end(r);
}
pwp_result pwp_win_lock(uint64_t directory, const uint16_t *name, size_t length, uint64_t *lease) {
    if (!lease) return PWP_ARGUMENT;
    *lease = 0;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(directory); WCHAR path[PWP_PATH_LIMIT];
    if (!p || !p->public_handle || !verify(p) || !join_name(p, name, length, path)) return end(PWP_POLICY);
    pwp_entry *held = owned_file(directory, path);
    if (held && !pwp_regular_metadata(held->stage.phase)) return end(PWP_POLICY);
    if (pwp_public_count(&state.owner) >= PWP_PUBLIC_HANDLE_LIMIT) return end(PWP_LIMIT);
    /* Qualification component only: existing lock file, share-none ownership. Never silently creates durable state. */
    r = open_relative(directory, (const WCHAR *)name, length, path, 0, 0, 1, 1, lease);
    if (r == PWP_OK) {
        r = pwp_publish(&state.owner, *lease);
        if (r == PWP_OK) entry(*lease)->public_handle = 1;
        else { if (retire(*lease) != PWP_OK) r = PWP_CLEANUP_UNKNOWN; *lease = 0; }
    }
    return end(r);
}
/* The shared publication controller runs under gate; no callback re-enters native admission. */
static int new_lock_verify(void *context) {
    uint64_t token = *(uint64_t *)context;
    pwp_entry *e = entry(token); FILE_STANDARD_INFO info;
    return !state.failed && !state.owner.poisoned && e && !e->directory && !e->public_handle &&
        e->parent == state.root && verify(entry(state.root)) && verify(e) &&
        GetFileInformationByHandleEx(raw(token), FileStandardInfo, &info, sizeof(info)) &&
        !info.Directory && !info.DeletePending && info.EndOfFile.QuadPart == 0;
}
static int new_lock_flush(void *context) {
    uint64_t token = *(uint64_t *)context;
    return !state.failed && !state.owner.poisoned && FlushFileBuffers(raw(token));
}
pwp_result pwp_win_create_profile_lock(uint64_t root, uint64_t *lease) {
    if (!lease) return PWP_ARGUMENT;
    *lease = 0;
    if (!pwp_token_valid(root)) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(root); WCHAR path[PWP_PATH_LIMIT];
    static const WCHAR name[] = L"profile.lock";
    if (root != state.root || !p || !p->public_handle || !verify(p) ||
        !join_name(p, (const uint16_t *)name, sizeof(name)/sizeof(name[0])-1, path)) return end(PWP_POLICY);
    /* Existing names are never opened/truncated/repaired by this explicit create operation. */
    if (owned_file(root, path)) return end(PWP_BUSY);
    if (pwp_public_count(&state.owner) >= PWP_PUBLIC_HANDLE_LIMIT) return end(PWP_LIMIT);
    uint64_t token = 0;
    r = open_relative(root, name, sizeof(name)/sizeof(name[0])-1, path, 0, 1, 1, 1, &token);
    if (r != PWP_OK) return end(state.failed ? PWP_CLEANUP_UNKNOWN : r);
    /* FILE_CREATE + shareAccess=0 + READ/WRITE_DATA is the existing exclusive-handle lease contract.
     * No byte-range lock or recoverable namespace publication is claimed. Failed new empty files stay put. */
    r = pwp_lock_finish(&state.owner, token, new_lock_verify, new_lock_flush, close_os, &token);
    if (r == PWP_OK) { entry(token)->public_handle = 1; *lease = token; }
    else if (state.owner.poisoned || state.failed) { state.failed = 1; r = PWP_CLEANUP_UNKNOWN; }
    return end(r);
}
/* This context never escapes the serialized call. Its token is already RETIRING during callbacks;
 * use the saved original handle, never a live-token lookup or a fresh pathname open. */
typedef struct { pwp_entry *file; HANDLE handle; uint64_t expected[PWP_IDENTITY_WORDS]; } pwp_delete_native;
static int deletion_verify_mode(pwp_delete_native *c, int pending) {
    uint64_t observed[PWP_IDENTITY_WORDS]; FILE_STANDARD_INFO standard;
    pwp_entry *parent = entry(c->file->parent);
    if (state.failed || state.owner.poisoned || !parent || !parent->public_handle || !parent->directory ||
        !verify(parent) || c->file->directory || c->file->public_handle ||
        !pwp_regular_metadata(c->file->stage.phase) ||
        !pwp_expected_file(c->expected, PWP_IDENTITY_WORDS, parent->identity[1]) ||
        !no_impersonation() || !inspect_mode(c->handle, c->file->path, 0, 1, pending, observed) ||
        !GetFileInformationByHandleEx(c->handle, FileStandardInfo, &standard, sizeof(standard)) ||
        !!standard.DeletePending != pending || standard.Directory || standard.NumberOfLinks != 1)
        return 0;
    /* Pending-mode inspection deliberately has flags0, never the normal !DeletePending assertion. */
    for (size_t i = 0; i < PWP_IDENTITY_WORDS; ++i)
        if (observed[i] != (pending && i == 4 ? 0 : c->expected[i])) return 0;
    return !state.failed && !state.owner.poisoned;
}
static int deletion_verify(void *context) { return deletion_verify_mode(context, 0); }
static int deletion_pending_verify(void *context) { return deletion_verify_mode(context, 1); }
static int deletion_mark(void *context) {
    pwp_delete_native *c = context; FILE_DISPOSITION_INFO disposition = {TRUE};
    return !state.failed && !state.owner.poisoned &&
        SetFileInformationByHandle(c->handle, FileDispositionInfo, &disposition, sizeof(disposition));
}
static int deletion_close(uintptr_t resource, void *context) {
    pwp_delete_native *c = context;
    return resource == (uintptr_t)c->handle && CloseHandle(c->handle);
}
pwp_result pwp_win_request_delete(uint64_t directory, const uint16_t *name, size_t length,
                                  const uint64_t *expected, size_t count) {
    /* Validate shape before any reservation or native entry; volume bits remain unsigned. */
    if (!pwp_token_valid(directory) || !pwp_component(name, length) || !expected ||
        count != PWP_IDENTITY_WORDS || !pwp_expected_file(expected, count, expected[1])) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *parent = entry(directory); WCHAR path[PWP_PATH_LIMIT];
    if (!parent || !parent->public_handle || !parent->directory || !verify(parent) ||
        !pwp_expected_file(expected, count, parent->identity[1]) || !join_name(parent, name, length, path))
        return end_stage(PWP_POLICY);
    /* Never borrow a live lock/stage handle, temporarily unlock it, or fall back to path deletion. */
    if (owned_file(directory, path)) return end_stage(PWP_POLICY);
    uint64_t token = 0;
    r = open_relative_access(directory, (const WCHAR *)name, length, path, 0, 0, 0, 1, 1, &token);
    if (r != PWP_OK) return end_stage(r); /* NOT_FOUND is an error, not successful absence. */
    pwp_delete_native operation = {entry(token), raw(token), {0}};
    memcpy(operation.expected, expected, sizeof(operation.expected));
    r = pwp_delete_intent_finish(&state.owner, token, deletion_verify, deletion_mark,
                                 deletion_pending_verify, deletion_close, &operation);
    pwp_clear(operation.expected, sizeof(operation.expected));
    /* A mark/readback ambiguity stays quarantined even when CloseHandle returned success.
     * No retry, namespace-absence assertion, directory flush or transaction commit is implied. */
    if (state.owner.poisoned) state.failed = 1;
    return end_stage(r);
}
pwp_result pwp_win_close(uint64_t token) {
    if (!pwp_token_valid(token)) return PWP_ARGUMENT;
    AcquireSRWLockExclusive(&gate); /* Join actual OS completion; no pretend coroutine cancellation. */
    pwp_owned_handle *h = pwp_lookup(&state.owner, token);
    if (token == state.root && !state.active) return end(state.terminal);
    if (!h) return end(PWP_ARGUMENT);
    if (h->state == 3 || h->state == 4) return end(retire(token));
    pwp_entry *e = entry(token);
    if (!e || !e->public_handle) return end(PWP_ARGUMENT);
    if (token == state.root) {
        state.active = 0;
        pwp_result r = pwp_retire_all(&state.owner, close_os, NULL);
        if (r != PWP_OK) state.failed = 1;
        if (state.failed && r == PWP_OK) r = PWP_CLEANUP_UNKNOWN;
        state.terminal = r;
        return end(r);
    }
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i)
        if (state.owner.slots[i].state == 2 && state.entries[i].parent == token) return end(PWP_BUSY);
    return end(retire(token));
}
