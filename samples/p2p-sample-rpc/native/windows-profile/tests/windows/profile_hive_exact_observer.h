#ifndef P2PKIT_PROFILE_HIVE_EXACT_OBSERVER_H
#define P2PKIT_PROFILE_HIVE_EXACT_OBSERVER_H

/* Test-executable exact-SID lookup only. No value reads, enumeration, notification/event,
 * profile changes, privilege grants, alternate API, or protected-storage authority.
 * The caller supplies the canonical SID from its verified fresh-account token's
 * ConvertSidToStringSidW result, never an external path or another account's identity. */
#ifndef P2PKIT_HIVE_EXACT_INERT_CONTROL
#include <windows.h>
#include <winternl.h>
NTSYSAPI NTSTATUS NTAPI NtOpenKey(PHANDLE KeyHandle, ACCESS_MASK DesiredAccess,
    POBJECT_ATTRIBUTES ObjectAttributes);
#endif

#define P2PKIT_HIVE_EXACT_SID_CHARS 184u
#define P2PKIT_HIVE_EXACT_MAXIMUM_LOOKUPS 65536u
#define P2PKIT_HIVE_EXACT_NAME_NOT_FOUND 0xc0000034u
#define P2PKIT_HIVE_EXACT_ERROR 0
#define P2PKIT_HIVE_EXACT_PRESENT 1
#define P2PKIT_HIVE_EXACT_ABSENT 2

typedef DWORD (*p2pkit_hive_exact_remaining)(void *context);

typedef struct {
    HKEY parent, child;
    WCHAR sid[P2PKIT_HIVE_EXACT_SID_CHARS];
    DWORD sid_length;
    DWORD parent_open_status, last_lookup_status, child_close_status, parent_close_status, system_error;
    DWORD lookups, presences, absences, child_closes;
    int started, sealed, retired, absence_observed;
    int parent_owned, child_owned, parent_close_attempted, child_close_attempted, uncertain;
} p2pkit_hive_exact_observation;

/* Failed close or contradictory output seals the owner. Known handles are retained and never
 * retried; status/handle contradictions are quarantined, not treated as newly owned handles.
 * Parent and child original close attempts remain independent. The original process watchdog
 * is the terminal boundary for uncertainty, not permission to report successful retirement. */
static int p2pkit_hive_exact_retire(p2pkit_hive_exact_observation *owner,
    p2pkit_hive_exact_remaining remaining, void *context) {
    if (!owner || !remaining) return 0;
    owner->sealed = 1;
    if (owner->child_owned && !owner->child_close_attempted) {
        owner->child_close_attempted = 1;
        (void)remaining(context);
        owner->child_close_status = (DWORD)RegCloseKey(owner->child);
        (void)remaining(context);
        if (owner->child_close_status == ERROR_SUCCESS) {
            owner->child = NULL; owner->child_owned = 0; ++owner->child_closes;
        } else owner->uncertain = 1;
    }
    if (owner->parent_owned && !owner->parent_close_attempted) {
        owner->parent_close_attempted = 1;
        (void)remaining(context);
        owner->parent_close_status = (DWORD)RegCloseKey(owner->parent);
        (void)remaining(context);
        if (owner->parent_close_status == ERROR_SUCCESS) {
            owner->parent = NULL; owner->parent_owned = 0;
        } else owner->uncertain = 1;
    }
    SecureZeroMemory(owner->sid, sizeof(owner->sid));
    owner->sid_length = 0;
    owner->retired = !owner->uncertain && !owner->parent && !owner->child &&
        !owner->parent_owned && !owner->child_owned;
    return owner->retired;
}

/* Zero-initialized create-only owner. Retain this actual parent across the before-load,
 * loaded-before-resume and after-exit observations. The caller must retire it on EVERY exit,
 * including open failure. This does not adopt ownership of the hive or other processes. */
static int p2pkit_hive_exact_open(const WCHAR *sid, p2pkit_hive_exact_remaining remaining,
    void *context, p2pkit_hive_exact_observation *owner) {
    if (!owner || !remaining || !sid || owner->started || owner->sealed || owner->parent || owner->child) return 0;
    owner->started = 1;
    DWORD length = 0;
    while (length < P2PKIT_HIVE_EXACT_SID_CHARS && sid[length]) ++length;
    int valid = length >= 5 && length < P2PKIT_HIVE_EXACT_SID_CHARS &&
        sid[0] == L'S' && sid[1] == L'-' && sid[2] == L'1' && sid[3] == L'-';
    if (valid) {
        for (DWORD i = 4; i < length; ++i) {
            if ((sid[i] < L'0' || sid[i] > L'9') && sid[i] != L'-') valid = 0;
            if (sid[i] == L'-' && (sid[i - 1] == L'-' || i + 1 == length)) valid = 0;
        }
    }
    if (!valid) { owner->system_error = ERROR_INVALID_DATA; owner->sealed = 1; return 0; }
    for (DWORD i = 0; i < length; ++i) owner->sid[i] = sid[i];
    owner->sid[length] = 0; owner->sid_length = length;
    WCHAR path[] = L"\\Registry\\User";
    UNICODE_STRING name = { (USHORT)(sizeof(path) - sizeof(WCHAR)), (USHORT)sizeof(path), path };
    OBJECT_ATTRIBUTES attributes = {0};
    attributes.Length = sizeof(attributes); attributes.ObjectName = &name;
    attributes.Attributes = OBJ_CASE_INSENSITIVE;
    HANDLE parent = NULL;
    (void)remaining(context);
    owner->parent_open_status = (DWORD)NtOpenKey(&parent, KEY_ENUMERATE_SUB_KEYS, &attributes);
    owner->parent = (HKEY)parent;
    (void)remaining(context);
    if (owner->parent_open_status != 0 || !parent || parent == INVALID_HANDLE_VALUE) {
        owner->sealed = 1;
        if (parent || owner->parent_open_status == 0) {
            owner->uncertain = 1; owner->system_error = ERROR_INVALID_HANDLE;
        }
        return 0;
    }
    owner->parent_owned = 1;
    return 1;
}

/* Exactly one lookup of the SID component relative to this retained real parent. Only
 * STATUS_OBJECT_NAME_NOT_FOUND with NULL output proves point-in-time exact-name absence.
 * KEY_DELETED, PATH_NOT_FOUND, access errors and ALL other statuses remain failures.
 * Successful opens temporarily pin the hive: close the acquired child before returning PRESENT.
 * No unsuccessful operation is retried; a failed child close retains its original handle. */
static int p2pkit_hive_exact_query(p2pkit_hive_exact_observation *owner,
    p2pkit_hive_exact_remaining remaining, void *context) {
    if (!owner || !remaining || !owner->started || owner->sealed || !owner->parent_owned ||
        owner->parent_close_attempted || owner->child || owner->child_owned || owner->uncertain) return P2PKIT_HIVE_EXACT_ERROR;
    owner->absence_observed = 0;
    if (owner->lookups >= P2PKIT_HIVE_EXACT_MAXIMUM_LOOKUPS) {
        owner->sealed = 1; owner->system_error = ERROR_NOT_ENOUGH_QUOTA; return P2PKIT_HIVE_EXACT_ERROR;
    }
    UNICODE_STRING name = { (USHORT)(owner->sid_length * sizeof(WCHAR)),
        (USHORT)((owner->sid_length + 1) * sizeof(WCHAR)), owner->sid };
    OBJECT_ATTRIBUTES attributes = {0};
    attributes.Length = sizeof(attributes); attributes.RootDirectory = owner->parent;
    attributes.ObjectName = &name; attributes.Attributes = OBJ_CASE_INSENSITIVE;
    HANDLE child = NULL;
    owner->child_close_attempted = 0;
    (void)remaining(context);
    ++owner->lookups;
    owner->last_lookup_status = (DWORD)NtOpenKey(&child, KEY_QUERY_VALUE, &attributes);
    owner->child = (HKEY)child;
    (void)remaining(context);
    if (owner->last_lookup_status == P2PKIT_HIVE_EXACT_NAME_NOT_FOUND && !child) {
        ++owner->absences; owner->absence_observed = 1; return P2PKIT_HIVE_EXACT_ABSENT;
    }
    if (owner->last_lookup_status != 0 || !child || child == INVALID_HANDLE_VALUE || child == owner->parent) {
        owner->sealed = 1;
        if (child || owner->last_lookup_status == 0) {
            owner->uncertain = 1; owner->system_error = ERROR_INVALID_HANDLE;
        }
        return P2PKIT_HIVE_EXACT_ERROR;
    }
    owner->child_owned = 1;
    ++owner->presences;
    owner->child_close_attempted = 1;
    (void)remaining(context);
    owner->child_close_status = (DWORD)RegCloseKey(owner->child);
    (void)remaining(context);
    if (owner->child_close_status != ERROR_SUCCESS) {
        owner->sealed = 1; owner->uncertain = 1; return P2PKIT_HIVE_EXACT_ERROR;
    }
    owner->child = NULL; owner->child_owned = 0; ++owner->child_closes;
    return P2PKIT_HIVE_EXACT_PRESENT;
}

/* Await only a state transition from successfully observed presence. Each successful child
 * handle is already closed before the cadence. Caller MUST retain the original independent
 * process watchdog during blocking opens/closes and delays; remaining() must also terminate at
 * that original expiry, never restart its budget. This returns absence only; the caller must
 * still retire the parent successfully before PASS. */
static int p2pkit_hive_exact_await_absent(p2pkit_hive_exact_observation *owner,
    p2pkit_hive_exact_remaining remaining, void *context) {
    for (;;) {
        int state = p2pkit_hive_exact_query(owner, remaining, context);
        if (state == P2PKIT_HIVE_EXACT_ABSENT) return 1;
        if (state != P2PKIT_HIVE_EXACT_PRESENT) return 0;
        DWORD cadence = remaining(context);
        if (cadence > 10u) cadence = 10u;
        Sleep(cadence);
        (void)remaining(context);
    }
}

#endif
