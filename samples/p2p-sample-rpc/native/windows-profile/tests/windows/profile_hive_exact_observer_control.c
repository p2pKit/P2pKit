/* Deterministic exact-lookup interposition only. No real registry, profile, Windows library,
 * process or security policy is accessed. Native compilation/runtime is separate evidence. */
#include <assert.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#define P2PKIT_HIVE_EXACT_INERT_CONTROL
typedef uint32_t DWORD;
typedef uint16_t USHORT;
typedef int32_t NTSTATUS;
typedef int32_t LSTATUS;
typedef uint32_t ACCESS_MASK;
typedef wchar_t WCHAR;
typedef void *HANDLE;
typedef HANDLE HKEY;
typedef struct { USHORT Length, MaximumLength; WCHAR *Buffer; } UNICODE_STRING;
typedef struct {
    DWORD Length; HANDLE RootDirectory; UNICODE_STRING *ObjectName; DWORD Attributes;
    void *SecurityDescriptor, *SecurityQualityOfService;
} OBJECT_ATTRIBUTES;
#define INVALID_HANDLE_VALUE ((HANDLE)(intptr_t)-1)
#define ERROR_SUCCESS 0u
#define ERROR_ACCESS_DENIED 5u
#define ERROR_INVALID_HANDLE 6u
#define ERROR_INVALID_DATA 13u
#define ERROR_NOT_ENOUGH_QUOTA 1816u
#define KEY_ENUMERATE_SUB_KEYS 8u
#define KEY_QUERY_VALUE 1u
#define OBJ_CASE_INSENSITIVE 64u
#define NAME_NOT_FOUND 0xc0000034u
#define KEY_DELETED 0xc000017cu
#define ACCESS_DENIED 0xc0000022u
#define PATH_NOT_FOUND 0xc000003au

enum { NO_HANDLE, VALID_HANDLE, INVALID_HANDLE, PARENT_ALIAS };
static unsigned char parent_identity, child_identity;
#define PARENT ((HANDLE)&parent_identity)
#define CHILD ((HANDLE)&child_identity)
static const WCHAR target[] = L"S-1-5-21-111-222-333-444";
static jmp_buf deadline_jump;
static struct {
    DWORD parent_status, statuses[8], elapsed, query_ms, close_ms;
    int parent_output, outputs[8], actions, action;
    int parent_live, child_live, parent_calls, query_calls, parent_closes, child_closes;
    int fail_parent_close, fail_child_close, sleeps, remaining_calls, expect_expiry, expirations;
    DWORD last_sleep;
} model;

static void SecureZeroMemory(void *bytes, size_t length) { memset(bytes, 0, length); }
static HANDLE output_handle(int kind, int parent) {
    if (kind == NO_HANDLE) return NULL;
    if (kind == INVALID_HANDLE) return INVALID_HANDLE_VALUE;
    if (kind == PARENT_ALIAS || parent) return PARENT;
    return CHILD;
}
static NTSTATUS NtOpenKey(HANDLE *key, ACCESS_MASK access, OBJECT_ATTRIBUTES *attributes) {
    assert(*key == NULL && attributes->Length == sizeof(*attributes));
    assert(attributes->Attributes == OBJ_CASE_INSENSITIVE);
    assert(!attributes->SecurityDescriptor && !attributes->SecurityQualityOfService);
    if (!attributes->RootDirectory) {
        assert(access == KEY_ENUMERATE_SUB_KEYS && !model.parent_calls);
        assert(wcscmp(attributes->ObjectName->Buffer, L"\\Registry\\User") == 0);
        assert(attributes->ObjectName->Length == 14 * sizeof(WCHAR));
        assert(attributes->ObjectName->MaximumLength == 15 * sizeof(WCHAR));
        ++model.parent_calls;
        *key = output_handle(model.parent_output, 1);
        if (*key == PARENT) model.parent_live = 1;
        return (NTSTATUS)model.parent_status;
    }
    assert(attributes->RootDirectory == PARENT && model.parent_live && !model.child_live);
    assert(access == KEY_QUERY_VALUE && model.action < model.actions);
    assert(wcscmp(attributes->ObjectName->Buffer, target) == 0);
    assert(attributes->ObjectName->Length == wcslen(target) * sizeof(WCHAR));
    assert(attributes->ObjectName->MaximumLength == (wcslen(target) + 1) * sizeof(WCHAR));
    int index = model.action++; ++model.query_calls; model.elapsed += model.query_ms;
    *key = output_handle(model.outputs[index], 0);
    if (*key == CHILD) model.child_live = 1;
    return (NTSTATUS)model.statuses[index];
}
static LSTATUS RegCloseKey(HKEY key) {
    model.elapsed += model.close_ms;
    if (key == CHILD) {
        assert(model.child_live); ++model.child_closes;
        if (model.fail_child_close) return ERROR_ACCESS_DENIED;
        model.child_live = 0; return ERROR_SUCCESS;
    }
    assert(key == PARENT && model.parent_live); ++model.parent_closes;
    if (model.fail_parent_close) return ERROR_ACCESS_DENIED;
    model.parent_live = 0; return ERROR_SUCCESS;
}
static DWORD original_remaining(void *context) {
    assert(context == &model); ++model.remaining_calls;
    if (model.elapsed >= 60000u) {
        assert(model.expect_expiry); ++model.expirations; longjmp(deadline_jump, 1);
    }
    return 60000u - model.elapsed;
}
static void Sleep(DWORD milliseconds) {
    assert(!model.child_live && model.parent_live);
    assert(milliseconds > 0 && milliseconds <= 10u && milliseconds <= 60000u - model.elapsed);
    ++model.sleeps; model.last_sleep = milliseconds; model.elapsed += milliseconds;
}

#include "profile_hive_exact_observer.h"

static void fresh(void) { memset(&model, 0, sizeof(model)); model.parent_output = VALID_HANDLE; }
static void action(DWORD status, int handle) {
    assert(model.actions < 8);
    model.statuses[model.actions] = status; model.outputs[model.actions++] = handle;
}
static int open_owner(p2pkit_hive_exact_observation *owner) {
    return p2pkit_hive_exact_open(target, original_remaining, &model, owner);
}
static int query(p2pkit_hive_exact_observation *owner) {
    return p2pkit_hive_exact_query(owner, original_remaining, &model);
}
static int retire(p2pkit_hive_exact_observation *owner) {
    return p2pkit_hive_exact_retire(owner, original_remaining, &model);
}
static void retired(const p2pkit_hive_exact_observation *owner) {
    assert(owner->retired && owner->sealed && !owner->parent && !owner->child);
    assert(!owner->parent_owned && !owner->child_owned && !model.parent_live && !model.child_live);
    assert(owner->sid_length == 0);
    for (DWORD i = 0; i < P2PKIT_HIVE_EXACT_SID_CHARS; ++i) assert(owner->sid[i] == 0);
}
static p2pkit_hive_exact_observation deadline_owner;

int main(void) {
    unsigned passed = 0;
    {
        fresh(); p2pkit_hive_exact_observation owner = {0};
        action(NAME_NOT_FOUND, NO_HANDLE); action(0, VALID_HANDLE);
        action(0, VALID_HANDLE); action(NAME_NOT_FOUND, NO_HANDLE);
        assert(open_owner(&owner));
        assert(query(&owner) == P2PKIT_HIVE_EXACT_ABSENT && owner.absence_observed);
        assert(query(&owner) == P2PKIT_HIVE_EXACT_PRESENT && !owner.absence_observed && !model.child_live);
        assert(p2pkit_hive_exact_await_absent(&owner, original_remaining, &model));
        assert(owner.last_lookup_status == NAME_NOT_FOUND && owner.lookups == 4);
        assert(owner.presences == 2 && owner.child_closes == 2 && owner.absences == 2 && model.sleeps == 1);
        assert(retire(&owner)); retired(&owner);
        assert(model.parent_calls == 1 && model.parent_closes == 1 && model.child_closes == 2); ++passed;
    }
    {
        /* Unexpected before-load presence is observable without adoption or value access;
         * the enclosing recipe must reject it, retaining none of this lookup's own handles. */
        fresh(); p2pkit_hive_exact_observation owner = {0}; action(0, VALID_HANDLE);
        assert(open_owner(&owner) && query(&owner) == P2PKIT_HIVE_EXACT_PRESENT);
        assert(owner.presences == 1 && owner.child_closes == 1 && !owner.absence_observed);
        assert(retire(&owner)); retired(&owner); ++passed;
    }
    {
        fresh(); p2pkit_hive_exact_observation owner = {0};
        assert(open_owner(&owner)); assert(!open_owner(&owner));
        assert(retire(&owner)); retired(&owner); assert(!open_owner(&owner));
        assert(query(&owner) == P2PKIT_HIVE_EXACT_ERROR && model.parent_calls == 1 && !model.query_calls);
        assert(retire(&owner) && model.parent_closes == 1); ++passed;
    }
    {
        const WCHAR *bad[] = { L"", L"S-1-", L"S-1--5", L"S-1-5\\nested", L"S-1-5/path", L"A-1-5", L"S-1-5\n" };
        for (unsigned i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i) {
            fresh(); p2pkit_hive_exact_observation owner = {0};
            assert(!p2pkit_hive_exact_open(bad[i], original_remaining, &model, &owner));
            assert(owner.sealed && owner.system_error == ERROR_INVALID_DATA && !model.parent_calls);
            assert(retire(&owner)); retired(&owner); ++passed;
        }
    }
    {
        fresh(); p2pkit_hive_exact_observation owner = {0}; WCHAR long_name[185];
        for (unsigned i = 0; i < 184; ++i) long_name[i] = L'1';
        long_name[184] = 0;
        assert(!p2pkit_hive_exact_open(long_name, original_remaining, &model, &owner));
        assert(!model.parent_calls && retire(&owner)); retired(&owner); ++passed;
    }
    {
        fresh(); p2pkit_hive_exact_observation owner = {0};
        model.parent_status = ACCESS_DENIED; model.parent_output = NO_HANDLE;
        assert(!open_owner(&owner) && owner.sealed && owner.parent_open_status == ACCESS_DENIED);
        assert(!open_owner(&owner) && query(&owner) == P2PKIT_HIVE_EXACT_ERROR);
        assert(retire(&owner)); retired(&owner);
        assert(model.parent_calls == 1 && !model.query_calls && !model.parent_closes); ++passed;
    }
    {
        const DWORD statuses[] = { 0, 0, ACCESS_DENIED };
        const int outputs[] = { NO_HANDLE, INVALID_HANDLE, VALID_HANDLE };
        for (unsigned i = 0; i < 3; ++i) {
            fresh(); p2pkit_hive_exact_observation owner = {0};
            model.parent_status = statuses[i]; model.parent_output = outputs[i];
            assert(!open_owner(&owner) && owner.sealed && owner.uncertain);
            HANDLE original = owner.parent;
            assert(!retire(&owner) && owner.parent == original && !model.parent_closes);
            assert(!retire(&owner) && !open_owner(&owner) && model.parent_calls == 1); ++passed;
        }
    }
    {
        const DWORD statuses[] = { KEY_DELETED, ACCESS_DENIED, PATH_NOT_FOUND, 1u };
        for (unsigned i = 0; i < sizeof(statuses) / sizeof(statuses[0]); ++i) {
            fresh(); p2pkit_hive_exact_observation owner = {0}; action(statuses[i], NO_HANDLE);
            assert(open_owner(&owner) && query(&owner) == P2PKIT_HIVE_EXACT_ERROR);
            assert(owner.last_lookup_status == statuses[i] && owner.sealed && !owner.absence_observed);
            assert(query(&owner) == P2PKIT_HIVE_EXACT_ERROR && model.query_calls == 1);
            assert(retire(&owner)); retired(&owner);
            assert(model.parent_closes == 1 && !model.child_closes); ++passed;
        }
    }
    {
        const DWORD statuses[] = { NAME_NOT_FOUND, 0, 0, 0, ACCESS_DENIED };
        const int outputs[] = { VALID_HANDLE, NO_HANDLE, INVALID_HANDLE, PARENT_ALIAS, VALID_HANDLE };
        for (unsigned i = 0; i < 5; ++i) {
            fresh(); p2pkit_hive_exact_observation owner = {0}; action(statuses[i], outputs[i]);
            assert(open_owner(&owner) && query(&owner) == P2PKIT_HIVE_EXACT_ERROR);
            HANDLE original = owner.child;
            assert(owner.uncertain && owner.sealed && !owner.absence_observed && !owner.child_owned);
            assert(!retire(&owner) && owner.child == original && !model.child_closes && model.parent_closes == 1);
            assert(query(&owner) == P2PKIT_HIVE_EXACT_ERROR && model.query_calls == 1);
            assert(!retire(&owner) && !model.child_closes && model.parent_closes == 1); ++passed;
        }
    }
    {
        fresh(); p2pkit_hive_exact_observation owner = {0}; action(0, VALID_HANDLE); model.fail_child_close = 1;
        assert(open_owner(&owner) && query(&owner) == P2PKIT_HIVE_EXACT_ERROR);
        assert(owner.child == CHILD && owner.child_owned && owner.child_close_attempted && owner.uncertain);
        assert(owner.child_close_status == ERROR_ACCESS_DENIED && owner.presences == 1 && owner.child_closes == 0);
        assert(query(&owner) == P2PKIT_HIVE_EXACT_ERROR && !p2pkit_hive_exact_await_absent(&owner, original_remaining, &model));
        assert(!retire(&owner) && !retire(&owner));
        assert(model.child_closes == 1 && model.parent_closes == 1 && model.query_calls == 1 && !model.sleeps);
        assert(owner.child == CHILD && !owner.absence_observed); ++passed;
    }
    {
        fresh(); p2pkit_hive_exact_observation owner = {0}; action(NAME_NOT_FOUND, NO_HANDLE); model.fail_parent_close = 1;
        assert(open_owner(&owner) && query(&owner) == P2PKIT_HIVE_EXACT_ABSENT);
        assert(!retire(&owner) && owner.absence_observed && !owner.retired && owner.parent == PARENT);
        assert(owner.parent_close_status == ERROR_ACCESS_DENIED && owner.parent_close_attempted);
        assert(!retire(&owner) && query(&owner) == P2PKIT_HIVE_EXACT_ERROR);
        assert(model.parent_closes == 1 && model.query_calls == 1); ++passed;
    }
    {
        fresh(); p2pkit_hive_exact_observation owner = {0}; assert(open_owner(&owner));
        owner.lookups = P2PKIT_HIVE_EXACT_MAXIMUM_LOOKUPS;
        assert(query(&owner) == P2PKIT_HIVE_EXACT_ERROR && owner.system_error == ERROR_NOT_ENOUGH_QUOTA);
        assert(!model.query_calls && owner.sealed && retire(&owner)); retired(&owner); ++passed;
    }
    {
        fresh(); memset(&deadline_owner, 0, sizeof(deadline_owner)); action(0, VALID_HANDLE);
        assert(open_owner(&deadline_owner)); model.elapsed = 59995u; model.expect_expiry = 1;
        if (setjmp(deadline_jump) == 0) {
            (void)p2pkit_hive_exact_await_absent(&deadline_owner, original_remaining, &model);
            assert(0); /* Original deadline must terminate, never restart or emit successful absence. */
        }
        assert(model.expirations == 1 && model.elapsed == 60000u && model.last_sleep == 5u);
        assert(model.query_calls == 1 && model.child_closes == 1 && !model.child_live);
        assert(!deadline_owner.absence_observed && !deadline_owner.retired && deadline_owner.parent == PARENT); ++passed;
    }
    {
        fresh(); p2pkit_hive_exact_observation owner = {0}; WCHAR sid[184] = {0};
        memcpy(sid, target, sizeof(target)); action(NAME_NOT_FOUND, NO_HANDLE);
        assert(p2pkit_hive_exact_open(sid, original_remaining, &model, &owner)); sid[0] = L'X';
        assert(query(&owner) == P2PKIT_HIVE_EXACT_ABSENT && retire(&owner)); retired(&owner); ++passed;
    }
    {
        fresh(); p2pkit_hive_exact_observation owner = {0};
        action(0, VALID_HANDLE); action(NAME_NOT_FOUND, NO_HANDLE); model.query_ms = 7; model.close_ms = 3;
        assert(open_owner(&owner) && p2pkit_hive_exact_await_absent(&owner, original_remaining, &model));
        assert(model.elapsed == 27u && model.sleeps == 1 && model.last_sleep == 10u);
        assert(retire(&owner) && model.elapsed == 30u); retired(&owner); ++passed;
    }
    {
        fresh(); p2pkit_hive_exact_observation owner = {0};
        assert(query(&owner) == P2PKIT_HIVE_EXACT_ERROR && !model.query_calls && !model.parent_calls);
        assert(!p2pkit_hive_exact_open(NULL, original_remaining, &model, &owner));
        assert(!p2pkit_hive_exact_open(target, NULL, &model, &owner));
        assert(!p2pkit_hive_exact_open(target, original_remaining, &model, NULL));
        assert(!model.parent_calls); ++passed;
    }
    printf("PASS %u inert exact-SID lookup/ownership controls; NOT Windows runtime evidence\n", passed);
    return 0;
}
