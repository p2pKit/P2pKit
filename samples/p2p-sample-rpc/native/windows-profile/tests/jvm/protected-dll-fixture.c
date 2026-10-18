/* Development read fixture only. Never loads the candidate DLL or changes an existing object's ACL.
 * The ordinary maintained test-host/compiler context is a prerequisite, not installed authority.
 * EOF, timeout or uncertainty leaves the protected fixture; only a nonce-bound cleanup handshake
 * after the caller's original reader/capture retirement may delete our original file and empty dir. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <aclapi.h>
#include <bcrypt.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdint.h>
#include <wchar.h>
#include <string.h>

#define LIMIT 260
#define MAXIMUM_DLL (32u * 1024u * 1024u)
#define MUTATION 0x000d0156u
#define SCOPE "DEVELOPMENT_PROTECTED_DLL_READ_FIXTURE_NOT_INSTALLED_AUTHORITY"
static const wchar_t DLL_NAME[] = L"p2pkit-windows-profile.dll";
static const wchar_t PREFIX[] = L"P2pKit-Rpc-ReadFixture-";
static const char *stage = "PREFLIGHT";
static HANDLE parents[16], directory_handle, file_handle, writer, source_handle;
static unsigned parent_count;
static wchar_t directory_path[LIMIT], dll_path[LIMIT], nonce[37];
static wchar_t source_pin[41], tree_pin[41], dll_pin[65];
/* error_code records only immediate failed Win32 calls; zero also covers policy/identity refusal. */
static DWORD dll_bytes, error_code;
static int directory_created;
static FILE_ID_INFO directory_id, file_id, parent_ids[16];
_Alignas(DWORD) static BYTE admin_sid[SECURITY_MAX_SID_SIZE];
_Alignas(DWORD) static BYTE system_sid[SECURITY_MAX_SID_SIZE];
_Alignas(DWORD) static BYTE users_sid[SECURITY_MAX_SID_SIZE];
static PSID installer_sid;

static int good(HANDLE handle) { return handle != NULL && handle != INVALID_HANDLE_VALUE; }
static int hex(const wchar_t *value, size_t length) {
    size_t index;
    if (wcslen(value) != length) return 0;
    for (index = 0; index < length; ++index)
        if (!((value[index] >= L'0' && value[index] <= L'9') || (value[index] >= L'a' && value[index] <= L'f'))) return 0;
    return 1;
}
static int alphanumeric(wchar_t c) {
    return (c >= L'A' && c <= L'Z') || (c >= L'a' && c <= L'z') || (c >= L'0' && c <= L'9');
}
static int reserved(const wchar_t *start, size_t length) {
    size_t stem = 0;
    while (stem < length && start[stem] != L'.') ++stem;
    while (stem != 0 && start[stem - 1] == L' ') --stem;
    return (stem == 3 && (_wcsnicmp(start, L"CON", 3) == 0 || _wcsnicmp(start, L"PRN", 3) == 0 ||
        _wcsnicmp(start, L"AUX", 3) == 0 || _wcsnicmp(start, L"NUL", 3) == 0)) ||
        (stem == 4 && (_wcsnicmp(start, L"COM", 3) == 0 || _wcsnicmp(start, L"LPT", 3) == 0) &&
        start[3] >= L'1' && start[3] <= L'9');
}
static int path_valid(const wchar_t *path) {
    size_t index, count = wcslen(path), start = 3;
    if (count < 3 || count >= LIMIT || !((path[0] >= L'A' && path[0] <= L'Z') ||
        (path[0] >= L'a' && path[0] <= L'z')) || path[1] != L':' || path[2] != L'\\') return 0;
    for (index = 3; index <= count; ++index) {
        wchar_t c = path[index];
        if (c == L'\\' || c == 0) {
            if (index == start || index - start > 255 || !alphanumeric(path[start]) ||
                path[index - 1] == L'.' || path[index - 1] == L' ' || reserved(path + start, index - start)) return 0;
            start = index + 1;
        } else if (!((c >= L'A' && c <= L'Z') || (c >= L'a' && c <= L'z') ||
            (c >= L'0' && c <= L'9') || c == L' ' || c == L'.' || c == L'_' || c == L'-')) return 0;
    }
    return 1;
}
static void json_string(const wchar_t *value) {
    const wchar_t *cursor;
    putchar('"');
    for (cursor = value; *cursor; ++cursor) {
        if (*cursor == L'\\' || *cursor == L'"') putchar('\\');
        putchar((char)*cursor); /* Every printed path/pin is previously bounded ASCII. */
    }
    putchar('"');
}
static void id_string(const FILE_ID_INFO *id) {
    unsigned index;
    putchar('"');
    for (index = 0; index < 16; ++index) printf("%02x", id->FileId.Identifier[index]);
    putchar('"');
}
static void receipt(const char *phase, DWORD error) {
    printf("{\"schema\":1,\"scope\":\"" SCOPE "\",\"phase\":\"%s\",\"stage\":\"%s\",\"error\":%lu,", phase, stage, error);
    printf("\"nonce\":"); json_string(nonce);
    printf(",\"path\":"); json_string(dll_path);
    printf(",\"source\":"); json_string(source_pin);
    printf(",\"tree\":"); json_string(tree_pin);
    printf(",\"sha256\":"); json_string(dll_pin);
    printf(",\"bytes\":%lu,\"created\":%s,\"owner\":\"BUILTIN_ADMINISTRATORS\",", dll_bytes,
        directory_created ? "true" : "false");
    printf("\"volume\":\"%016llx\",\"directoryId\":", (unsigned long long)directory_id.VolumeSerialNumber);
    id_string(&directory_id); printf(",\"fileId\":"); id_string(&file_id); printf("}\n"); fflush(stdout);
}
static int trusted(PSID sid) {
    return sid != NULL && IsValidSid(sid) && (EqualSid(sid, admin_sid) || EqualSid(sid, system_sid) ||
        (installer_sid != NULL && EqualSid(sid, installer_sid)));
}
static int create_sids(void) {
    SID_IDENTIFIER_AUTHORITY nt = SECURITY_NT_AUTHORITY;
    DWORD size = sizeof(admin_sid);
    if (!CreateWellKnownSid(WinBuiltinAdministratorsSid, NULL, admin_sid, &size)) return 0;
    size = sizeof(system_sid);
    if (!CreateWellKnownSid(WinLocalSystemSid, NULL, system_sid, &size)) return 0;
    size = sizeof(users_sid);
    if (!CreateWellKnownSid(WinBuiltinUsersSid, NULL, users_sid, &size)) return 0;
    return AllocateAndInitializeSid(&nt, 6, 80, 956008885u, 3418522649u, 1831038044u,
        1853292631u, 2271478464u, 0, 0, &installer_sid) != 0;
}
static int safe_acl(HANDLE handle, int root, int exact_fixture, int is_directory) {
    PSECURITY_DESCRIPTOR descriptor = NULL;
    PSID owner = NULL;
    PACL acl = NULL;
    SECURITY_DESCRIPTOR_CONTROL control;
    DWORD revision, index, status, cursor = sizeof(ACL);
    int accepted = 0;
    GENERIC_MAPPING mapping = {FILE_GENERIC_READ, FILE_GENERIC_WRITE, FILE_GENERIC_EXECUTE, FILE_ALL_ACCESS};
    status = GetSecurityInfo(handle, SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
        &owner, NULL, &acl, NULL, &descriptor);
    if (status != ERROR_SUCCESS || descriptor == NULL) goto done;
    if (!IsValidSecurityDescriptor(descriptor) || GetSecurityDescriptorLength(descriptor) > 65536 ||
        !GetSecurityDescriptorControl(descriptor, &control, &revision) || !trusted(owner) ||
        ((SECURITY_DESCRIPTOR_RELATIVE *)descriptor)->Sacl != 0 || acl == NULL || !IsValidAcl(acl) || (control & (SE_DACL_PRESENT | SE_SELF_RELATIVE)) !=
        (SE_DACL_PRESENT | SE_SELF_RELATIVE) || (control & ~0xbf3fu) != 0 ||
        (acl->AclRevision != ACL_REVISION && acl->AclRevision != ACL_REVISION_DS) || acl->Sbz1 != 0 || acl->Sbz2 != 0) goto done;
    if (exact_fixture && (!EqualSid(owner, admin_sid) || (control & SE_DACL_PROTECTED) == 0 || acl->AceCount != 3)) goto done;
    for (index = 0; index < acl->AceCount; ++index) {
        ACE_HEADER *header = NULL;
        ACCESS_ALLOWED_ACE *ace;
        DWORD mask, forbidden = root ? MUTATION & ~6u : MUTATION;
        PSID sid;
        if (!GetAce(acl, index, (void **)&header) || header == NULL ||
            (header->AceType != ACCESS_ALLOWED_ACE_TYPE && header->AceType != ACCESS_DENIED_ACE_TYPE) ||
            (header->AceFlags & ~0x1fu) != 0 || header->AceSize < 16 ||
            (BYTE *)header != (BYTE *)acl + cursor || cursor > acl->AclSize || header->AceSize > acl->AclSize - cursor) goto done;
        cursor += header->AceSize;
        ace = (ACCESS_ALLOWED_ACE *)header; sid = (PSID)&ace->SidStart;
        if (!IsValidSid(sid) || GetLengthSid(sid) != header->AceSize - 8u ||
            (ace->Mask & ~(0x001f01ffu | 0xf0000000u)) != 0) goto done;
        if (exact_fixture) {
            PSID expected = index == 0 ? system_sid : index == 1 ? admin_sid : users_sid;
            DWORD rights = index < 2 ? FILE_ALL_ACCESS : FILE_GENERIC_READ | FILE_GENERIC_EXECUTE;
            BYTE flags = is_directory ? OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE : 0;
            if (header->AceType != ACCESS_ALLOWED_ACE_TYPE || header->AceFlags != flags ||
                !EqualSid(sid, expected) || ace->Mask != rights) goto done;
        }
        mask = ace->Mask; MapGenericMask(&mask, &mapping);
        if (header->AceType == ACCESS_ALLOWED_ACE_TYPE && (header->AceFlags & INHERIT_ONLY_ACE) == 0 &&
            !trusted(sid) && (mask & forbidden) != 0) goto done;
    }
    while (cursor < acl->AclSize) if (((BYTE *)acl)[cursor++] != 0) goto done;
    accepted = 1;
done:
    if (descriptor != NULL) LocalFree(descriptor);
    return accepted;
}
static int initial_security(SECURITY_DESCRIPTOR *descriptor, ACL *acl, DWORD bytes, int directory,
    SECURITY_ATTRIBUTES *attributes) {
    DWORD flags = directory ? OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE : 0;
    ZeroMemory(acl, bytes);
    if (!InitializeSecurityDescriptor(descriptor, SECURITY_DESCRIPTOR_REVISION) || !InitializeAcl(acl, bytes, ACL_REVISION) ||
        !AddAccessAllowedAceEx(acl, ACL_REVISION, flags, FILE_ALL_ACCESS, system_sid) ||
        !AddAccessAllowedAceEx(acl, ACL_REVISION, flags, FILE_ALL_ACCESS, admin_sid) ||
        !AddAccessAllowedAceEx(acl, ACL_REVISION, flags, FILE_GENERIC_READ | FILE_GENERIC_EXECUTE, users_sid) ||
        !SetSecurityDescriptorOwner(descriptor, admin_sid, FALSE) || !SetSecurityDescriptorDacl(descriptor, TRUE, acl, FALSE) ||
        !SetSecurityDescriptorControl(descriptor, SE_DACL_PROTECTED, SE_DACL_PROTECTED)) return 0;
    attributes->nLength = sizeof(*attributes); attributes->lpSecurityDescriptor = descriptor; attributes->bInheritHandle = FALSE;
    return 1;
}
static int identity(HANDLE handle, int directory, FILE_ID_INFO *id, FILE_STANDARD_INFO *standard) {
    FILE_ATTRIBUTE_TAG_INFO tag;
    DWORD case_flags = 0xffffffffu;
    if (!GetFileInformationByHandleEx(handle, FileIdInfo, id, sizeof(*id)) ||
        !GetFileInformationByHandleEx(handle, FileStandardInfo, standard, sizeof(*standard)) ||
        !GetFileInformationByHandleEx(handle, FileAttributeTagInfo, &tag, sizeof(tag))) return 0;
    if (id->VolumeSerialNumber == 0 || standard->AllocationSize.QuadPart < 0 || standard->EndOfFile.QuadPart < 0 ||
        standard->NumberOfLinks == 0 || standard->DeletePending || (standard->Directory != FALSE) != directory ||
        ((tag.FileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) != directory || tag.ReparseTag != 0 ||
        (tag.FileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_OFFLINE)) != 0) return 0;
    if (directory && (!GetFileInformationByHandleEx(handle, (FILE_INFO_BY_HANDLE_CLASS)23, &case_flags, 4) || case_flags != 0)) return 0;
    return memcmp(id->FileId.Identifier, "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0", 16) != 0;
}
static int same_id(const FILE_ID_INFO *left, const FILE_ID_INFO *right) {
    return left->VolumeSerialNumber == right->VolumeSerialNumber && memcmp(left->FileId.Identifier, right->FileId.Identifier, 16) == 0;
}
static int original(HANDLE handle, int directory, const FILE_ID_INFO *expected, int fixture) {
    FILE_ID_INFO actual; FILE_STANDARD_INFO standard;
    return identity(handle, directory, &actual, &standard) && same_id(&actual, expected) &&
        (directory || (standard.NumberOfLinks == 1 && standard.EndOfFile.QuadPart == dll_bytes)) &&
        (!fixture || safe_acl(handle, 0, 1, directory));
}
static int ancestors(const wchar_t *program_files) {
    wchar_t prefix[LIMIT], guid[64], final_path[512], fs[32];
    DWORD flags, maximum, length, index; size_t cut, count = wcslen(program_files);
    FILE_STANDARD_INFO standard;
    wcscpy_s(prefix, LIMIT, program_files); prefix[3] = 0;
    for (cut = 3; cut <= count; ++cut) {
        if (cut != 3 && cut != count && program_files[cut] != L'\\') continue;
        if (cut != 3) { wmemcpy(prefix, program_files, cut); prefix[cut] = 0; }
        if (parent_count >= 16) return 0;
        parents[parent_count] = CreateFileW(prefix, READ_CONTROL | FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE,
            NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
        if (!good(parents[parent_count]) || !identity(parents[parent_count], 1, &parent_ids[parent_count], &standard) ||
            !safe_acl(parents[parent_count], parent_count == 0, 0, 1)) return 0;
        if (parent_count == 0) {
            length = GetFinalPathNameByHandleW(parents[0], guid, 64, VOLUME_NAME_GUID);
            if (length != 49 || guid[49] != 0 || wcsncmp(guid, L"\\\\?\\Volume{", 11) != 0 ||
                guid[47] != L'}' || guid[48] != L'\\' || GetDriveTypeW(guid) != DRIVE_FIXED ||
                !GetVolumeInformationByHandleW(parents[0], NULL, 0, NULL, &maximum, &flags, fs, 32) ||
                wcscmp(fs, L"NTFS") != 0 || maximum < 255 || (flags & FILE_PERSISTENT_ACLS) == 0) return 0;
        } else if (parent_ids[parent_count].VolumeSerialNumber != parent_ids[0].VolumeSerialNumber) return 0;
        length = GetFinalPathNameByHandleW(parents[parent_count], final_path, 512, VOLUME_NAME_GUID);
        if (length != 49 + cut - 3 || _wcsnicmp(guid, final_path, 49) != 0 ||
            _wcsnicmp(final_path + 49, program_files + 3, cut - 3) != 0 || final_path[length] != 0) return 0;
        ++parent_count;
    }
    for (index = 0; index < parent_count; ++index) {
        FILE_ID_INFO again;
        if (!identity(parents[index], 1, &again, &standard) || !same_id(&again, &parent_ids[index])) return 0;
    }
    return parent_count >= 2;
}
static int sha_finish(BCRYPT_HASH_HANDLE hash, const wchar_t *expected) {
    BYTE result[32]; wchar_t text[65]; unsigned index;
    if (BCryptFinishHash(hash, result, 32, 0) != 0) return 0;
    for (index = 0; index < 32; ++index) swprintf_s(text + index * 2, 65 - index * 2, L"%02x", result[index]);
    return wcscmp(text, expected) == 0;
}
static int copy_or_check(HANDLE input, HANDLE output) {
    BCRYPT_ALG_HANDLE algorithm = NULL; BCRYPT_HASH_HANDLE hash = NULL;
    BYTE object[4096], bytes[65536]; DWORD object_bytes, returned, read, written, total = 0;
    FILE_ID_INFO before, after; FILE_STANDARD_INFO first, last;
    int accepted = 0;
    if (!identity(input, 0, &before, &first) || first.NumberOfLinks != 1 || first.EndOfFile.QuadPart != dll_bytes ||
        BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, MS_PRIMITIVE_PROVIDER, 0) != 0 ||
        BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, (PUCHAR)&object_bytes, 4, &returned, 0) != 0 ||
        returned != 4 || object_bytes == 0 || object_bytes > sizeof(object) ||
        BCryptCreateHash(algorithm, &hash, object, object_bytes, NULL, 0, 0) != 0) goto done;
    while (total < dll_bytes) {
        DWORD wanted = dll_bytes - total < sizeof(bytes) ? dll_bytes - total : (DWORD)sizeof(bytes);
        if (!ReadFile(input, bytes, wanted, &read, NULL) || read != wanted ||
            BCryptHashData(hash, bytes, read, 0) != 0 ||
            (good(output) && (!WriteFile(output, bytes, read, &written, NULL) || written != read))) goto done;
        total += read;
    }
    if (!ReadFile(input, bytes, 1, &read, NULL) || read != 0 || !sha_finish(hash, dll_pin) ||
        (good(output) && !FlushFileBuffers(output)) || !identity(input, 0, &after, &last) || !same_id(&before, &after) ||
        first.EndOfFile.QuadPart != last.EndOfFile.QuadPart || first.AllocationSize.QuadPart != last.AllocationSize.QuadPart ||
        first.NumberOfLinks != last.NumberOfLinks) goto done;
    accepted = 1;
done:
    SecureZeroMemory(bytes, sizeof(bytes));
    if (hash != NULL) BCryptDestroyHash(hash);
    if (algorithm != NULL) BCryptCloseAlgorithmProvider(algorithm, 0);
    SecureZeroMemory(object, sizeof(object));
    return accepted;
}
static int provision(const wchar_t *source) {
    PWSTR known = NULL; GUID random;
    union { void *align; BYTE bytes[512]; } acl;
    SECURITY_DESCRIPTOR descriptor; SECURITY_ATTRIBUTES attributes;
    FILE_STANDARD_INFO standard; LARGE_INTEGER zero; zero.QuadPart = 0;
    if (SHGetKnownFolderPath(&FOLDERID_ProgramFiles, KF_FLAG_DONT_VERIFY, NULL, &known) != S_OK || known == NULL ||
        !path_valid(known) || !ancestors(known) || CoCreateGuid(&random) != S_OK) goto refused;
    if (wcslen(known) + 1 + wcslen(PREFIX) + 36 + 1 + wcslen(DLL_NAME) >= LIMIT) goto refused;
    swprintf_s(nonce, 37, L"%08lx-%04x-%04x-%02x%02x-%02x%02x%02x%02x%02x%02x", random.Data1, random.Data2, random.Data3,
        random.Data4[0], random.Data4[1], random.Data4[2], random.Data4[3], random.Data4[4], random.Data4[5], random.Data4[6], random.Data4[7]);
    if (swprintf_s(directory_path, LIMIT, L"%ls\\%ls%ls", known, PREFIX, nonce) < 0 ||
        swprintf_s(dll_path, LIMIT, L"%ls\\%ls", directory_path, DLL_NAME) < 0 || !path_valid(dll_path)) goto refused;
    source_handle = CreateFileW(source, GENERIC_READ | READ_CONTROL, FILE_SHARE_READ, NULL, OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (!good(source_handle)) { error_code = GetLastError(); goto refused; }
    if (!copy_or_check(source_handle, NULL) || !SetFilePointerEx(source_handle, zero, NULL, FILE_BEGIN)) goto refused;
    stage = "CREATE_DIRECTORY";
    if (!initial_security(&descriptor, (ACL *)acl.bytes, sizeof(acl.bytes), 1, &attributes)) goto refused;
    if (!CreateDirectoryW(directory_path, &attributes)) { error_code = GetLastError(); goto refused; }
    directory_created = 1;
    directory_handle = CreateFileW(directory_path, READ_CONTROL | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (!good(directory_handle) || !identity(directory_handle, 1, &directory_id, &standard) ||
        directory_id.VolumeSerialNumber != parent_ids[0].VolumeSerialNumber || !safe_acl(directory_handle, 0, 1, 1)) goto refused;
    stage = "CREATE_FILE";
    if (!initial_security(&descriptor, (ACL *)acl.bytes, sizeof(acl.bytes), 0, &attributes)) goto refused;
    writer = CreateFileW(dll_path, GENERIC_READ | GENERIC_WRITE | READ_CONTROL | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, &attributes, CREATE_NEW, FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (!good(writer)) { error_code = GetLastError(); goto refused; }
    stage = "COPY";
    if (!copy_or_check(source_handle, writer) || !SetFilePointerEx(writer, zero, NULL, FILE_BEGIN) ||
        !copy_or_check(writer, NULL) || !identity(writer, 0, &file_id, &standard) || standard.NumberOfLinks != 1 ||
        file_id.VolumeSerialNumber != directory_id.VolumeSerialNumber || standard.EndOfFile.QuadPart != dll_bytes ||
        !safe_acl(writer, 0, 1, 0)) goto refused;
    /* Only original-object ReOpenFile, no later path lookup; metadata handles carry no WRITE or DELETE access.
     * Their sharing permits this original writer until it is CLOSED BEFORE publication/Java. */
    file_handle = ReOpenFile(writer, READ_CONTROL | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, FILE_FLAG_OPEN_REPARSE_POINT);
    if (!good(file_handle) || !original(file_handle, 0, &file_id, 1) || !CloseHandle(writer)) goto refused;
    writer = NULL;
    if (!CloseHandle(source_handle)) goto refused;
    source_handle = NULL;
    if (!original(directory_handle, 1, &directory_id, 1)) goto refused;
    CoTaskMemFree(known); stage = "READY"; return 1;
refused:
    if (known != NULL) CoTaskMemFree(known);
    return 0; /* Never guess at rollback of a partially created object. */
}
static int directory_file_descriptor(const BY_HANDLE_FILE_INFORMATION *information, FILE_ID_DESCRIPTOR *descriptor) {
    ZeroMemory(descriptor, sizeof(*descriptor));
    if ((information->dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) == 0 ||
        (information->nFileIndexHigh == 0 && information->nFileIndexLow == 0)) return 0;
    descriptor->dwSize = sizeof(*descriptor);
    descriptor->Type = FileIdType;
    descriptor->FileId.HighPart = (LONG)information->nFileIndexHigh;
    descriptor->FileId.LowPart = information->nFileIndexLow;
    return 1;
}
static int original_parents(void) {
    unsigned index;
    if (parent_count < 2 || parent_count > 16) return 0;
    for (index = 0; index < parent_count; ++index) {
        if (!original(parents[index], 1, &parent_ids[index], 0) ||
            !safe_acl(parents[index], index == 0, 0, 1)) return 0;
    }
    return 1;
}
static int directory_guid_path_matches(const wchar_t *root, const wchar_t *actual, const wchar_t *expected) {
    size_t index, count = wcslen(expected);
    if (wcslen(root) != 49 || wcsncmp(root, L"\\\\?\\Volume{", 11) != 0 || root[47] != L'}' || root[48] != L'\\' ||
        !path_valid(expected) || count <= 3 || wcslen(actual) != 49 + count - 3) return 0;
    for (index = 11; index < 47; ++index) {
        wchar_t c = root[index];
        if (index == 19 || index == 24 || index == 29 || index == 34) {
            if (c != L'-') return 0;
        } else if (!((c >= L'0' && c <= L'9') || (c >= L'a' && c <= L'f') || (c >= L'A' && c <= L'F'))) return 0;
    }
    return _wcsnicmp(actual, root, 49) == 0 && _wcsicmp(actual + 49, expected + 3) == 0;
}
static int cleanup(void) {
    HANDLE deletion = NULL;
    FILE_DISPOSITION_INFO disposition = {TRUE};
    wchar_t root[64] = {0}, directory[512] = {0}, reopened[512] = {0};
    DWORD length;
    stage = "VERIFY_DIRECTORY_PATH";
    if (good(writer) || !original_parents() || !original(directory_handle, 1, &directory_id, 1) ||
        !original(file_handle, 0, &file_id, 1)) return 0;
    stage = "QUERY_DIRECTORY_PATH";
    length = GetFinalPathNameByHandleW(parents[0], root, 64, VOLUME_NAME_GUID);
    if (length == 0) { error_code = GetLastError(); return 0; }
    if (length != 49 || root[length] != 0) return 0;
    length = GetFinalPathNameByHandleW(directory_handle, directory, 512, VOLUME_NAME_GUID);
    if (length == 0) { error_code = GetLastError(); return 0; }
    if (length >= 512 || directory[length] != 0 ||
        !directory_guid_path_matches(root, directory, directory_path)) return 0;
    stage = "DELETE_FILE";
    deletion = ReOpenFile(file_handle, DELETE | READ_CONTROL | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, FILE_FLAG_OPEN_REPARSE_POINT);
    if (!good(deletion)) { error_code = GetLastError(); return 0; }
    if (!original(deletion, 0, &file_id, 1)) return 0;
    if (!SetFileInformationByHandle(deletion, FileDispositionInfo, &disposition, sizeof(disposition))) {
        error_code = GetLastError(); return 0;
    }
    if (!CloseHandle(deletion) || !CloseHandle(file_handle)) return 0;
    file_handle = NULL;
    stage = "OPEN_DIRECTORY_PATH";
    /* Primary reopen only: our retained run refused directory ReOpenFile, then rejected disposition
     * on the otherwise identity-verified OpenFileById handle. The locator is the ORIGINAL held
     * directory's volume-GUID path under our held protected ancestors, never a caller/DOS alias.
     * Resolving that locator grants no deletion authority: full original ID, path and ACL checks
     * below must succeed before the sole handle-based disposition. There is no fallback/retry. */
    deletion = CreateFileW(directory, DELETE | READ_CONTROL | FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (!good(deletion)) { error_code = GetLastError(); return 0; }
    stage = "VERIFY_DIRECTORY_PATH";
    if (!original(deletion, 1, &directory_id, 1)) return 0;
    length = GetFinalPathNameByHandleW(deletion, reopened, 512, VOLUME_NAME_GUID);
    if (length == 0) { error_code = GetLastError(); return 0; }
    if (length >= 512 || reopened[length] != 0 || !directory_guid_path_matches(root, reopened, directory_path) ||
        _wcsicmp(reopened, directory) != 0 || !original_parents() ||
        !original(directory_handle, 1, &directory_id, 1)) return 0;
    stage = "DISPOSE_DIRECTORY";
    if (!SetFileInformationByHandle(deletion, FileDispositionInfo, &disposition, sizeof(disposition))) {
        error_code = GetLastError(); return 0;
    }
    if (!CloseHandle(deletion) || !CloseHandle(directory_handle)) return 0;
    directory_handle = NULL;
    stage = "CLEANED"; return 1;
}
static int command_matches(const char *command, const wchar_t *expected) {
    unsigned index;
    if (strlen(command) != 45 || memcmp(command, "CLEANUP ", 8) != 0 || command[44] != '\n') return 0;
    for (index = 0; index < 36; ++index) if ((unsigned char)command[index + 8] != expected[index]) return 0;
    return 1;
}
static int await_cleanup(void) {
    char command[46] = {0}; DWORD total = 0; ULONGLONG started = GetTickCount64();
    HANDLE input = GetStdHandle(STD_INPUT_HANDLE);
    /* Helper lifetime only: does not extend the caller's existing 60-second reader deadline. */
    while (GetTickCount64() - started < 90000) {
        DWORD available = 0, read = 0;
        if (!PeekNamedPipe(input, NULL, 0, NULL, &available, NULL)) return 0; /* EOF/broken pipe => preserve. */
        if (available != 0) {
            if (available > 45 - total || !ReadFile(input, command + total, available, &read, NULL) || read != available) return 0;
            total += read;
            if (memchr(command, '\n', total) != NULL) return command_matches(command, nonce);
        }
        Sleep(10);
    }
    return 0;
}
static int self_test(void) {
    SECURITY_DESCRIPTOR descriptor; SECURITY_ATTRIBUTES attributes;
    BY_HANDLE_FILE_INFORMATION information;
    FILE_ID_DESCRIPTOR file_descriptor;
    union { void *align; BYTE bytes[512]; } acl;
    const wchar_t *root = L"\\\\?\\Volume{01234567-89ab-cdef-0123-456789abcdef}\\";
    const wchar_t *path = L"\\\\?\\Volume{01234567-89ab-cdef-0123-456789abcdef}\\Program Files\\Owned";
    if (!directory_guid_path_matches(root, path, L"C:\\Program Files\\Owned") ||
        !directory_guid_path_matches(root, path, L"D:\\program files\\owned") ||
        directory_guid_path_matches(root, path, L"C:\\Program Files\\Other") ||
        directory_guid_path_matches(root, path, L"C:\\Program Files\\..\\Owned") ||
        directory_guid_path_matches(root, path, L"C:\\Program Files\\Owned ") ||
        directory_guid_path_matches(root, path, L"C:\\Program Files\\Owned:stream") ||
        directory_guid_path_matches(L"\\\\?\\Volume{11234567-89ab-cdef-0123-456789abcdef}\\", path, L"C:\\Program Files\\Owned") ||
        directory_guid_path_matches(L"\\\\?\\Volume{01234567_89ab-cdef-0123-456789abcdef}\\", path, L"C:\\Program Files\\Owned") ||
        directory_guid_path_matches(L"C:\\", path, L"C:\\Program Files\\Owned") ||
        directory_guid_path_matches(root, L"C:\\Program Files\\Owned", L"C:\\Program Files\\Owned")) return 0;
    /* Preserve the earlier inert FileIdType descriptor controls as historical regression coverage;
     * the live cleanup no longer uses a by-ID handle for disposition. */
    ZeroMemory(&information, sizeof(information));
    information.dwFileAttributes = FILE_ATTRIBUTE_DIRECTORY;
    if (directory_file_descriptor(&information, &file_descriptor)) return 0;
    information.nFileIndexHigh = 0x80000001u;
    information.nFileIndexLow = 0xfedcba98u;
    if (!directory_file_descriptor(&information, &file_descriptor) || file_descriptor.dwSize != sizeof(file_descriptor) ||
        file_descriptor.Type != FileIdType || (DWORD)file_descriptor.FileId.HighPart != information.nFileIndexHigh ||
        file_descriptor.FileId.LowPart != information.nFileIndexLow) return 0;
    information.nFileIndexHigh = 0;
    if (!directory_file_descriptor(&information, &file_descriptor) || file_descriptor.FileId.HighPart != 0 ||
        file_descriptor.FileId.LowPart != information.nFileIndexLow) return 0;
    information.nFileIndexHigh = 1;
    information.nFileIndexLow = 0;
    if (!directory_file_descriptor(&information, &file_descriptor) || file_descriptor.FileId.HighPart != 1 ||
        file_descriptor.FileId.LowPart != 0) return 0;
    information.dwFileAttributes = FILE_ATTRIBUTE_NORMAL;
    if (directory_file_descriptor(&information, &file_descriptor)) return 0;
    if (!initial_security(&descriptor, (ACL *)acl.bytes, sizeof(acl.bytes), 1, &attributes) ||
        !IsValidSecurityDescriptor(&descriptor) || !command_matches("CLEANUP 01234567-89ab-cdef-0123-456789abcdef\n", L"01234567-89ab-cdef-0123-456789abcdef") ||
        command_matches("CLEANUP 01234567-89ab-cdef-0123-456789abcdef\n", L"11234567-89ab-cdef-0123-456789abcdef") ||
        command_matches("CLEANUP 01234567-89ab-cdef-0123-456789abcdef\nx", L"01234567-89ab-cdef-0123-456789abcdef") ||
        !path_valid(L"C:\\Program Files\\P2pKit-Rpc-ReadFixture-01234567-89ab-cdef-0123-456789abcdef\\p2pkit-windows-profile.dll") ||
        path_valid(L"C:\\Program Files\\..\\p2pkit-windows-profile.dll")) return 0;
    puts("WINDOWS_PROTECTED_DLL_FIXTURE_SELF_TEST_PASS scope=INERT_DESCRIPTOR_AND_PROTOCOL_NOT_FILESYSTEM_OR_AUTHORITY"); return 1;
}
int wmain(int argc, wchar_t **argv) {
    wchar_t *end = NULL; unsigned long size; size_t index;
    _Static_assert(sizeof(void *) == 8, "Only the maintained Windows x64 test host is supported");
    if (!create_sids()) return 2;
    if (argc == 2 && wcscmp(argv[1], L"--self-test") == 0) return self_test() ? 0 : 2;
    if (argc != 6 || !path_valid(argv[1]) || !hex(argv[3], 64) || !hex(argv[4], 40) || !hex(argv[5], 40)) return 2;
    if (wcslen(argv[2]) == 0 || wcslen(argv[2]) > 8 || argv[2][0] == L'0') return 2;
    for (index = 0; argv[2][index]; ++index) if (argv[2][index] < L'0' || argv[2][index] > L'9') return 2;
    if (wcscmp(wcsrchr(argv[1], L'\\') + 1, DLL_NAME) != 0) return 2;
    size = wcstoul(argv[2], &end, 10);
    if (end == argv[2] || *end != 0 || size < 512 || size > MAXIMUM_DLL) return 2;
    dll_bytes = (DWORD)size; wcscpy_s(dll_pin, 65, argv[3]); wcscpy_s(source_pin, 41, argv[4]); wcscpy_s(tree_pin, 41, argv[5]);
    if (!provision(argv[1])) { receipt("FAILED", error_code); return 1; }
    receipt("READY", 0);
    if (!await_cleanup()) { stage = "PRESERVED"; receipt("LEFT", 0); return 3; }
    if (!cleanup()) { receipt("LEFT", error_code); return 1; }
    receipt("CLEANED", 0);
    return 0; /* OS closes only remaining read-only metadata/ancestor handles at process exit. */
}
