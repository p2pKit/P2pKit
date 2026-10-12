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

/* Not declared by every user-mode SDK winternl.h. Signature/calling convention are the native API;
 * all types still come from the real Windows SDK and ntdll.lib supplies the static import. */
NTSYSAPI NTSTATUS NTAPI NtSetInformationFile(HANDLE file, PIO_STATUS_BLOCK status, PVOID information,
                                           ULONG length, FILE_INFORMATION_CLASS information_class);
NTSYSAPI NTSTATUS NTAPI NtQueryInformationFile(HANDLE file, PIO_STATUS_BLOCK status, PVOID information,
                                             ULONG length, FILE_INFORMATION_CLASS information_class);
NTSYSAPI NTSTATUS NTAPI NtFlushBuffersFileEx(HANDLE file, ULONG flags, PVOID parameters,
                                           ULONG parameter_size, PIO_STATUS_BLOCK status);

/* Static imports are exclusively Windows system KnownDLLs; no cwd search or dynamically named DLL. */
#pragma comment(lib, "advapi32.lib")
#pragma comment(lib, "kernel32.lib")
#pragma comment(lib, "ntdll.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "uuid.lib")

_Static_assert(sizeof(void *) == 8 && sizeof(WCHAR) == 2, "Windows x64 ABI required");
_Static_assert(sizeof(FILE_ID_INFO) == 24 && sizeof(IO_STATUS_BLOCK) == 16, "Unexpected Windows SDK ABI");
_Static_assert((READ_CONTROL | SYNCHRONIZE | FILE_LIST_DIRECTORY | FILE_TRAVERSE |
                FILE_READ_ATTRIBUTES | FILE_ADD_FILE) == PWP_DIRECTORY_SYNC_ACCESS,
               "Unexpected private directory synchronization access mask");
typedef struct { ACCESS_MASK granted; } pwp_file_access_information;
_Static_assert(sizeof(pwp_file_access_information) == 4, "Unexpected FileAccessInformation ABI");
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

/* Classic native FileRenameInformation, not Win32 pathname/CWD resolution or extended rename flags.
 * Explicit layout checked for the only supported native AMD64 ABI. FileNameLength excludes the terminator. */
typedef struct {
    BOOLEAN replace;
    HANDLE root;
    ULONG name_bytes;
    WCHAR name[PWP_COMPONENT_LIMIT+1];
} pwp_rename_information;
_Static_assert(offsetof(pwp_rename_information, replace) == 0 &&
               offsetof(pwp_rename_information, root) == 8 &&
               offsetof(pwp_rename_information, name_bytes) == 16 &&
               offsetof(pwp_rename_information, name) == 20, "Unexpected native rename ABI");
_Static_assert(sizeof(pwp_rename_information) >= 24+PWP_COMPONENT_LIMIT*sizeof(WCHAR),
               "Native rename buffer lacks documented structure/name capacity");

typedef struct {
    uint64_t token, parent;
    WCHAR path[PWP_PATH_LIMIT];
    uint64_t identity[PWP_IDENTITY_WORDS];
    int directory, public_handle;
    pwp_stage stage;
    pwp_candidate candidate;
    pwp_directory_sync sync;
    int stage_created, stage_validated, directory_sync_access;
} pwp_entry;
typedef struct {
    pwp_owner owner;
    pwp_roles roles;
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
    if (state.failed) state.owner.poisoned = 1;
    pwp_result r = pwp_roles_retire(&state.roles, &state.owner, token, close_os, NULL);
    if (r == PWP_CLEANUP_UNKNOWN) state.failed = 1;
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
static int directory_sync_access(HANDLE handle) {
    pwp_file_access_information access = {0}; IO_STATUS_BLOCK io = {0};
    NTSTATUS status = NtQueryInformationFile(handle, &io, &access, (ULONG)sizeof(access),
                                            (FILE_INFORMATION_CLASS)8); /* FileAccessInformation */
    return pwp_directory_sync_access(status == 0 && io.Status == 0 && io.Information == sizeof(access),
                                      access.granted);
}
static pwp_result open_relative_access(uint64_t parent, const WCHAR *name, size_t length,
                                 const WCHAR *path, int directory, int create, int lock_file,
                                 int private_file, int delete_file, int sync_directory,
                                 int exclusive_probe, uint64_t *output) {
    if ((delete_file && (directory != 0 || create || lock_file || !private_file)) ||
        (sync_directory && (directory != 1 || lock_file || !private_file || delete_file)) ||
        (exclusive_probe && (directory != 0 || create || lock_file || !private_file ||
                             delete_file || sync_directory)) ||
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
        (lock_file ? FILE_WRITE_DATA : 0) | (delete_file ? DELETE : 0) |
        (sync_directory ? FILE_ADD_FILE : 0);
    NTSTATUS status = NtCreateFile(&handle, access, &attributes, &io, NULL, FILE_ATTRIBUTE_NORMAL,
        (lock_file || delete_file || exclusive_probe) ? 0 : FILE_SHARE_READ,
        create ? PWP_FILE_CREATE : PWP_FILE_OPEN,
        PWP_FILE_REPARSE | PWP_FILE_SYNCHRONOUS |
        (directory < 0 ? 0 : directory ? PWP_FILE_DIRECTORY : PWP_FILE_NON_DIRECTORY), NULL, 0);
    if (handle && handle != INVALID_HANDLE_VALUE && attach(owned, handle) != PWP_OK) {
        state.failed = 1; return PWP_CLEANUP_UNKNOWN;
    }
    if (status != 0 || (exclusive_probe && io.Status != 0) ||
        io.Information != (create ? 2u : 1u) || !raw(owned)) {
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
    e->directory_sync_access = sync_directory;
    wcscpy_s(e->path, PWP_PATH_LIMIT, path);
    if (!inspect(handle, path, directory, private_file, e->identity) ||
        (sync_directory && !directory_sync_access(handle))) {
        if (retire(owned) != PWP_OK) return PWP_CLEANUP_UNKNOWN;
        return PWP_POLICY;
    }
    *output = owned; return PWP_OK;
}
/* Preserve all existing callers' exact access/share/create semantics. */
static pwp_result open_relative(uint64_t parent, const WCHAR *name, size_t length,
                                 const WCHAR *path, int directory, int create, int lock_file,
                                 int private_file, uint64_t *output) {
    return open_relative_access(parent, name, length, path, directory, create, lock_file, private_file,
                                 0, 0, 0, output);
}
/* Only the canonical public root/identity callers select this on their first original open. Ancestors,
 * noncanonical children, files and ordinary observations retain their existing access/share policy. */
static pwp_result open_sync_directory(uint64_t parent, const WCHAR *name, size_t length,
                                       const WCHAR *path, int create, uint64_t *output) {
    return open_relative_access(parent, name, length, path, 1, create, 0, 1, 0, 1, 0, output);
}
static int regular_entry(const pwp_entry *e) {
    return e && pwp_regular_metadata(e->stage.phase) && e->candidate.phase == PWP_CANDIDATE_EMPTY;
}
static int verify(pwp_entry *e) {
    uint64_t observed[6];
    return regular_entry(e) && no_impersonation() &&
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
/* Replacement must not borrow/retire any pre-existing owner, even an unpublished or directory owner. */
static int owned_target(uint64_t parent, const WCHAR *path) {
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        const pwp_owned_handle *owned = &state.owner.slots[i];
        const pwp_entry *e = &state.entries[i];
        if (owned->state && owned->state != 3 && e->token == owned->token &&
            e->parent == parent && same_path(e->path, path)) return 1;
    }
    return 0;
}
static int join_name(pwp_entry *parent, const uint16_t *name, size_t length, WCHAR *path) {
    if (!parent || !parent->directory || !pwp_component(name, length)) return 0;
    size_t count = wcslen(parent->path);
    if (count+length+2 > PWP_PATH_LIMIT) return 0;
    memcpy(path, parent->path, count*sizeof(WCHAR)); path[count++] = L'\\';
    memcpy(path+count, name, length*sizeof(WCHAR)); path[count+length] = 0; return 1;
}
static const WCHAR profile_lock_name[] = L"profile.lock", vault_lock_name[] = L"vault.lock";
static const WCHAR identity_name[] = L"identity";
static const WCHAR *lease_name(pwp_lease_role role) {
    return role == PWP_LEASE_PROFILE ? profile_lock_name : role == PWP_LEASE_VAULT ? vault_lock_name : NULL;
}
static int canonical_identity_name(const uint16_t *name, size_t length) {
    if (!name || length != sizeof(identity_name)/sizeof(identity_name[0])-1) return 0;
    for (size_t i = 0; i < length; ++i) {
        uint16_t c = name[i];
        if (c >= 'A' && c <= 'Z') c = (uint16_t)(c+32);
        if (c != (uint16_t)identity_name[i]) return 0;
    }
    return 1;
}
/* Structural custody alone is not lease authority. All callers already hold gate; never re-enter begin(). */
static int lease_directory_verify(uint64_t directory, pwp_lease_role role) {
    pwp_entry *root = entry(state.root), *parent = entry(directory);
    if (state.failed || state.owner.poisoned || state.roles.root != state.root || !root || !parent ||
        !root->directory || !root->public_handle || !parent->directory || !parent->public_handle) return 0;
    if (role == PWP_LEASE_PROFILE) {
        if (directory != state.root) return 0;
    } else if (role != PWP_LEASE_VAULT || directory != state.roles.identity ||
        directory == state.root || parent->parent != state.root) return 0;
    if (!verify(root)) return 0;
    if (role == PWP_LEASE_VAULT && (!verify(parent) ||
        !pwp_vault_directory_scope(root->identity, parent->identity, PWP_IDENTITY_WORDS,
            (const uint16_t *)root->path, wcslen(root->path),
            (const uint16_t *)parent->path, wcslen(parent->path)))) return 0;
    return !state.failed && !state.owner.poisoned;
}
static int held_lease_verify(pwp_lease_role role) {
    uint64_t directory = role == PWP_LEASE_PROFILE ? state.roles.root : state.roles.identity;
    uint64_t token = role == PWP_LEASE_PROFILE ? state.roles.profile : state.roles.vault;
    pwp_role_grant grant;
    if (pwp_roles_capture(&state.roles, &state.owner, directory, &grant) != PWP_OK) return 0;
    if (role == PWP_LEASE_VAULT && !held_lease_verify(PWP_LEASE_PROFILE)) return 0;
    pwp_entry *file = entry(token), *parent = entry(directory); WCHAR path[PWP_PATH_LIMIT];
    FILE_STANDARD_INFO info; const WCHAR *name = lease_name(role);
    return name && file && parent && !file->directory && file->public_handle && file->parent == directory &&
        lease_directory_verify(directory, role) &&
        join_name(parent, (const uint16_t *)name, wcslen(name), path) && same_path(file->path, path) &&
        verify(file) && pwp_expected_lock_file(parent->identity, file->identity, PWP_IDENTITY_WORDS) &&
        GetFileInformationByHandleEx(raw(token), FileStandardInfo, &info, sizeof(info)) &&
        !info.Directory && !info.DeletePending && info.EndOfFile.QuadPart == 0 &&
        pwp_roles_check_grant(&state.roles, &state.owner, &grant) == PWP_OK && !state.failed;
}
static int mutation_verify(const pwp_role_grant *grant) {
    return !state.failed && pwp_roles_check_grant(&state.roles, &state.owner, grant) == PWP_OK &&
        held_lease_verify(PWP_LEASE_PROFILE) &&
        (grant->directory == state.roles.root || held_lease_verify(PWP_LEASE_VAULT)) &&
        pwp_roles_check_grant(&state.roles, &state.owner, grant) == PWP_OK && !state.failed;
}
/* Public primitives capture their current grant. Composite operations pass the one original grant;
 * never silently replace its generations between preparation, publication and directory sync. */
static pwp_result operation_grant(uint64_t directory, const pwp_role_grant *original, pwp_role_grant *grant) {
    if (!original) return pwp_roles_capture(&state.roles, &state.owner, directory, grant);
    if (original->directory != directory) return PWP_POLICY;
    *grant = *original;
    return pwp_roles_check_grant(&state.roles, &state.owner, grant);
}
static int lock_admission_verify(uint64_t directory, pwp_lease_role role) {
    return pwp_roles_lease_admit(&state.roles, &state.owner, directory, role) == PWP_OK &&
        lease_directory_verify(directory, role) &&
        (role == PWP_LEASE_PROFILE || held_lease_verify(PWP_LEASE_PROFILE)) &&
        pwp_roles_lease_admit(&state.roles, &state.owner, directory, role) == PWP_OK && !state.failed;
}
typedef struct { pwp_entry *entry; HANDLE handle; const pwp_role_grant *grant; } pwp_stage_context;
static int stage_check(size_t expected_size, void *context) {
    pwp_stage_context *c = context; uint64_t observed[6]; FILE_STANDARD_INFO size;
    pwp_entry *parent = entry(c->entry->parent);
    return c->entry->stage_created && c->entry->stage_validated && mutation_verify(c->grant) &&
        verify(parent) && no_impersonation() &&
        inspect_mode(c->handle, c->entry->path, 0, 1, 1, observed) &&
        memcmp(observed, c->entry->identity, sizeof(observed)) == 0 &&
        GetFileInformationByHandleEx(c->handle, FileStandardInfo, &size, sizeof(size)) &&
        size.EndOfFile.QuadPart >= 0 && (uint64_t)size.EndOfFile.QuadPart == expected_size &&
        mutation_verify(c->grant);
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
            e->token == state.owner.slots[i].token && e->directory) {
            int closed = CloseHandle((HANDLE)resource) != 0;
            /* Do not mark a live owner retired before this actual close. Flush uncertainty survives
             * successful physical cleanup and the owner registry prevents every later close retry. */
            return pwp_directory_sync_close_ok(&e->sync, closed);
        }
        if (state.owner.slots[i].resource == resource && state.owner.slots[i].state == 4 &&
            e->token == state.owner.slots[i].token && e->candidate.phase != PWP_CANDIDATE_EMPTY) {
            int closed = CloseHandle((HANDLE)resource) != 0;
            /* A post-rename ambiguity survives even a successful physical close. The original owner/grant
             * stays quarantined; repeated close cannot reuse/retry that numeric Windows handle. */
            return pwp_candidate_close_ok(&e->candidate, closed);
        }
        if (state.owner.slots[i].resource == resource && state.owner.slots[i].state == 4 &&
            e->token == state.owner.slots[i].token && e->stage.phase != PWP_STAGE_EMPTY) {
            pwp_stage_context context = {e, (HANDLE)resource, NULL};
            return pwp_stage_discard(&e->stage, stage_mark_delete, stage_close_handle, &context) == PWP_OK;
        }
    }
    return CloseHandle((HANDLE)resource) != 0;
}
static pwp_result end_stage(pwp_result result) {
    /* Security-descriptor/other custody cleanup can fail independently of an operation's result. */
    return end(pwp_cleanup_result(result, state.failed, state.owner.poisoned));
}
typedef struct { pwp_entry *directory; HANDLE handle; pwp_role_grant grant; } pwp_sync_context;
static int sync_directory_verify(void *opaque) {
    pwp_sync_context *c = opaque; pwp_entry *directory = c->directory;
    return directory && entry(directory->token) == directory && directory->public_handle &&
        directory->directory && directory->directory_sync_access &&
        directory->sync.phase == PWP_SYNC_RUNNING && raw(directory->token) == c->handle &&
        mutation_verify(&c->grant) && verify(directory) && directory_sync_access(c->handle) &&
        mutation_verify(&c->grant);
}
static int sync_directory_flush(void *opaque) {
    pwp_sync_context *c = opaque; IO_STATUS_BLOCK io = {0};
    /* Normal (zero) flags flush NTFS metadata AND the underlying storage cache. FILE_DATA_ONLY,
     * NO_SYNC, FILE_DATA_SYNC_ONLY, volume handles, reopening, and privileged fallbacks are forbidden. */
    NTSTATUS status = NtFlushBuffersFileEx(c->handle, 0, NULL, 0, &io);
    return status == 0 && io.Status == 0; /* Original synchronous handle: never accept STATUS_PENDING. */
}
static pwp_result sync_directory_locked(uint64_t token, const pwp_role_grant *original) {
    pwp_entry *directory = entry(token);
    if (!directory || !directory->directory || !directory->public_handle ||
        !directory->directory_sync_access) return PWP_POLICY;
    pwp_role_grant grant;
    pwp_result r = operation_grant(token, original, &grant);
    if (r != PWP_OK) return r;
    pwp_sync_context context = {directory, raw(token), grant};
    r = pwp_directory_sync_apply(&directory->sync, sync_directory_verify, sync_directory_flush, &context);
    if (directory->sync.phase == PWP_SYNC_UNCERTAIN) {
        /* Retain all original handles/grants for actual independent retirement, never fake a close. */
        state.failed = 1; state.owner.poisoned = 1;
    }
    return r;
}
pwp_result pwp_win_sync_directory(uint64_t token) {
    if (!pwp_token_valid(token)) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    return end_stage(sync_directory_locked(token, NULL));
}
/* This is NOT a record write/commit. The original handle is delete-on-close from creation, share-none,
 * never renameable by this component, and remains registered until explicit discard or session close. */
static pwp_result stage_bytes(uint64_t directory, const uint16_t *name, size_t length, const WCHAR *path,
                               const unsigned char *bytes, size_t count, const pwp_role_grant *grant,
                               uint64_t *output) {
    if (!mutation_verify(grant)) return PWP_POLICY;
    uint64_t token = 0; pwp_result r = reserve(&token); if (r != PWP_OK) return r;
    _Alignas(void *) unsigned char acl_buffer[256]; SECURITY_DESCRIPTOR sd;
    if (!security_descriptor(&sd, (ACL *)acl_buffer, sizeof(acl_buffer), 0)) {
        r = retire(token); return r == PWP_OK ? PWP_OS : r;
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
        state.failed = 1; return PWP_CLEANUP_UNKNOWN;
    }
    if (raw(token)) {
        pwp_owned_handle *h = pwp_lookup(&state.owner, token);
        pwp_entry *e = &state.entries[h-state.owner.slots];
        e->token = token; e->parent = directory; wcscpy_s(e->path, PWP_PATH_LIMIT, path);
        (void)pwp_stage_init(&e->stage);
        e->stage_created = status == 0 && io.Information == 2;
    }
    if (status != 0 || io.Information != 2 || !raw(token)) {
        r = retire(token); return r == PWP_OK ? PWP_OS : r;
    }
    pwp_entry *e = entry(token);
    if (!inspect_mode(handle, path, 0, 1, 1, e->identity)) {
        r = retire(token); return r == PWP_OK ? PWP_POLICY : r;
    }
    e->stage_validated = 1;
    pwp_stage_context context = {e, handle, grant};
    r = pwp_stage_fill(&e->stage, bytes, count, stage_write, stage_flush, stage_check, &context);
    if (r == PWP_OK) r = pwp_publish(&state.owner, token);
    if (r == PWP_OK) r = pwp_roles_bind_stage(&state.roles, &state.owner, token, grant);
    if (r != PWP_OK) {
        pwp_result cleanup = retire(token); return cleanup == PWP_OK ? r : cleanup;
    }
    e->public_handle = 1; *output = token; return PWP_OK;
}
typedef struct {
    uint64_t directory;
    const uint16_t *name;
    size_t length;
    const WCHAR *path;
    pwp_buffer_action copy;
    void *context;
    uint64_t *output;
    pwp_role_grant grant;
} pwp_stage_input;
static pwp_result stage_copy_and_fill(unsigned char *bytes, size_t count, void *opaque) {
    pwp_stage_input *input = opaque;
    pwp_result result = input->copy(bytes, count, input->context);
    if (result != PWP_OK) return result;
    return stage_bytes(input->directory, input->name, input->length, input->path, bytes, count,
                        &input->grant, input->output);
}
pwp_result pwp_win_stage(uint64_t directory, const uint16_t *name, size_t length,
                         size_t count, pwp_buffer_action copy, void *context, uint64_t *output) {
    if (!output) return PWP_ARGUMENT;
    *output = 0;
    if (!copy || count > PWP_RECORD_LIMIT || !pwp_stage_name(name, length)) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *parent = entry(directory); WCHAR path[PWP_PATH_LIMIT];
    if (!parent || !parent->public_handle || !verify(parent) || !join_name(parent, name, length, path))
        return end_stage(PWP_POLICY);
    pwp_role_grant grant;
    r = pwp_roles_capture(&state.roles, &state.owner, directory, &grant);
    if (r != PWP_OK) return end_stage(r);
    if (!mutation_verify(&grant)) return end_stage(PWP_POLICY);
    if (pwp_public_count(&state.owner) >= PWP_PUBLIC_HANDLE_LIMIT) return end_stage(PWP_LIMIT);
    pwp_stage_input input = {directory, name, length, path, copy, context, output, grant};
    /* Input allocation/copy and zero/free are inside this exact native admission, including JNI failure. */
    r = pwp_buffer_apply(count, stage_copy_and_fill, &input);
    return end_stage(r);
}
/* A persistent candidate is NOT a delete-on-close stage or a committed record. Keep DELETE access for
 * a future same-original-handle publication operation, but never set disposition or rename here. */
typedef struct { pwp_entry *entry; HANDLE handle; const pwp_role_grant *grant; } pwp_candidate_context;
static int candidate_check(size_t expected_size, void *opaque) {
    pwp_candidate_context *c = opaque;
    uint64_t observed[PWP_IDENTITY_WORDS]; FILE_STANDARD_INFO size;
    pwp_entry *parent = entry(c->entry->parent);
    return c->entry->candidate.phase == PWP_CANDIDATE_FILLING && mutation_verify(c->grant) &&
        verify(parent) && no_impersonation() &&
        inspect(c->handle, c->entry->path, 0, 1, observed) &&
        memcmp(observed, c->entry->identity, sizeof(observed)) == 0 &&
        pwp_expected_lock_file(parent->identity, observed, PWP_IDENTITY_WORDS) &&
        GetFileInformationByHandleEx(c->handle, FileStandardInfo, &size, sizeof(size)) &&
        size.EndOfFile.QuadPart >= 0 && (uint64_t)size.EndOfFile.QuadPart == expected_size &&
        mutation_verify(c->grant);
}
static int candidate_write(const unsigned char *bytes, size_t count, size_t *written, void *opaque) {
    pwp_candidate_context *c = opaque; DWORD actual = 0;
    if (!written || !bytes || !count || count > 65536) return 0;
    int ok = WriteFile(c->handle, bytes, (DWORD)count, &actual, NULL) != 0;
    *written = actual; return ok;
}
static int candidate_read(unsigned char *bytes, size_t count, size_t *read_count, void *opaque) {
    pwp_candidate_context *c = opaque; DWORD actual = 0;
    if (!read_count || !bytes || !count || count > 4096) return 0;
    int ok = ReadFile(c->handle, bytes, (DWORD)count, &actual, NULL) != 0;
    *read_count = actual; return ok;
}
static int candidate_flush(void *opaque) {
    pwp_candidate_context *c = opaque; return FlushFileBuffers(c->handle) != 0;
}
static int candidate_rewind(void *opaque) {
    pwp_candidate_context *c = opaque; LARGE_INTEGER zero = {0}, position = {0};
    return SetFilePointerEx(c->handle, zero, &position, FILE_BEGIN) && position.QuadPart == 0;
}
static pwp_result candidate_bytes(uint64_t directory, const uint16_t *name, size_t length,
                                  const WCHAR *path, const unsigned char *bytes, size_t count,
                                  const pwp_role_grant *grant, uint64_t *output) {
    if (!mutation_verify(grant)) return PWP_POLICY;
    uint64_t token = 0; pwp_result r = reserve(&token); if (r != PWP_OK) return r;
    _Alignas(void *) unsigned char acl_buffer[256]; SECURITY_DESCRIPTOR sd;
    if (!security_descriptor(&sd, (ACL *)acl_buffer, sizeof(acl_buffer), 0)) {
        r = retire(token); return r == PWP_OK ? PWP_OS : r;
    }
    UNICODE_STRING text = {(USHORT)(length*2), (USHORT)(length*2), (PWSTR)name};
    OBJECT_ATTRIBUTES attributes;
    InitializeObjectAttributes(&attributes, &text, OBJ_CASE_INSENSITIVE, raw(directory), &sd);
    IO_STATUS_BLOCK io = {0}; HANDLE handle = NULL;
    NTSTATUS status = NtCreateFile(&handle, READ_CONTROL | FILE_READ_ATTRIBUTES | FILE_READ_DATA |
        FILE_WRITE_DATA | DELETE | SYNCHRONIZE, &attributes, &io, NULL, FILE_ATTRIBUTE_NORMAL, 0,
        PWP_FILE_CREATE, PWP_FILE_REPARSE | PWP_FILE_SYNCHRONOUS | PWP_FILE_NON_DIRECTORY, NULL, 0);
    if (handle && handle != INVALID_HANDLE_VALUE && attach(token, handle) != PWP_OK) {
        state.failed = 1; return PWP_CLEANUP_UNKNOWN;
    }
    if (raw(token)) {
        /* attach owns the raw handle before entry metadata is initialized. */
        pwp_owned_handle *h = pwp_lookup(&state.owner, token);
        pwp_entry *e = &state.entries[h-state.owner.slots];
        e->token = token; e->parent = directory; wcscpy_s(e->path, PWP_PATH_LIMIT, path);
        (void)pwp_candidate_init(&e->candidate);
    }
    if (status != 0 || io.Information != 2 || !raw(token)) {
        r = retire(token); return r == PWP_OK ? PWP_OS : r;
    }
    pwp_entry *e = entry(token);
    if (!inspect(handle, path, 0, 1, e->identity)) {
        r = retire(token); return r == PWP_OK ? PWP_POLICY : r;
    }
    pwp_candidate_context operation = {e, handle, grant};
    r = pwp_candidate_fill(&e->candidate, bytes, count, candidate_write, candidate_flush,
                           candidate_rewind, candidate_read, candidate_check, &operation);
    if (r == PWP_OK) r = pwp_publish(&state.owner, token);
    /* The dependency ledger binds exact role grants, not delete-on-close semantics. */
    if (r == PWP_OK) r = pwp_roles_bind_stage(&state.roles, &state.owner, token, grant);
    if (r != PWP_OK) {
        /* Retire the exact original handle only. Partial/new candidates remain for explicit future recovery;
         * never delete a pathname, treat them as committed, or promise namespace durability. */
        pwp_result cleanup = retire(token); return cleanup == PWP_OK ? r : cleanup;
    }
    e->public_handle = 1; *output = token; return PWP_OK;
}
static pwp_result candidate_copy_and_fill(unsigned char *bytes, size_t count, void *opaque) {
    pwp_stage_input *input = opaque;
    pwp_result r = input->copy(bytes, count, input->context);
    if (r != PWP_OK) return r;
    return candidate_bytes(input->directory, input->name, input->length, input->path, bytes, count,
                            &input->grant, input->output);
}
static pwp_result prepare_record_locked(uint64_t directory, const uint16_t *name, size_t length,
                                       size_t count, pwp_buffer_action copy, void *context, uint64_t *output,
                                       const pwp_role_grant *original) {
    pwp_entry *parent = entry(directory); WCHAR path[PWP_PATH_LIMIT];
    if (!parent || !parent->public_handle || !verify(parent) || !join_name(parent, name, length, path))
        return PWP_POLICY;
    pwp_role_grant grant;
    pwp_result r = operation_grant(directory, original, &grant);
    if (r != PWP_OK) return r;
    if (!mutation_verify(&grant)) return PWP_POLICY;
    if (pwp_public_count(&state.owner) >= PWP_PUBLIC_HANDLE_LIMIT) return PWP_LIMIT;
    pwp_stage_input input = {directory, name, length, path, copy, context, output, grant};
    return pwp_buffer_apply(count, candidate_copy_and_fill, &input);
}
pwp_result pwp_win_prepare_record(uint64_t directory, const uint16_t *name, size_t length,
                                  size_t count, pwp_buffer_action copy, void *context, uint64_t *output) {
    if (!output) return PWP_ARGUMENT;
    *output = 0;
    if (!copy || count > PWP_RECORD_LIMIT || !pwp_candidate_name(name, length)) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    return end_stage(prepare_record_locked(directory, name, length, count, copy, context, output, NULL));
}
typedef struct {
    pwp_entry *file;
    HANDLE handle;
    const uint16_t *name;
    size_t length;
    const WCHAR *target_path;
    pwp_role_grant grant;
} pwp_rename_context;
static int publication_check(size_t expected_size, pwp_entry *file, HANDLE handle, const pwp_role_grant *grant,
                              const WCHAR *path, pwp_candidate_phase phase) {
    pwp_entry *parent = entry(file->parent);
    uint64_t observed[PWP_IDENTITY_WORDS]; FILE_STANDARD_INFO size;
    return entry(file->token) == file && raw(file->token) == handle && file->candidate.phase == phase &&
        expected_size == file->candidate.prepared_size && expected_size <= PWP_RECORD_LIMIT &&
        pwp_roles_check_stage(&state.roles, &state.owner, file->token) == PWP_OK &&
        mutation_verify(grant) && verify(parent) && no_impersonation() &&
        inspect(handle, path, 0, 1, observed) &&
        memcmp(observed, file->identity, sizeof(observed)) == 0 &&
        pwp_expected_lock_file(parent->identity, observed, PWP_IDENTITY_WORDS) &&
        GetFileInformationByHandleEx(handle, FileStandardInfo, &size, sizeof(size)) &&
        size.EndOfFile.QuadPart >= 0 && (uint64_t)size.EndOfFile.QuadPart == expected_size &&
        mutation_verify(grant) &&
        pwp_roles_check_stage(&state.roles, &state.owner, file->token) == PWP_OK;
}
static int rename_before(size_t expected_size, void *opaque) {
    pwp_rename_context *c = opaque;
    return publication_check(expected_size, c->file, c->handle, &c->grant, c->file->path,
                              PWP_CANDIDATE_RENAMING);
}
static int rename_after(size_t expected_size, void *opaque) {
    pwp_rename_context *c = opaque;
    return publication_check(expected_size, c->file, c->handle, &c->grant, c->target_path,
                              PWP_CANDIDATE_RENAMING);
}
static int rename_target(pwp_rename_context *c, int replace) {
    if (replace != 0 && replace != 1) return 0;
    pwp_rename_information info; IO_STATUS_BLOCK io = {0};
    memset(&info, 0, sizeof(info)); /* Include padding, not just C member initialization. */
    /* Native NULL RootDirectory + simple name means the source file's own directory, NOT process CWD.
     * No absolute target, alternate parent, POSIX flag or write-sharing relaxation. A true replacement
     * flag is reachable only through the separately admitted/retired fresh destination probe. */
    info.replace = (BOOLEAN)(replace ? TRUE : FALSE);
    info.root = NULL; info.name_bytes = (ULONG)(c->length*sizeof(WCHAR));
    memcpy(info.name, c->name, info.name_bytes);
    /* Advertise the complete zero-padded fixed buffer, not merely offsetof(FileName)+name bytes.
     * It covers the documented sizeof(FILE_RENAME_INFORMATION)+name-bytes requirement on AMD64. */
    NTSTATUS status = NtSetInformationFile(c->handle, &io, &info, (ULONG)sizeof(info), (FILE_INFORMATION_CLASS)10);
    pwp_clear(&info, sizeof(info));
    /* The original handle is synchronous. Do not retry or reinterpret non-success as harmless collision. */
    return status == 0 && io.Status == 0;
}
static int rename_once(void *opaque) { return rename_target(opaque, 0); }
static int rename_flush(void *opaque) {
    pwp_rename_context *c = opaque; return FlushFileBuffers(c->handle) != 0;
}
static pwp_result rename_candidate_locked(uint64_t token, const uint16_t *name, size_t length,
                                          const pwp_role_grant *original) {
    pwp_entry *file = entry(token);
    if (!file || !file->public_handle || file->directory || file->stage.phase != PWP_STAGE_EMPTY ||
        file->candidate.phase == PWP_CANDIDATE_EMPTY) return PWP_POLICY;
    if (file->candidate.phase != PWP_CANDIDATE_VERIFIED) return PWP_CLOSED;
    pwp_entry *parent = entry(file->parent); WCHAR target_path[PWP_PATH_LIMIT];
    if (!parent || !parent->public_handle || !verify(parent) ||
        pwp_roles_check_stage(&state.roles, &state.owner, token) != PWP_OK) return PWP_POLICY;
    int identity_scope = file->parent == state.roles.identity;
    if (!pwp_candidate_target(name, length, identity_scope)) return PWP_ARGUMENT;
    pwp_role_grant grant;
    pwp_result r = operation_grant(file->parent, original, &grant);
    if (r != PWP_OK) return r;
    if (!mutation_verify(&grant) || !join_name(parent, name, length, target_path)) return PWP_POLICY;
    /* Early collision refusal is read-only, NOT authority for publication: the actual syscall below must
     * still refuse replacement atomically. Never temporarily release a held destination against ourselves. */
    if (owned_file(file->parent, target_path)) return PWP_POLICY;
    uint64_t probe = 0;
    r = open_relative(file->parent, (const WCHAR *)name, length, target_path, -1, 0, 0, 1, &probe);
    if (r == PWP_OK) {
        r = retire(probe); return r == PWP_OK ? PWP_POLICY : r;
    }
    if (r != PWP_NOT_FOUND) return r;
    pwp_rename_context operation = {file, raw(token), name, length, target_path, grant};
    r = pwp_candidate_rename_new(&file->candidate, rename_before, rename_once, rename_after,
                                 rename_flush, &operation);
    if (file->candidate.phase == PWP_CANDIDATE_UNCERTAIN) {
        /* Leave original owner state live until real retirement; pre-marking it retired would skip close. */
        state.failed = 1; state.owner.poisoned = 1;
    }
    if (r == PWP_OK) {
        /* Only complete same-handle post-rename/file-flush readback permits updating the observed path.
         * RENAMED still refuses ordinary metadata. This is NOT the complete adapter's durable write. */
        memcpy(file->path, target_path, (wcslen(target_path)+1)*sizeof(WCHAR));
    }
    return r;
}
pwp_result pwp_win_rename_candidate(uint64_t token, const uint16_t *name, size_t length) {
    if (!pwp_token_valid(token) || !pwp_component(name, length)) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    return end_stage(rename_candidate_locked(token, name, length, NULL));
}
typedef struct {
    pwp_rename_context source;
    uint64_t target_token;
    pwp_entry *target;
    HANDLE target_handle;
    int close_attempted, closed;
} pwp_replace_context;
static int replace_before(size_t expected_size, void *opaque) {
    pwp_replace_context *c = opaque;
    return rename_before(expected_size, &c->source);
}
static int replace_target_verify(void *opaque) {
    pwp_replace_context *c = opaque;
    pwp_entry *target = c->target, *parent = entry(c->source.file->parent);
    return target && parent && c->target_token && !c->close_attempted &&
        entry(c->target_token) == target && raw(c->target_token) == c->target_handle &&
        !target->public_handle && !target->directory && target->parent == parent->token &&
        regular_entry(target) && same_path(target->path, c->source.target_path) &&
        mutation_verify(&c->source.grant) && verify(target) &&
        pwp_expected_lock_file(parent->identity, target->identity, PWP_IDENTITY_WORDS) &&
        /* Distinct original identities, not a borrowed candidate alias or a compare-and-swap promise. */
        (target->identity[2] != c->source.file->identity[2] ||
         target->identity[3] != c->source.file->identity[3]) &&
        mutation_verify(&c->source.grant);
}
static int replace_target_close(uintptr_t resource, void *opaque) {
    pwp_replace_context *c = opaque;
    if (c->close_attempted) return 0;
    c->close_attempted = 1;
    if (resource != (uintptr_t)c->target_handle) return 0;
    c->closed = CloseHandle(c->target_handle) != 0;
    return c->closed;
}
static int replace_rename(int replace, void *opaque) {
    pwp_replace_context *c = opaque;
    if (replace != (c->target_token != 0) ||
        (c->target_token ? !c->close_attempted || !c->closed : c->close_attempted || c->closed)) return 0;
    /* Source revalidation may already have reused the retired probe's registry slot. Neither its entry
     * pointer nor numeric OS handle is read or reused after the successful original close. */
    return rename_target(&c->source, replace);
}
static int replace_after(size_t expected_size, void *opaque) {
    pwp_replace_context *c = opaque;
    return rename_after(expected_size, &c->source);
}
static int replace_flush(void *opaque) {
    pwp_replace_context *c = opaque;
    return rename_flush(&c->source);
}
static pwp_result replace_candidate_locked(uint64_t token, const uint16_t *name, size_t length,
                                           const pwp_role_grant *original) {
    pwp_entry *file = entry(token);
    if (!file || !file->public_handle || file->directory || file->stage.phase != PWP_STAGE_EMPTY ||
        file->candidate.phase == PWP_CANDIDATE_EMPTY) return PWP_POLICY;
    if (file->candidate.phase != PWP_CANDIDATE_VERIFIED) return PWP_CLOSED;
    pwp_entry *parent = entry(file->parent); WCHAR target_path[PWP_PATH_LIMIT];
    if (file->parent != state.roles.identity || !parent || !parent->public_handle || !verify(parent) ||
        pwp_roles_check_stage(&state.roles, &state.owner, token) != PWP_OK) return PWP_POLICY;
    pwp_role_grant grant;
    pwp_result r = operation_grant(file->parent, original, &grant);
    if (r != PWP_OK) return r;
    if (!mutation_verify(&grant) || !join_name(parent, name, length, target_path)) return PWP_POLICY;
    if (owned_target(file->parent, target_path)) return PWP_POLICY;
    uint64_t probe = 0;
    /* FILE_OPEN/read-only/share-none on a fresh owner: no lock-file mode, DELETE/WRITE access,
     * sharing relaxation, repair, truncation or adoption of a held owner. The helper verifies the exact
     * private regular NTFS file, protected ACL, one link, no reparse/ADS and bounded size before return. */
    r = open_relative_access(file->parent, (const WCHAR *)name, length, target_path,
                               0, 0, 0, 1, 0, 0, 1, &probe);
    if (r != PWP_OK && r != PWP_NOT_FOUND) return r;
    /* Exact NOT_FOUND selects CREATE-ONLY. A later collision is a failed operation, never a replace retry. */
    pwp_replace_context operation = {{file, raw(token), name, length, target_path, grant},
                                     probe, entry(probe), raw(probe), 0, 0};
    r = pwp_candidate_replace(&file->candidate, &state.owner, probe, replace_before, replace_target_verify,
                               replace_target_close, replace_rename, replace_after, replace_flush, &operation);
    /* An invalid controller input does not transfer the unpublished probe. Retire it here only if the
     * controller never attempted its exact close; every admitted path already consumed that one attempt. */
    if (probe && !operation.close_attempted && retire(probe) != PWP_OK) r = PWP_CLEANUP_UNKNOWN;
    if (r == PWP_CLEANUP_UNKNOWN || file->candidate.phase == PWP_CANDIDATE_UNCERTAIN || state.owner.poisoned) {
        state.failed = 1; state.owner.poisoned = 1;
    }
    if (r == PWP_OK) memcpy(file->path, target_path, (wcslen(target_path)+1)*sizeof(WCHAR));
    return r;
}
pwp_result pwp_win_replace_candidate(uint64_t token, const uint16_t *name, size_t length) {
    if (!pwp_token_valid(token) || !pwp_candidate_replace_target(name, length, 1)) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    return end_stage(replace_candidate_locked(token, name, length, NULL));
}
typedef struct {
    uint64_t directory, candidate;
    const uint16_t *pending, *target;
    size_t pending_length, target_length, count;
    pwp_buffer_action copy;
    void *context;
    int replace;
    pwp_role_grant grant;
    pwp_entry *parent, *file;
    HANDLE parent_handle, handle;
    uint64_t identity[PWP_IDENTITY_WORDS];
    WCHAR target_path[PWP_PATH_LIMIT];
} pwp_write_context;
static pwp_result write_prepare(uint64_t *token, void *opaque) {
    pwp_write_context *c = opaque;
    pwp_result r = prepare_record_locked(c->directory, c->pending, c->pending_length, c->count,
                                         c->copy, c->context, token, &c->grant);
    c->candidate = *token;
    if (*token) {
        /* Adopt even a late returned owner on preparation failure. Low-level failures normally return
         * zero after their own cleanup; a nonzero returned owner remains this controller's obligation. */
        c->file = entry(*token); c->handle = raw(*token);
        if (!c->file || !c->handle || c->file->parent != c->directory ||
            c->file->candidate.phase == PWP_CANDIDATE_EMPTY) r = PWP_CLEANUP_UNKNOWN;
        else memcpy(c->identity, c->file->identity, sizeof(c->identity));
    }
    return pwp_cleanup_result(r, state.failed, state.owner.poisoned);
}
static int write_original_check(pwp_write_context *c, uint64_t token, pwp_candidate_phase phase,
                                 const WCHAR *path) {
    return token == c->candidate && c->file && entry(token) == c->file && raw(token) == c->handle &&
        c->file->public_handle && !c->file->directory && c->file->stage.phase == PWP_STAGE_EMPTY &&
        c->file->parent == c->directory && entry(c->directory) == c->parent &&
        raw(c->directory) == c->parent_handle && memcmp(c->file->identity, c->identity, sizeof(c->identity)) == 0 &&
        publication_check(c->count, c->file, c->handle, &c->grant, path, phase);
}
static pwp_result write_publish(uint64_t token, void *opaque) {
    pwp_write_context *c = opaque;
    if (!c->file || !write_original_check(c, token, PWP_CANDIDATE_VERIFIED, c->file->path))
        return pwp_cleanup_result(PWP_POLICY, state.failed, state.owner.poisoned);
    pwp_result r = c->replace ? replace_candidate_locked(token, c->target, c->target_length, &c->grant) :
        rename_candidate_locked(token, c->target, c->target_length, &c->grant);
    return pwp_cleanup_result(r, state.failed, state.owner.poisoned);
}
static pwp_result write_sync(uint64_t token, void *opaque) {
    pwp_write_context *c = opaque;
    if (!write_original_check(c, token, PWP_CANDIDATE_RENAMED, c->target_path))
        return pwp_cleanup_result(PWP_POLICY, state.failed, state.owner.poisoned);
    pwp_result r = sync_directory_locked(c->directory, &c->grant);
    r = pwp_cleanup_result(r, state.failed, state.owner.poisoned);
    if (r == PWP_OK && !write_original_check(c, token, PWP_CANDIDATE_RENAMED, c->target_path)) r = PWP_POLICY;
    return pwp_cleanup_result(r, state.failed, state.owner.poisoned);
}
static void write_uncertain(uint64_t token, void *opaque) {
    pwp_write_context *c = opaque;
    /* Memory only: mark the still-live original before its actual close. On a close failure the owner
     * is already quarantined; entry() returns NULL and no retired entry/OS handle is inspected or retried. */
    pwp_entry *file = token == c->candidate ? entry(token) : NULL;
    if (file && file == c->file && file->candidate.phase != PWP_CANDIDATE_EMPTY)
        file->candidate.phase = PWP_CANDIDATE_UNCERTAIN;
    state.failed = 1; state.owner.poisoned = 1;
}
static pwp_result write_close(uint64_t token, void *opaque) {
    pwp_write_context *c = opaque;
    if (token != c->candidate) return PWP_CLEANUP_UNKNOWN;
    /* No begin(), path verification, reopened owner or poison short-circuit: close the captured original
     * under the held gate exactly once. Do not dereference c->file after this potentially retiring call. */
    pwp_result r = retire(token);
    return pwp_cleanup_result(r, state.failed, state.owner.poisoned);
}
pwp_result pwp_win_write_record(uint64_t directory, const uint16_t *pending, size_t pending_length,
                                const uint16_t *target, size_t target_length, size_t count,
                                pwp_buffer_action copy, void *context, int replace) {
    if (!pwp_token_valid(directory) || !copy ||
        (!pwp_record_write_request(pending, pending_length, target, target_length, count, 0, replace) &&
         !pwp_record_write_request(pending, pending_length, target, target_length, count, 1, replace)))
        return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *parent = entry(directory);
    if (!parent || !parent->directory || !parent->public_handle ||
        (directory != state.roles.root && directory != state.roles.identity)) return end_stage(PWP_POLICY);
    /* Validate actual target scope and capture the original generation before any payload allocation/copy. */
    if (!pwp_record_write_request(pending, pending_length, target, target_length, count,
                                  directory == state.roles.identity, replace)) return end_stage(PWP_ARGUMENT);
    pwp_write_context operation = {0}; pwp_record_write write = {0};
    r = pwp_roles_capture(&state.roles, &state.owner, directory, &operation.grant);
    if (r != PWP_OK) return end_stage(r);
    if (!mutation_verify(&operation.grant) || !join_name(parent, target, target_length, operation.target_path))
        return end_stage(PWP_POLICY);
    operation.directory = directory; operation.pending = pending; operation.target = target;
    operation.pending_length = pending_length; operation.target_length = target_length; operation.count = count;
    operation.copy = copy; operation.context = context; operation.replace = replace;
    operation.parent = parent; operation.parent_handle = raw(directory);
    r = pwp_record_write_apply(&write, write_prepare, write_publish, write_sync, write_close, write_uncertain,
                               &operation);
    pwp_clear(&operation, sizeof(operation));
    return end_stage(r);
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
    if (!state.initialized) {
        pwp_owner_init(&state.owner); pwp_roles_init(&state.roles); state.initialized = 1;
    }
    if (state.active || state.failed || state.owner.poisoned) return end(PWP_CLOSED);
    pwp_result result = pwp_roles_begin_root(&state.roles, &state.owner);
    if (result != PWP_OK) return end(result);
    result = PWP_POLICY;
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
        result = i == 1 ? open_sync_directory(parent, parts[i], wcslen(parts[i]), current, 0, &child) :
            open_relative(parent, parts[i], wcslen(parts[i]), current, 1, 0, 0, 1, &child);
        if (result == PWP_NOT_FOUND)
            result = i == 1 ? open_sync_directory(parent, parts[i], wcslen(parts[i]), current, 1, &child) :
                open_relative(parent, parts[i], wcslen(parts[i]), current, 1, 1, 0, 1, &child);
        if (result != PWP_OK) goto failed;
        parent = child;
    }
    CoTaskMemFree(known); known = NULL;
    result = pwp_publish(&state.owner, parent);
    if (result == PWP_OK) result = pwp_roles_bind_root(&state.roles, &state.owner, parent);
    if (result != PWP_OK) goto failed;
    state.root = parent; state.active = 1; entry(parent)->public_handle = 1;
    *output = parent; return end(PWP_OK);
failed:
    if (known) CoTaskMemFree(known);
    if (state.failed) state.owner.poisoned = 1;
    if (pwp_roles_retire_all(&state.roles, &state.owner, close_os, NULL) != PWP_OK) {
        state.failed = 1; result = PWP_CLEANUP_UNKNOWN;
    }
    if (state.failed && result != PWP_CLEANUP_UNKNOWN) result = PWP_CLEANUP_UNKNOWN;
    return end(result == PWP_OK ? PWP_POLICY : result);
}
typedef struct { uint64_t token; int canonical, create; pwp_role_grant grant; } pwp_child_admission;
static int child_admission_verify(void *context) {
    pwp_child_admission *c = context;
    pwp_entry *child = entry(c->token);
    pwp_entry *parent = child ? entry(child->parent) : NULL;
    return !state.failed && !state.owner.poisoned && child && parent &&
        child->directory && !child->public_handle && parent->directory && parent->public_handle &&
        verify(parent) && verify(child) &&
        pwp_expected_child_directory(parent->identity, child->identity, PWP_IDENTITY_WORDS) &&
        (!c->canonical || (pwp_roles_identity_admit(&state.roles, &state.owner, child->parent) == PWP_OK &&
            pwp_vault_directory_scope(parent->identity, child->identity, PWP_IDENTITY_WORDS,
                (const uint16_t *)parent->path, wcslen(parent->path),
                (const uint16_t *)child->path, wcslen(child->path)))) &&
        (!c->create || mutation_verify(&c->grant)) &&
        !state.failed && !state.owner.poisoned;
}
static pwp_result child_publish(pwp_child_admission *context, uint64_t *output) {
    pwp_result r = pwp_child_finish(&state.owner, context->token, child_admission_verify, close_os, context);
    if (r == PWP_OK && context->canonical) {
        r = pwp_roles_bind_identity(&state.roles, &state.owner, entry(context->token)->parent, context->token);
        if (r != PWP_OK && retire(context->token) != PWP_OK) r = PWP_CLEANUP_UNKNOWN;
    }
    if (r == PWP_OK) { entry(context->token)->public_handle = 1; *output = context->token; }
    if (state.owner.poisoned) state.failed = 1;
    return r;
}
pwp_result pwp_win_child(uint64_t parent, const uint16_t *name, size_t length, uint64_t *child) {
    if (!child) return PWP_ARGUMENT;
    *child = 0;
    if (!pwp_token_valid(parent) || !pwp_component(name, length)) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(parent); WCHAR path[PWP_PATH_LIMIT];
    if (!p || !p->public_handle || !verify(p) || !join_name(p, name, length, path)) return end_stage(PWP_POLICY);
    int canonical = parent == state.roles.root && canonical_identity_name(name, length);
    if (canonical) {
        r = pwp_roles_identity_admit(&state.roles, &state.owner, parent);
        if (r != PWP_OK) return end_stage(r); /* Reject duplicate canonical-directory aliases before opening. */
    }
    if (pwp_public_count(&state.owner) >= PWP_PUBLIC_HANDLE_LIMIT) return end_stage(PWP_LIMIT);
    uint64_t token = 0;
    r = canonical ? open_sync_directory(parent, (const WCHAR *)name, length, path, 0, &token) :
        open_relative(parent, (const WCHAR *)name, length, path, 1, 0, 0, 1, &token);
    if (r != PWP_OK) return end_stage(r);
    pwp_child_admission context = {token, canonical, 0, {0}};
    return end_stage(child_publish(&context, child));
}
pwp_result pwp_win_create_child(uint64_t parent, const uint16_t *name, size_t length, uint64_t *child) {
    if (!child) return PWP_ARGUMENT;
    *child = 0;
    if (!pwp_token_valid(parent) || !pwp_component(name, length)) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(parent); WCHAR path[PWP_PATH_LIMIT];
    if (!canonical_identity_name(name, length) || !p || !p->public_handle || !p->directory ||
        !verify(p) || !join_name(p, name, length, path))
        return end_stage(PWP_POLICY);
    r = pwp_roles_identity_admit(&state.roles, &state.owner, parent);
    if (r != PWP_OK) return end_stage(r);
    pwp_role_grant grant;
    r = pwp_roles_capture(&state.roles, &state.owner, parent, &grant);
    if (r != PWP_OK) return end_stage(r);
    if (!mutation_verify(&grant)) return end_stage(PWP_POLICY);
    if (pwp_public_count(&state.owner) >= PWP_PUBLIC_HANDLE_LIMIT) return end_stage(PWP_LIMIT);
    uint64_t token = 0;
    /* The existing relative helper reserves before OS entry, installs the protected DACL at FILE_CREATE,
     * requires FILE_CREATED, and validates the exact returned handle. No failed open is rescued by create
     * and no collision is rescued by opening/replacing/deleting/repairing the pre-existing name. */
    r = open_sync_directory(parent, (const WCHAR *)name, length, path, 1, &token);
    if (r != PWP_OK) return end_stage(r);
    pwp_child_admission context = {token, 1, 1, grant};
    r = child_publish(&context, child);
    /* On failure a newly created directory may remain. Only handle retirement is claimed; there is
     * no pathname rollback, empty-directory assumption, directory flush or transaction commit. */
    return end_stage(r);
}
pwp_result pwp_win_identity(uint64_t token, uint64_t words[6]) {
    if (!words) return PWP_ARGUMENT;
    pwp_clear(words, 6*sizeof(uint64_t));
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *e = entry(token);
    if (!e || !e->public_handle || !verify(e)) return end_stage(PWP_POLICY);
    memcpy(words, e->identity, 6*sizeof(uint64_t)); return end_stage(PWP_OK);
}
pwp_result pwp_win_file_identity(uint64_t directory, const uint16_t *name, size_t length, uint64_t words[6]) {
    if (!words) return PWP_ARGUMENT;
    pwp_clear(words, 6*sizeof(uint64_t));
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(directory); WCHAR path[PWP_PATH_LIMIT]; uint64_t token = 0;
    if (!p || !p->public_handle || !verify(p) || !join_name(p, name, length, path)) return end_stage(PWP_POLICY);
    pwp_entry *held = owned_file(directory, path);
    if (held) {
        if (!verify(held)) return end_stage(PWP_POLICY);
        memcpy(words, held->identity, 6*sizeof(uint64_t)); return end_stage(PWP_OK);
    }
    r = open_relative(directory, (const WCHAR *)name, length, path, 0, 0, 0, 1, &token);
    if (r != PWP_OK) return end_stage(r);
    uint64_t observed[6]; memcpy(observed, entry(token)->identity, sizeof(observed));
    r = retire(token);
    if (r == PWP_OK) memcpy(words, observed, sizeof(observed));
    return end_stage(r);
}
pwp_result pwp_win_exists(uint64_t directory, const uint16_t *name, size_t length, int *exists) {
    if (!exists) return PWP_ARGUMENT;
    *exists = 0;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(directory); WCHAR path[PWP_PATH_LIMIT]; uint64_t token = 0;
    if (!p || !p->public_handle || !verify(p) || !join_name(p, name, length, path)) return end_stage(PWP_POLICY);
    pwp_entry *held = owned_file(directory, path);
    if (held) {
        if (!verify(held)) return end_stage(PWP_POLICY);
        *exists = 1; return end_stage(PWP_OK);
    }
    /* Unknown kind is queried on the actual opened handle; a failed file open is never inferred as a directory. */
    r = open_relative(directory, (const WCHAR *)name, length, path, -1, 0, 0, 1, &token);
    if (r == PWP_NOT_FOUND) return end_stage(PWP_OK);
    if (r != PWP_OK) return end_stage(r);
    r = retire(token);
    if (r == PWP_OK) *exists = 1;
    return end_stage(r);
}
static pwp_result collect_names(uint64_t directory, pwp_entry *p, pwp_directory_names *names) {
    pwp_result r = PWP_OK;
    /* Uncommitted stages/candidates are not ordinary records, irrespective of OS enumeration visibility. */
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i)
        if (state.owner.slots[i].state == 2 && state.entries[i].parent == directory &&
            !regular_entry(&state.entries[i])) return PWP_POLICY;
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
    return r;
}
typedef struct { uint64_t directory; pwp_entry *entry; pwp_names_action receive; void *context; } pwp_names_output;
static pwp_result names_collect_and_receive(unsigned char *bytes, size_t count, void *opaque) {
    pwp_names_output *output = opaque;
    if (count != sizeof(pwp_directory_names)) return PWP_ARGUMENT;
    pwp_directory_names *names = (pwp_directory_names *)bytes;
    pwp_result r = collect_names(output->directory, output->entry, names);
    return r == PWP_OK ? output->receive(names, output->context) : r;
}
pwp_result pwp_win_names(uint64_t directory, pwp_names_action receive, void *context) {
    if (!receive) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(directory);
    if (!p || !p->public_handle || !p->directory || !verify(p)) return end_stage(PWP_POLICY);
    pwp_names_output output = {directory, p, receive, context};
    _Static_assert(sizeof(pwp_directory_names) <= PWP_RECORD_LIMIT, "Directory result exceeds allocation bound");
    r = pwp_buffer_apply(sizeof(pwp_directory_names), names_collect_and_receive, &output);
    return end_stage(r);
}
static pwp_result read_bytes(uint64_t directory, const uint16_t *name, size_t length, const WCHAR *path,
                              unsigned char *output, size_t maximum, size_t *written) {
    uint64_t token = 0;
    pwp_result r = open_relative(directory, (const WCHAR *)name, length, path, 0, 0, 0, 1, &token);
    if (r != PWP_OK) return r;
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
    return r;
}
typedef struct {
    uint64_t directory;
    const uint16_t *name;
    size_t length;
    const WCHAR *path;
    pwp_buffer_action receive;
    void *context;
} pwp_read_output;
static pwp_result read_and_receive(unsigned char *bytes, size_t count, void *opaque) {
    pwp_read_output *output = opaque; size_t written = 0;
    pwp_result r = read_bytes(output->directory, output->name, output->length, output->path, bytes, count, &written);
    return r == PWP_OK ? output->receive(bytes, written, output->context) : r;
}
pwp_result pwp_win_read(uint64_t directory, const uint16_t *name, size_t length,
                        size_t maximum, pwp_buffer_action receive, void *context) {
    if (!receive || maximum > PWP_RECORD_LIMIT) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *p = entry(directory); WCHAR path[PWP_PATH_LIMIT];
    if (!p || !p->public_handle || !verify(p) || !join_name(p, name, length, path)) return end_stage(PWP_POLICY);
    pwp_entry *held = owned_file(directory, path);
    if (held && !regular_entry(held)) return end_stage(PWP_POLICY);
    pwp_read_output output = {directory, name, length, path, receive, context};
    r = pwp_buffer_apply(maximum, read_and_receive, &output);
    return end_stage(r);
}
/* New/existing locks share role verification; neither operation ever falls back to the other. */
typedef struct {
    uint64_t token, directory;
    pwp_lease_role role;
    const WCHAR *path;
} pwp_lock_context;
/* The shared publication controller runs under gate; this stack context never escapes or re-enters. */
static int lock_verify(void *context) {
    pwp_lock_context *c = context;
    pwp_entry *file = entry(c->token), *parent = entry(c->directory); FILE_STANDARD_INFO info;
    return !state.failed && !state.owner.poisoned && file && parent &&
        !file->directory && !file->public_handle && file->parent == c->directory &&
        lock_admission_verify(c->directory, c->role) && same_path(file->path, c->path) && verify(file) &&
        pwp_expected_lock_file(parent->identity, file->identity, PWP_IDENTITY_WORDS) &&
        GetFileInformationByHandleEx(raw(c->token), FileStandardInfo, &info, sizeof(info)) &&
        !info.Directory && !info.DeletePending && info.EndOfFile.QuadPart == 0 &&
        !state.failed && !state.owner.poisoned;
}
static int lock_flush(void *context) {
    pwp_lock_context *c = context;
    return !state.failed && !state.owner.poisoned && FlushFileBuffers(raw(c->token));
}
static pwp_result fixed_lock(uint64_t directory, pwp_lease_role role, int create, uint64_t *lease) {
    if (!lease) return PWP_ARGUMENT;
    *lease = 0;
    if (!pwp_token_valid(directory)) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_entry *parent = entry(directory); WCHAR path[PWP_PATH_LIMIT];
    const WCHAR *name = lease_name(role);
    r = pwp_roles_lease_admit(&state.roles, &state.owner, directory, role);
    if (r != PWP_OK) return end_stage(r);
    if (!name) return end_stage(PWP_ARGUMENT);
    size_t length = wcslen(name);
    if (!lock_admission_verify(directory, role) ||
        !join_name(parent, (const uint16_t *)name, length, path)) return end_stage(PWP_POLICY);
    /* Existing names are never opened/truncated/repaired by create; open-existing never creates them. */
    if (owned_file(directory, path)) return end_stage(PWP_BUSY);
    if (pwp_public_count(&state.owner) >= PWP_PUBLIC_HANDLE_LIMIT) return end_stage(PWP_LIMIT);
    uint64_t token = 0;
    r = open_relative(directory, name, length, path, 0, create, 1, 1, &token);
    if (r != PWP_OK) return end_stage(r);
    /* FILE_CREATE/FILE_OPEN + shareAccess=0 + READ/WRITE_DATA is the exclusive-handle lease contract.
     * No byte-range lock or recoverable namespace publication is claimed. Failed new empty files stay put. */
    pwp_lock_context context = {token, directory, role, path};
    r = pwp_lock_finish(&state.owner, token, lock_verify, lock_flush, close_os, &context);
    if (r == PWP_OK) {
        r = pwp_roles_bind_lease(&state.roles, &state.owner, directory, role, token);
        if (r != PWP_OK && retire(token) != PWP_OK) r = PWP_CLEANUP_UNKNOWN;
    }
    if (r == PWP_OK) { entry(token)->public_handle = 1; *lease = token; }
    if (state.owner.poisoned) state.failed = 1;
    return end_stage(r);
}
pwp_result pwp_win_lock(uint64_t directory, const uint16_t *name, size_t length, uint64_t *lease) {
    if (!lease) return PWP_ARGUMENT;
    *lease = 0;
    if (!pwp_token_valid(directory) || !pwp_component(name, length)) return PWP_ARGUMENT;
    pwp_lease_role role = pwp_lease_name(name, length);
    if (role == PWP_LEASE_NONE) return PWP_POLICY;
    return fixed_lock(directory, role, 0, lease);
}
pwp_result pwp_win_create_profile_lock(uint64_t root, uint64_t *lease) {
    return fixed_lock(root, PWP_LEASE_PROFILE, 1, lease);
}
pwp_result pwp_win_create_vault_lock(uint64_t identity_directory, uint64_t *lease) {
    return fixed_lock(identity_directory, PWP_LEASE_VAULT, 1, lease);
}
/* This context never escapes the serialized call. Its token is already RETIRING during callbacks;
 * use the saved original handle, never a live-token lookup or a fresh pathname open. */
typedef struct {
    pwp_entry *file; HANDLE handle;
    uint64_t expected[PWP_IDENTITY_WORDS];
    pwp_role_grant grant;
} pwp_delete_native;
static int deletion_verify_mode(pwp_delete_native *c, int pending) {
    uint64_t observed[PWP_IDENTITY_WORDS]; FILE_STANDARD_INFO standard;
    pwp_entry *parent = entry(c->file->parent);
    if (state.failed || state.owner.poisoned || !mutation_verify(&c->grant) ||
        !parent || !parent->public_handle || !parent->directory ||
        !verify(parent) || c->file->directory || c->file->public_handle ||
        !regular_entry(c->file) ||
        !pwp_expected_file(c->expected, PWP_IDENTITY_WORDS, parent->identity[1]) ||
        !no_impersonation() || !inspect_mode(c->handle, c->file->path, 0, 1, pending, observed) ||
        !GetFileInformationByHandleEx(c->handle, FileStandardInfo, &standard, sizeof(standard)) ||
        !!standard.DeletePending != pending || standard.Directory || standard.NumberOfLinks != 1)
        return 0;
    /* Pending-mode inspection deliberately has flags0, never the normal !DeletePending assertion. */
    for (size_t i = 0; i < PWP_IDENTITY_WORDS; ++i)
        if (observed[i] != (pending && i == 4 ? 0 : c->expected[i])) return 0;
    return mutation_verify(&c->grant) && !state.failed && !state.owner.poisoned;
}
static int deletion_verify(void *context) { return deletion_verify_mode(context, 0); }
static int deletion_pending_verify(void *context) { return deletion_verify_mode(context, 1); }
static int deletion_mark(void *context) {
    pwp_delete_native *c = context; FILE_DISPOSITION_INFO disposition = {TRUE};
    return !state.failed && !state.owner.poisoned && mutation_verify(&c->grant) &&
        SetFileInformationByHandle(c->handle, FileDispositionInfo, &disposition, sizeof(disposition));
}
static int deletion_close(uintptr_t resource, void *context) {
    pwp_delete_native *c = context;
    return resource == (uintptr_t)c->handle && CloseHandle(c->handle);
}
static pwp_result request_delete_locked(uint64_t directory, const uint16_t *name, size_t length,
                                        const uint64_t *expected, size_t count, const pwp_role_grant *original) {
    pwp_entry *parent = entry(directory); WCHAR path[PWP_PATH_LIMIT];
    if (!parent || !parent->public_handle || !parent->directory || !verify(parent) ||
        !pwp_expected_file(expected, count, parent->identity[1]) || !join_name(parent, name, length, path))
        return PWP_POLICY;
    pwp_role_grant grant;
    pwp_result r = operation_grant(directory, original, &grant);
    if (r != PWP_OK) return r;
    if (!mutation_verify(&grant)) return PWP_POLICY;
    /* Never borrow a live lock/stage handle, temporarily unlock it, or fall back to path deletion. */
    if (owned_file(directory, path)) return PWP_POLICY;
    uint64_t token = 0;
    r = open_relative_access(directory, (const WCHAR *)name, length, path, 0, 0, 0, 1, 1, 0, 0, &token);
    if (r != PWP_OK) return r; /* NOT_FOUND is an error, not successful absence. */
    pwp_delete_native operation = {entry(token), raw(token), {0}, grant};
    memcpy(operation.expected, expected, sizeof(operation.expected));
    r = pwp_delete_intent_finish(&state.owner, token, deletion_verify, deletion_mark,
                                 deletion_pending_verify, deletion_close, &operation);
    pwp_clear(operation.expected, sizeof(operation.expected));
    /* A mark/readback ambiguity stays quarantined even when CloseHandle returned success.
     * No retry, namespace-absence assertion, directory flush or transaction commit is implied. */
    if (state.owner.poisoned) state.failed = 1;
    return r;
}
pwp_result pwp_win_request_delete(uint64_t directory, const uint16_t *name, size_t length,
                                  const uint64_t *expected, size_t count) {
    /* Validate shape before any reservation or native entry; volume bits remain unsigned. */
    if (!pwp_token_valid(directory) || !pwp_component(name, length) || !expected ||
        count != PWP_IDENTITY_WORDS || !pwp_expected_file(expected, count, expected[1])) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    return end_stage(request_delete_locked(directory, name, length, expected, count, NULL));
}
typedef struct {
    uint64_t directory;
    const uint16_t *name;
    size_t length;
    pwp_role_grant grant;
    pwp_entry *parent;
    HANDLE parent_handle;
    uint64_t directory_identity[PWP_IDENTITY_WORDS], expected[PWP_IDENTITY_WORDS];
    WCHAR target_path[PWP_PATH_LIMIT];
} pwp_delete_record_native;
static int delete_record_parent_check(void *opaque) {
    pwp_delete_record_native *c = opaque;
    return entry(c->directory) == c->parent && raw(c->directory) == c->parent_handle &&
        c->parent && c->parent->directory && c->parent->public_handle &&
        memcmp(c->parent->identity, c->directory_identity, sizeof(c->directory_identity)) == 0 &&
        mutation_verify(&c->grant) && verify(c->parent) && mutation_verify(&c->grant);
}
static pwp_result delete_record_intent(void *opaque) {
    pwp_delete_record_native *c = opaque;
    if (!delete_record_parent_check(c)) return pwp_cleanup_result(PWP_POLICY, state.failed, state.owner.poisoned);
    pwp_result r = request_delete_locked(c->directory, c->name, c->length, c->expected,
                                         PWP_IDENTITY_WORDS, &c->grant);
    return pwp_cleanup_result(r, state.failed, state.owner.poisoned);
}
static pwp_result delete_record_absent(void *opaque) {
    pwp_delete_record_native *c = opaque;
    if (!delete_record_parent_check(c) || owned_target(c->directory, c->target_path))
        return pwp_cleanup_result(PWP_POLICY, state.failed, state.owner.poisoned);
    uint64_t probe = 0;
    pwp_result r = reserve(&probe); if (r != PWP_OK) return r;
    HANDLE handle = NULL; IO_STATUS_BLOCK io = {0};
    UNICODE_STRING text = {(USHORT)(c->length*sizeof(WCHAR)), (USHORT)(c->length*sizeof(WCHAR)), (PWSTR)c->name};
    OBJECT_ATTRIBUTES attributes;
    InitializeObjectAttributes(&attributes, &text, OBJ_CASE_INSENSITIVE, c->parent_handle, NULL);
    /* Strict read-only FILE_OPEN. Any object at the final component is a refusal, not an adopted file.
     * No create, DELETE, data-write, directory-kind assumption, repair, share relaxation or path fallback. */
    NTSTATUS status = NtCreateFile(&handle, READ_CONTROL | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
        &attributes, &io, NULL, FILE_ATTRIBUTE_NORMAL, FILE_SHARE_READ, PWP_FILE_OPEN,
        PWP_FILE_REPARSE | PWP_FILE_SYNCHRONOUS, NULL, 0);
    if (handle && handle != INVALID_HANDLE_VALUE && attach(probe, handle) != PWP_OK) {
        state.failed = 1; state.owner.poisoned = 1; return PWP_CLEANUP_UNKNOWN;
    }
    /* On a final nonpending return, the NTSTATUS itself is authoritative, not failure IOSB contents.
     * Never aggregate NAME_NOT_FOUND with PATH_NOT_FOUND via a DOS-error conversion. A non-NULL invalid
     * sentinel is not absence and is never closed. Any valid returned handle is retired exactly once. */
    r = pwp_name_absence_finish(&state.owner, probe, (uint32_t)status, handle == NULL,
                                 delete_record_parent_check, close_os, c);
    if (r == PWP_ARGUMENT) {
        /* Invalid controller arguments retain caller ownership; no admitted path returns ARGUMENT. */
        (void)retire(probe); r = PWP_CLEANUP_UNKNOWN;
    }
    return pwp_cleanup_result(r, state.failed, state.owner.poisoned);
}
static pwp_result delete_record_sync(void *opaque) {
    pwp_delete_record_native *c = opaque;
    if (!delete_record_parent_check(c)) return pwp_cleanup_result(PWP_POLICY, state.failed, state.owner.poisoned);
    pwp_result r = sync_directory_locked(c->directory, &c->grant);
    r = pwp_cleanup_result(r, state.failed, state.owner.poisoned);
    if (r == PWP_OK && !delete_record_parent_check(c)) r = PWP_POLICY;
    return pwp_cleanup_result(r, state.failed, state.owner.poisoned);
}
static void delete_record_uncertain(void *opaque) {
    (void)opaque;
    /* The original file may already be physically retired and its registry slot reused. Seal only
     * session authority; never reconstruct, inspect, reclose or relabel that retired resource. */
    state.failed = 1; state.owner.poisoned = 1;
}
pwp_result pwp_win_delete_record(uint64_t directory, const uint16_t *name, size_t length,
                                 const uint64_t *expected, size_t count) {
    if (!pwp_token_valid(directory) || !pwp_component(name, length) || !expected ||
        count != PWP_IDENTITY_WORDS || !pwp_expected_file(expected, count, expected[1])) return PWP_ARGUMENT;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    pwp_delete_record_native operation = {0}; pwp_record_delete deletion = {0};
    memcpy(operation.expected, expected, sizeof(operation.expected));
    operation.directory = directory; operation.name = name; operation.length = length;
    operation.parent = entry(directory); operation.parent_handle = raw(directory);
    r = PWP_POLICY;
    if (!operation.parent || !operation.parent->directory || !operation.parent->public_handle ||
        !pwp_expected_file(operation.expected, PWP_IDENTITY_WORDS, operation.parent->identity[1]) ||
        !join_name(operation.parent, name, length, operation.target_path)) goto done;
    memcpy(operation.directory_identity, operation.parent->identity, sizeof(operation.directory_identity));
    r = pwp_roles_capture(&state.roles, &state.owner, directory, &operation.grant);
    if (r != PWP_OK) goto done;
    r = pwp_record_delete_apply(&deletion, delete_record_intent, delete_record_absent, delete_record_sync,
                                 delete_record_uncertain, &operation);
done:
    pwp_clear(&operation, sizeof(operation));
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
        if (state.failed) state.owner.poisoned = 1;
        pwp_result r = pwp_roles_retire_all(&state.roles, &state.owner, close_os, NULL);
        if (r != PWP_OK) state.failed = 1;
        if (state.failed && r == PWP_OK) r = PWP_CLEANUP_UNKNOWN;
        state.terminal = r;
        return end(r);
    }
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i)
        if (state.owner.slots[i].state == 2 && state.entries[i].parent == token) return end(PWP_BUSY);
    return end(retire(token));
}
