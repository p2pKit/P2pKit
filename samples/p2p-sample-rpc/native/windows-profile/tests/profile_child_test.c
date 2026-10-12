#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Real shared publication/identity policy; no Windows create, DACL or namespace emulation. */
typedef struct {
    pwp_owner *owner;
    unsigned verifies, closes;
    int reject, fail_close, poison, exhaust;
    char order[8]; size_t ordered;
} fake;
static void record(fake *f, char action) { assert(f->ordered < sizeof(f->order)); f->order[f->ordered++] = action; }
static int verify(void *context) {
    fake *f = context; ++f->verifies; record(f, 'V');
    if (f->poison) f->owner->poisoned = 1;
    if (f->exhaust) for (unsigned i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i) {
        uint64_t next = 0;
        assert(pwp_reserve(f->owner, &next) == PWP_OK && pwp_attach(f->owner, next, 7) == PWP_OK);
        assert(pwp_publish(f->owner, next) == PWP_OK);
    }
    return !f->reject;
}
static int close_handle(uintptr_t resource, void *context) {
    fake *f = context; assert(resource == 7); ++f->closes; record(f, 'C'); return !f->fail_close;
}
static uint64_t allocated(pwp_owner *owner) {
    uint64_t token = 0; pwp_owner_init(owner);
    assert(pwp_reserve(owner, &token) == PWP_OK && pwp_attach(owner, token, 7) == PWP_OK); return token;
}
static void success_retains_exact_lease(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    assert(pwp_child_finish(&owner, token, verify, close_handle, &f) == PWP_OK);
    assert(f.ordered == 1 && f.order[0] == 'V' && f.closes == 0 && pwp_public_count(&owner) == 1);
    assert(pwp_lookup(&owner, token)->state == 2 && pwp_lookup(&owner, token)->resource == 7);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK && f.closes == 1);
}
static void directory_tuples_are_exact(void) {
    const uint64_t parent[6] = {1, UINT64_MAX, UINT64_C(0x8000000000000000), 0, 0x1ff, 1};
    const uint64_t child[6] = {1, UINT64_MAX, 0, UINT64_MAX, 0x1ff, 1};
    assert(pwp_expected_child_directory(parent, child, 6));
    assert(!pwp_expected_child_directory(NULL, child, 6) && !pwp_expected_child_directory(parent, NULL, 6));
    assert(!pwp_expected_child_directory(parent, child, 5) && !pwp_expected_child_directory(parent, child, 7));
    assert(!pwp_expected_child_directory(parent, parent, 6));
    for (int side = 0; side < 2; ++side) for (unsigned mode = 0; mode < 8; ++mode) {
        uint64_t changed[6]; memcpy(changed, side ? child : parent, sizeof(changed));
        if (mode == 0) changed[0] = 2;
        if (mode == 1) changed[1] = 0;
        if (mode == 2) changed[1] = 3;
        if (mode == 3) changed[2] = changed[3] = 0;
        if (mode == 4) changed[4] = 0x2ff; /* A file is not a directory. */
        if (mode == 5) changed[4] = 0;
        if (mode == 6) changed[5] = 2;
        if (mode == 7) changed[5] = 0;
        assert(!pwp_expected_child_directory(side ? parent : changed, side ? changed : child, 6));
    }
}
static void invalid_arguments_do_not_transfer_ownership(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    assert(pwp_child_finish(NULL, token, verify, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_child_finish(&owner, 0, verify, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_child_finish(&owner, token+1, verify, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_child_finish(&owner, token, NULL, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_child_finish(&owner, token, verify, NULL, &f) == PWP_ARGUMENT);
    assert(f.ordered == 0 && pwp_lookup(&owner, token)->state == 2);
    uint64_t reserved = 0; assert(pwp_reserve(&owner, &reserved) == PWP_OK);
    assert(pwp_child_finish(&owner, reserved, verify, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK && f.closes == 1);
    assert(pwp_retire(&owner, reserved, close_handle, &f) == PWP_OK && f.closes == 1);
}
static void rejection_closes_once_without_publication(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner; f.reject = 1;
    assert(pwp_child_finish(&owner, token, verify, close_handle, &f) == PWP_POLICY);
    assert(f.ordered == 2 && memcmp(f.order, "VC", 2) == 0 && pwp_public_count(&owner) == 0);
    assert(pwp_lookup(&owner, token)->state == 3 && !pwp_lookup(&owner, token)->published);
    assert(pwp_retire_all(&owner, close_handle, &f) == PWP_OK && f.closes == 1);
}
static void failed_close_retains_quarantine_without_retry(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    f.reject = 1; f.fail_close = 1;
    assert(pwp_child_finish(&owner, token, verify, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
    assert(owner.poisoned && pwp_lookup(&owner, token)->state == 4 && pwp_public_count(&owner) == 0);
    assert(pwp_lookup(&owner, token)->resource == 7 && !pwp_lookup(&owner, token)->published);
    assert(pwp_retire_all(&owner, close_handle, &f) == PWP_CLEANUP_UNKNOWN && f.closes == 1);
    assert(pwp_child_finish(&owner, token, verify, close_handle, &f) == PWP_ARGUMENT && f.closes == 1);
    uint64_t next = 0; assert(pwp_reserve(&owner, &next) == PWP_CLEANUP_UNKNOWN);
}
static void poisoned_owner_cannot_publish(void) {
    for (int mode = 0; mode < 3; ++mode) {
        pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
        owner.poisoned = mode == 0; f.poison = mode != 0; f.reject = mode == 2;
        assert(pwp_child_finish(&owner, token, verify, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(!pwp_lookup(&owner, token)->published && pwp_lookup(&owner, token)->state == 3);
        assert(f.closes == 1 && f.verifies == (mode == 0 ? 0u : 1u));
    }
}
static void public_capacity_rejects_before_verification(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    for (unsigned i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i) {
        uint64_t other = 0;
        assert(pwp_reserve(&owner, &other) == PWP_OK && pwp_attach(&owner, other, 7) == PWP_OK);
        assert(pwp_publish(&owner, other) == PWP_OK);
    }
    assert(pwp_child_finish(&owner, token, verify, close_handle, &f) == PWP_LIMIT);
    assert(f.verifies == 0 && f.closes == 1 && pwp_public_count(&owner) == PWP_PUBLIC_HANDLE_LIMIT);
}
static void failed_publication_retires_exact_resource(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner; f.exhaust = 1;
    assert(pwp_child_finish(&owner, token, verify, close_handle, &f) == PWP_LIMIT);
    assert(f.verifies == 1 && f.closes == 1 && !pwp_lookup(&owner, token)->published);
    assert(pwp_lookup(&owner, token)->state == 3);
}
static void no_republication_or_stale_token(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    assert(pwp_child_finish(&owner, token, verify, close_handle, &f) == PWP_OK);
    assert(pwp_child_finish(&owner, token, verify, close_handle, &f) == PWP_ARGUMENT && f.ordered == 1);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK);
    uint64_t next = 0; assert(pwp_reserve(&owner, &next) == PWP_OK && next != token);
    assert(pwp_attach(&owner, next, 7) == PWP_OK);
    assert(pwp_child_finish(&owner, token, verify, close_handle, &f) == PWP_ARGUMENT && f.ordered == 2);
    assert(pwp_retire(&owner, next, close_handle, &f) == PWP_OK);
}
typedef struct { uintptr_t resources[2]; size_t count; } retirement;
static int ordered_close(uintptr_t resource, void *context) {
    retirement *r = context; assert(r->count < 2); r->resources[r->count++] = resource; return 1;
}
static void session_closes_child_before_parent(void) {
    pwp_owner owner; pwp_owner_init(&owner); uint64_t parent = 0, child = 0;
    assert(pwp_reserve(&owner, &parent) == PWP_OK && pwp_attach(&owner, parent, 9) == PWP_OK);
    assert(pwp_publish(&owner, parent) == PWP_OK);
    assert(pwp_reserve(&owner, &child) == PWP_OK && pwp_attach(&owner, child, 7) == PWP_OK);
    fake f = {0}; f.owner = &owner;
    assert(pwp_child_finish(&owner, child, verify, close_handle, &f) == PWP_OK);
    retirement retired = {{0}, 0}; assert(pwp_retire_all(&owner, ordered_close, &retired) == PWP_OK);
    assert(retired.count == 2 && retired.resources[0] == 7 && retired.resources[1] == 9);
    assert(pwp_retire_all(&owner, ordered_close, &retired) == PWP_OK && retired.count == 2);
}
int main(void) {
    success_retains_exact_lease(); directory_tuples_are_exact(); invalid_arguments_do_not_transfer_ownership();
    rejection_closes_once_without_publication(); failed_close_retains_quarantine_without_retry();
    poisoned_owner_cannot_publish(); public_capacity_rejects_before_verification();
    failed_publication_retires_exact_resource(); no_republication_or_stale_token(); session_closes_child_before_parent();
    puts("10 portable child-custody groups PASS; NOT Windows creation/DACL/namespace durability qualification"); return 0;
}
