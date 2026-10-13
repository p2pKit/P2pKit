/* Deterministic API-interposition controls only: never opens a registry or loads native code.
 * Native Windows compilation/runtime remains a separate environment qualification. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#define P2PKIT_HIVE_OBSERVER_INERT_CONTROL
typedef uint32_t DWORD;
typedef uint16_t USHORT;
typedef int32_t NTSTATUS;
typedef int32_t LSTATUS;
typedef uint32_t ACCESS_MASK;
typedef wchar_t WCHAR;
typedef void *HANDLE;
typedef HANDLE HKEY;
typedef int BOOL;
typedef struct { USHORT Length, MaximumLength; WCHAR *Buffer; } UNICODE_STRING;
typedef struct {
    DWORD Length; HANDLE RootDirectory; UNICODE_STRING *ObjectName; DWORD Attributes;
    void *SecurityDescriptor, *SecurityQualityOfService;
} OBJECT_ATTRIBUTES;
#define TRUE 1
#define FALSE 0
#define INVALID_HANDLE_VALUE ((HANDLE)(intptr_t)-1)
#define ERROR_SUCCESS 0
#define ERROR_INVALID_HANDLE 6
#define ERROR_INVALID_DATA 13
#define ERROR_ACCESS_DENIED 5
#define ERROR_NO_MORE_ITEMS 259
#define ERROR_MORE_DATA 234
#define ERROR_KEY_DELETED 1018
#define WAIT_OBJECT_0 0u
#define WAIT_TIMEOUT 258u
#define WAIT_FAILED UINT32_MAX
#define KEY_ENUMERATE_SUB_KEYS 8u
#define KEY_NOTIFY 16u
#define REG_NOTIFY_CHANGE_NAME 1u
#define REG_NOTIFY_THREAD_AGNOSTIC 0x10000000u
#define OBJ_CASE_INSENSITIVE 64u

static unsigned char parent_identity, event_identity;
#define PARENT ((HANDLE)&parent_identity)
#define EVENT ((HANDLE)&event_identity)
static const WCHAR target[] = L"S-1-5-21-111-222-333-444";
static struct {
    int present, mutate_during_scan, fail_open, fail_event, fail_reset, fail_notify;
    int enum_error, malformed_name, too_many, fail_parent_close, fail_event_close;
    int fail_scan_wait, fail_cancellation_wait, cancel_not_signaled;
    int pending, event_signaled, parent_live, event_live;
    int arms, enum_calls, parent_closes, event_closes, waits, original_deadline_calls;
    DWORD last_error;
} model;

static DWORD GetLastError(void) { return model.last_error; }
static void SecureZeroMemory(void *bytes, size_t length) { memset(bytes, 0, length); }
static NTSTATUS NtOpenKey(HANDLE *key, ACCESS_MASK access, OBJECT_ATTRIBUTES *attributes) {
    assert(access == (KEY_ENUMERATE_SUB_KEYS | KEY_NOTIFY));
    assert(attributes->Length == sizeof(*attributes));
    assert(attributes->RootDirectory == NULL && attributes->Attributes == OBJ_CASE_INSENSITIVE);
    assert(attributes->SecurityDescriptor == NULL && attributes->SecurityQualityOfService == NULL);
    assert(wcscmp(attributes->ObjectName->Buffer, L"\\Registry\\User") == 0);
    assert(attributes->ObjectName->Length == 14 * sizeof(WCHAR));
    if (model.fail_open) return (NTSTATUS)0xc0000022u;
    *key = PARENT; model.parent_live = 1; return 0;
}
static HANDLE CreateEventW(void *attributes, BOOL manual, BOOL initial, const WCHAR *name) {
    assert(attributes == NULL && manual && !initial && name == NULL);
    if (model.fail_event) { model.last_error = 8; return NULL; }
    model.event_live = 1; return EVENT;
}
static BOOL ResetEvent(HANDLE event) {
    assert(event == EVENT && model.event_live && !model.pending);
    if (model.fail_reset) { model.last_error = ERROR_INVALID_HANDLE; return FALSE; }
    model.event_signaled = 0; return TRUE;
}
static LSTATUS RegNotifyChangeKeyValue(HKEY parent, BOOL subtree, DWORD flags, HANDLE event, BOOL asynchronous) {
    assert(parent == PARENT && model.parent_live && event == EVENT && model.event_live);
    assert(!subtree && asynchronous && flags == (REG_NOTIFY_CHANGE_NAME | REG_NOTIFY_THREAD_AGNOSTIC));
    assert(!model.pending);
    if (model.fail_notify) return ERROR_ACCESS_DENIED;
    model.pending = 1; ++model.arms; return ERROR_SUCCESS;
}
static LSTATUS RegEnumKeyExW(HKEY parent, DWORD index, WCHAR *name, DWORD *length,
    DWORD *reserved, WCHAR *klass, DWORD *class_length, void *last_write) {
    assert(parent == PARENT && model.parent_live && model.pending);
    assert(*length == 256 && !reserved && !klass && !class_length && !last_write);
    /* All bytes from the preceding unrelated key must have been erased before reuse. */
    for (DWORD i = 0; i < *length; ++i) assert(name[i] == 0);
    ++model.enum_calls;
    if (model.enum_error) return (LSTATUS)model.enum_error;
    if (model.malformed_name) { *length = 256; return ERROR_SUCCESS; }
    if (model.too_many) { wcscpy(name, L"unrelated"); *length = 9; return ERROR_SUCCESS; }
    if (model.mutate_during_scan && model.arms == 1 && index == 0) {
        /* A target moves during enumeration. Returning no-more-items must NOT become absence. */
        model.present = 1; model.event_signaled = 1; model.pending = 0;
        return ERROR_NO_MORE_ITEMS;
    }
    if (index == 0) { wcscpy(name, L".DEFAULT"); *length = 8; return ERROR_SUCCESS; }
    if (index == 1 && model.present) {
        wcscpy(name, target); *length = (DWORD)wcslen(target); return ERROR_SUCCESS;
    }
    return ERROR_NO_MORE_ITEMS;
}
static DWORD WaitForSingleObject(HANDLE event, DWORD timeout) {
    assert(event == EVENT && model.event_live); ++model.waits;
    if (model.fail_scan_wait && model.parent_live) { model.last_error = 6; return WAIT_FAILED; }
    if (model.fail_cancellation_wait && !model.parent_live) { model.last_error = 6; return WAIT_FAILED; }
    if (model.event_signaled) return WAIT_OBJECT_0;
    if (!model.parent_live && model.cancel_not_signaled) return WAIT_TIMEOUT;
    if (timeout && model.present) {
        assert(model.pending); model.present = 0; model.pending = 0; model.event_signaled = 1;
        return WAIT_OBJECT_0;
    }
    return WAIT_TIMEOUT;
}
static LSTATUS RegCloseKey(HKEY parent) {
    assert(parent == PARENT && model.parent_live); ++model.parent_closes;
    if (model.fail_parent_close) return ERROR_ACCESS_DENIED;
    model.parent_live = 0;
    if (model.pending && !model.cancel_not_signaled) {
        model.pending = 0; model.event_signaled = 1;
    }
    return ERROR_SUCCESS;
}
static BOOL CloseHandle(HANDLE event) {
    assert(event == EVENT && model.event_live && !model.pending); ++model.event_closes;
    if (model.fail_event_close) { model.last_error = 6; return FALSE; }
    model.event_live = 0; return TRUE;
}
static DWORD original_remaining(void *context) {
    assert(context == &model); ++model.original_deadline_calls;
    /* Deliberately clobber LastError: the observer must capture actual API errors before this callback. */
    model.last_error = 999;
    return 60000;
}

#include "profile_hive_namespace_observer.h"

static int execute(p2pkit_hive_namespace_observation *result) {
    return p2pkit_hive_namespace_await_absent(target, original_remaining, &model, result);
}
static void fresh(void) { memset(&model, 0, sizeof(model)); }
static void assert_retired(const p2pkit_hive_namespace_observation *result) {
    assert(result->retired && !result->parent && !result->event && !result->notification_pending);
    assert(!model.parent_live && !model.event_live && !model.pending);
}
int main(void) {
    unsigned passed = 0;
    {
        fresh(); p2pkit_hive_namespace_observation result = {0};
        assert(execute(&result)); assert_retired(&result);
        assert(result.absence_observed && model.arms == 1 && model.enum_calls == 2);
        assert(model.parent_closes == 1 && model.event_closes == 1); ++passed;
    }
    {
        fresh(); model.present = 1; p2pkit_hive_namespace_observation result = {0};
        assert(execute(&result)); assert_retired(&result);
        assert(model.arms == 2 && result.scans == 2 && model.enum_calls == 4); ++passed;
    }
    {
        fresh(); model.mutate_during_scan = 1; p2pkit_hive_namespace_observation result = {0};
        assert(execute(&result)); assert_retired(&result);
        assert(model.arms == 3 && result.scans == 3 && model.enum_calls == 5); ++passed;
    }
    for (int code_index = 0; code_index < 3; ++code_index) {
        const int codes[] = { ERROR_KEY_DELETED, ERROR_ACCESS_DENIED, ERROR_MORE_DATA };
        fresh(); model.enum_error = codes[code_index]; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert_retired(&result);
        assert(!result.absence_observed && result.enumeration_status == codes[code_index]);
        assert(model.enum_calls == 1 && model.arms == 1); ++passed;
    }
    {
        fresh(); model.malformed_name = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert_retired(&result);
        assert(!result.absence_observed && result.system_error == ERROR_INVALID_DATA); ++passed;
    }
    {
        fresh(); model.too_many = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert_retired(&result);
        assert(model.enum_calls == 1025 && result.names == 1024 && !result.absence_observed); ++passed;
    }
    {
        fresh(); model.fail_parent_close = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert(result.absence_observed && !result.retired);
        assert(result.parent == PARENT && result.event == EVENT && result.notification_pending);
        assert(model.parent_closes == 1 && model.event_closes == 0);
        assert(!p2pkit_hive_namespace_retire(&result, original_remaining, &model));
        assert(model.parent_closes == 1 && model.event_closes == 0); ++passed;
    }
    {
        fresh(); model.fail_cancellation_wait = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert(result.absence_observed && !result.retired);
        assert(!result.parent && result.event == EVENT && result.notification_pending);
        assert(result.system_error == 6 && model.parent_closes == 1 && model.event_closes == 0); ++passed;
    }
    {
        fresh(); model.cancel_not_signaled = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert(result.absence_observed && !result.retired);
        assert(!result.parent && result.event == EVENT && result.notification_pending);
        assert(model.event_closes == 0); ++passed;
    }
    {
        fresh(); model.fail_event_close = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert(result.absence_observed && !result.retired);
        assert(!result.parent && result.event == EVENT && !result.notification_pending);
        assert(result.system_error == 6 && model.event_closes == 1);
        assert(!p2pkit_hive_namespace_retire(&result, original_remaining, &model));
        assert(model.event_closes == 1); ++passed;
    }
    {
        fresh(); model.fail_scan_wait = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert_retired(&result);
        assert(!result.absence_observed && result.system_error == 6 && model.enum_calls == 2); ++passed;
    }
    {
        fresh(); model.fail_open = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert(!model.parent_live && !model.event_live);
        assert(model.arms == 0 && model.parent_closes == 0 && model.event_closes == 0); ++passed;
    }
    {
        fresh(); model.fail_event = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert_retired(&result);
        assert(model.arms == 0 && model.parent_closes == 1 && model.event_closes == 0); ++passed;
    }
    {
        fresh(); model.fail_reset = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert_retired(&result);
        assert(model.arms == 0 && model.parent_closes == 1 && model.event_closes == 1); ++passed;
    }
    {
        fresh(); model.fail_notify = 1; p2pkit_hive_namespace_observation result = {0};
        assert(!execute(&result)); assert_retired(&result);
        assert(result.notification_status == ERROR_ACCESS_DENIED && model.arms == 0 && model.enum_calls == 0); ++passed;
    }
    {
        fresh(); p2pkit_hive_namespace_observation result = {0};
        assert(execute(&result)); int calls = model.original_deadline_calls;
        assert(!execute(&result)); assert(model.original_deadline_calls == calls); ++passed;
    }
    printf("PASS %u inert parent-namespace/notification ownership controls; NOT Windows runtime evidence\n", passed);
    return 0;
}
