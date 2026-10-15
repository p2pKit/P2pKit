#ifndef P2PKIT_PROFILE_HIVE_NAMESPACE_OBSERVER_H
#define P2PKIT_PROFILE_HIVE_NAMESPACE_OBSERVER_H

/* Test-executable environment observation only. Never opens a user hive, reads values, loads
 * P2pKit code, establishes protected supervision, changes policy, or grants privileges.
 * The standalone inert control defines the API/types before including this implementation. */
#ifndef P2PKIT_HIVE_OBSERVER_INERT_CONTROL
#include <windows.h>
#include <winternl.h>
NTSYSAPI NTSTATUS NTAPI NtOpenKey(PHANDLE KeyHandle, ACCESS_MASK DesiredAccess,
    POBJECT_ATTRIBUTES ObjectAttributes);
#endif

#define P2PKIT_HIVE_NAME_CHARS 256u
#define P2PKIT_HIVE_MAXIMUM_NAMES 1024u
#define P2PKIT_HIVE_MAXIMUM_SCANS 65536u

typedef struct {
    HKEY parent;
    HANDLE event;
    int started, parent_close_attempted, event_close_attempted, notification_pending;
    int absence_observed, retired, diagnostic_wait_attempted, diagnostic_retirement_requested;
    DWORD snapshot_state;
    LSTATUS snapshot_status;
    NTSTATUS native_open_status;
    LSTATUS enumeration_status, notification_status, parent_close_status;
    DWORD system_error, wait_result;
    unsigned long scans, names, notifications;
} p2pkit_hive_namespace_observation;

/* Caller supplies the ORIGINAL end-to-end watchdog, not a fresh timeout per operation.
 * The callback must terminate the owning test process at expiry, including during cleanup. */
typedef DWORD (*p2pkit_hive_remaining)(void *context);

/* Optional fixed-phase evidence, never an acceptance/timeout hook. The enclosing diagnostic
 * bounds its output; preserve the Win32 error channel even when its output implementation uses it. */
static void p2pkit_hive_namespace_phase(DWORD phase) {
#ifdef P2PKIT_HIVE_OBSERVER_TRACE
    DWORD error = GetLastError();
    P2PKIT_HIVE_OBSERVER_TRACE(phase);
    SetLastError(error);
#else
    (void)phase;
#endif
}

static int p2pkit_hive_same_name(const WCHAR *name, DWORD length, const WCHAR *sid, DWORD sid_length) {
    if (length != sid_length) return 0;
    for (DWORD i = 0; i < length; ++i) {
        WCHAR a = name[i], b = sid[i];
        if (a >= L'a' && a <= L'z') a = (WCHAR)(a - L'a' + L'A');
        if (b >= L'a' && b <= L'z') b = (WCHAR)(b - L'a' + L'A');
        if (a != b) return 0;
    }
    return 1;
}

/* One diagnostic scan of the already-owned parent only. This scan is NOT independently
 * notification-stabilized: 1 means exact target observed, 2 means enumeration exhausted without
 * the target, 3 means an API/shape error. It cannot establish acceptance or retire a notification. */
static DWORD p2pkit_hive_namespace_snapshot(HKEY parent, const WCHAR *sid, DWORD sid_length,
    p2pkit_hive_remaining remaining, void *context, LSTATUS *status) {
    WCHAR child[P2PKIT_HIVE_NAME_CHARS] = {0};
    DWORD state = 3;
    *status = ERROR_INVALID_DATA;
    for (DWORD index = 0; index <= P2PKIT_HIVE_MAXIMUM_NAMES; ++index) {
        DWORD length = P2PKIT_HIVE_NAME_CHARS;
        (void)remaining(context);
        *status = RegEnumKeyExW(parent, index, child, &length, NULL, NULL, NULL, NULL);
        (void)remaining(context);
        if (*status == ERROR_NO_MORE_ITEMS) state = 2;
        else if (*status == ERROR_SUCCESS && index < P2PKIT_HIVE_MAXIMUM_NAMES &&
            length > 0 && length < P2PKIT_HIVE_NAME_CHARS && child[length] == 0) {
            if (p2pkit_hive_same_name(child, length, sid, sid_length)) state = 1;
            else { SecureZeroMemory(child, sizeof(child)); continue; }
        } else if (*status == ERROR_SUCCESS) *status = ERROR_INVALID_DATA;
        break;
    }
    SecureZeroMemory(child, sizeof(child));
#ifdef P2PKIT_HIVE_OBSERVER_SNAPSHOT
    DWORD error = GetLastError();
    P2PKIT_HIVE_OBSERVER_SNAPSHOT(state, (DWORD)*status);
    SetLastError(error);
#endif
    return state;
}

/* Exactly one retirement attempt per original handle. If it fails, the original handle remains
 * in this result as quarantined ownership; no caller may retry/reuse it. The enclosing test fails
 * and its original process watchdog/exit supplies the terminal boundary, not a successful receipt. */
static int p2pkit_hive_namespace_retire(p2pkit_hive_namespace_observation *owner,
    p2pkit_hive_remaining remaining, void *context) {
    int okay = 1;
    if (owner->parent && !owner->parent_close_attempted) {
        owner->parent_close_attempted = 1;
        (void)remaining(context);
        p2pkit_hive_namespace_phase(5);
        owner->parent_close_status = RegCloseKey(owner->parent);
        (void)remaining(context);
        if (owner->parent_close_status != ERROR_SUCCESS) okay = 0;
        else {
            owner->parent = NULL;
            if (owner->notification_pending) {
                /* Documented RegNotifyChangeKeyValue cancellation: closing its actual key signals
                 * the event. Keep the event owned until the pending registration has completed. */
                p2pkit_hive_namespace_phase(6);
                owner->wait_result = WaitForSingleObject(owner->event, remaining(context));
                DWORD error = owner->wait_result == WAIT_FAILED ? GetLastError() : 0;
                (void)remaining(context);
                if (owner->wait_result != WAIT_OBJECT_0) {
                    if (owner->wait_result == WAIT_FAILED) owner->system_error = error;
                    okay = 0;
                } else owner->notification_pending = 0;
            }
        }
    }
    if (owner->parent_close_attempted && owner->parent) okay = 0;
    if (owner->event && !owner->notification_pending && !owner->event_close_attempted) {
        owner->event_close_attempted = 1;
        p2pkit_hive_namespace_phase(7);
        if (!CloseHandle(owner->event)) { owner->system_error = GetLastError(); okay = 0; }
        else owner->event = NULL;
        (void)remaining(context);
    }
    if (owner->parent || owner->event || owner->notification_pending) okay = 0;
    owner->retired = okay;
    p2pkit_hive_namespace_phase(8);
    return okay;
}

/* Supply a zero-initialized create-only result. Names of unrelated HKU children are inspected
 * only in a bounded stack buffer and wiped immediately; no value data, child handles, SID/name
 * list or path evidence is returned. Success is exact-name absence in an unchanged parent scan
 * AND retirement of the actual parent/event/notification owners. */
static int p2pkit_hive_namespace_await_absent(const WCHAR *sid,
    p2pkit_hive_remaining remaining, void *context, p2pkit_hive_namespace_observation *owner) {
    if (!sid || !remaining || !owner || owner->started || owner->parent || owner->event) return 0;
    owner->started = 1;
    DWORD sid_length = 0;
    while (sid_length < 184u && sid[sid_length]) ++sid_length;
    if (sid_length < 5u || sid_length == 184u || sid[0] != L'S' || sid[1] != L'-' ||
        sid[2] != L'1' || sid[3] != L'-') return 0;
    for (DWORD i = 4; i < sid_length; ++i)
        if ((sid[i] < L'0' || sid[i] > L'9') && sid[i] != L'-') return 0;

    /* NtOpenKey returns an independently owned real local parent, unlike RegOpenKeyEx(HKU, "")
     * which may return the predefined pseudo-handle. This system root is never created/repaired. */
    WCHAR path[] = L"\\Registry\\User";
    UNICODE_STRING name = { (USHORT)(sizeof(path) - sizeof(WCHAR)), (USHORT)sizeof(path), path };
    OBJECT_ATTRIBUTES attributes = {0};
    attributes.Length = sizeof(attributes);
    attributes.ObjectName = &name;
    attributes.Attributes = OBJ_CASE_INSENSITIVE;
    HANDLE parent = NULL;
    (void)remaining(context);
    p2pkit_hive_namespace_phase(1);
    owner->native_open_status = NtOpenKey(&parent, KEY_ENUMERATE_SUB_KEYS | KEY_NOTIFY, &attributes);
    if (owner->native_open_status != 0) return 0;
    if (!parent || parent == INVALID_HANDLE_VALUE) { owner->system_error = ERROR_INVALID_HANDLE; return 0; }
    owner->parent = (HKEY)parent;
    (void)remaining(context);
    owner->event = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!owner->event) { owner->system_error = GetLastError(); goto done; }

    while (owner->scans < P2PKIT_HIVE_MAXIMUM_SCANS) {
        /* Reset/re-arm only after the prior notification was observed complete. Re-registering a
         * still-pending wait leaks registration ownership and is explicitly forbidden by Win32. */
        if (!ResetEvent(owner->event)) { owner->system_error = GetLastError(); goto done; }
        (void)remaining(context);
        p2pkit_hive_namespace_phase(2);
        owner->notification_status = RegNotifyChangeKeyValue(owner->parent, FALSE,
            REG_NOTIFY_CHANGE_NAME | REG_NOTIFY_THREAD_AGNOSTIC, owner->event, TRUE);
        (void)remaining(context);
        if (owner->notification_status != ERROR_SUCCESS) goto done;
        owner->notification_pending = 1;
        ++owner->notifications;
        ++owner->scans;
        int present = 0, exhausted = 0;
        WCHAR child[P2PKIT_HIVE_NAME_CHARS] = {0};
        for (DWORD index = 0; index <= P2PKIT_HIVE_MAXIMUM_NAMES; ++index) {
            DWORD length = P2PKIT_HIVE_NAME_CHARS;
            (void)remaining(context);
            owner->enumeration_status = RegEnumKeyExW(owner->parent, index, child, &length,
                NULL, NULL, NULL, NULL);
            (void)remaining(context);
            if (owner->enumeration_status == ERROR_NO_MORE_ITEMS) exhausted = 1;
            else if (owner->enumeration_status == ERROR_SUCCESS && index < P2PKIT_HIVE_MAXIMUM_NAMES &&
                length > 0 && length < P2PKIT_HIVE_NAME_CHARS && child[length] == 0) {
                ++owner->names;
                present = p2pkit_hive_same_name(child, length, sid, sid_length);
            } else {
                if (owner->enumeration_status == ERROR_SUCCESS) owner->system_error = ERROR_INVALID_DATA;
                SecureZeroMemory(child, sizeof(child));
                goto done;
            }
            SecureZeroMemory(child, sizeof(child));
            if (present || exhausted) break;
        }
        /* A successful notification is namespace mutation, not an API failure to retry. A changed
         * scan never proves absence: consume that completed notification and rescan from index 0. */
        p2pkit_hive_namespace_phase(present ? 3u : 4u);
        DWORD wait_budget = present ? remaining(context) : 0;
        int diagnostic_split = present && !owner->diagnostic_wait_attempted;
        if (diagnostic_split) {
            owner->diagnostic_wait_attempted = 1;
            if (wait_budget > 1000u) wait_budget = 1000u;
        }
        owner->wait_result = WaitForSingleObject(owner->event, wait_budget);
        DWORD error = owner->wait_result == WAIT_FAILED ? GetLastError() : 0;
        (void)remaining(context);
        if (diagnostic_split && owner->wait_result == WAIT_TIMEOUT) {
            owner->snapshot_state = p2pkit_hive_namespace_snapshot(owner->parent, sid, sid_length,
                remaining, context, &owner->snapshot_status);
            if (owner->snapshot_state == 3) {
                owner->system_error = (DWORD)owner->snapshot_status;
                goto done; /* Diagnostic API failures remain terminal; never retry or demote them. */
            }
#ifdef P2PKIT_HIVE_OBSERVER_DIAGNOSTIC_RETIRE_ON_MISS
            /* Explicit profile-experiment diagnosis only: retire the original registration after
             * a diagnostic miss. Neither this miss nor cancellation may establish absence. */
            if (owner->snapshot_state == 2 && P2PKIT_HIVE_OBSERVER_DIAGNOSTIC_RETIRE_ON_MISS) {
                owner->diagnostic_retirement_requested = 1;
                goto done;
            }
#endif
            /* Even a diagnostic state2 cannot pass. Await the SAME pending registration, with
             * the ORIGINAL remaining budget; no reset/rearm, additional owner, or new deadline. */
            owner->wait_result = WaitForSingleObject(owner->event, remaining(context));
            error = owner->wait_result == WAIT_FAILED ? GetLastError() : 0;
            (void)remaining(context);
        }
        if (owner->wait_result == WAIT_OBJECT_0) { owner->notification_pending = 0; continue; }
        if (!present && exhausted && owner->wait_result == WAIT_TIMEOUT) {
            owner->absence_observed = 1;
            break;
        }
        if (owner->wait_result == WAIT_FAILED) owner->system_error = error;
        goto done;
    }
done:
    if (!p2pkit_hive_namespace_retire(owner, remaining, context)) return 0;
    return owner->absence_observed;
}

#endif
