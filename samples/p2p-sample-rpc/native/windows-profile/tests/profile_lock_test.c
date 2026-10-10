#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Shared orchestration contracts, not Windows open/share/ACL/durability emulation. */
typedef struct {
    unsigned verifies, flushes, closes;
    unsigned reject_verify;
    int fail_flush, fail_close, poison_on_verify;
    char order[8]; size_t ordered;
    pwp_owner *owner;
} fake;
static void record(fake *f, char action) { assert(f->ordered < sizeof(f->order)); f->order[f->ordered++] = action; }
static int verify(void *context) {
    fake *f = context; ++f->verifies; record(f, 'V');
    if (f->poison_on_verify) f->owner->poisoned = 1;
    return f->verifies != f->reject_verify;
}
static int flush(void *context) { fake *f = context; ++f->flushes; record(f, 'F'); return !f->fail_flush; }
static int close_handle(uintptr_t resource, void *context) {
    fake *f = context; assert(resource == 7); ++f->closes; record(f, 'C'); return !f->fail_close;
}
static uint64_t allocated(pwp_owner *owner) {
    uint64_t token = 0; pwp_owner_init(owner);
    assert(pwp_reserve(owner, &token) == PWP_OK && pwp_attach(owner, token, 7) == PWP_OK); return token;
}
static void exact_order_and_owned_lease(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_OK);
    assert(f.ordered == 3 && memcmp(f.order, "VFV", 3) == 0 && f.closes == 0);
    assert(pwp_public_count(&owner) == 1 && pwp_lookup(&owner, token)->state == 2);
    assert(pwp_lookup(&owner, token)->resource == 7 && pwp_lookup(&owner, token)->published);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK && f.closes == 1);
}
static void bad_arguments_do_not_assume_ownership(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    assert(pwp_lock_finish(NULL, token, verify, flush, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_lock_finish(&owner, 0, verify, flush, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_lock_finish(&owner, token+1, verify, flush, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_lock_finish(&owner, token, NULL, flush, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_lock_finish(&owner, token, verify, NULL, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_lock_finish(&owner, token, verify, flush, NULL, &f) == PWP_ARGUMENT);
    assert(f.ordered == 0 && pwp_lookup(&owner, token)->state == 2);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK && f.closes == 1);
}
static void verification_failure_never_publishes(void) {
    for (unsigned fail = 1; fail <= 2; ++fail) {
        pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner; f.reject_verify = fail;
        assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_POLICY);
        assert(f.verifies == fail && f.flushes == fail-1 && f.closes == 1 && pwp_public_count(&owner) == 0);
        assert(pwp_lookup(&owner, token)->state == 3 && !pwp_lookup(&owner, token)->published);
        assert(pwp_retire_all(&owner, close_handle, &f) == PWP_OK && f.closes == 1);
    }
}
static void flush_failure_closes_without_retry(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner; f.fail_flush = 1;
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_OS);
    assert(f.ordered == 3 && memcmp(f.order, "VFC", 3) == 0 && pwp_public_count(&owner) == 0);
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_ARGUMENT && f.ordered == 3);
}
static void uncertain_close_is_quarantined(void) {
    for (int mode = 0; mode < 3; ++mode) {
        pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
        f.fail_close = 1; f.reject_verify = mode == 0 ? 1u : mode == 2 ? 2u : 0u; f.fail_flush = mode == 1;
        assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(f.closes == 1 && owner.poisoned && pwp_lookup(&owner, token)->state == 4);
        assert(pwp_lookup(&owner, token)->resource == 7 && !pwp_lookup(&owner, token)->published);
        assert(pwp_retire_all(&owner, close_handle, &f) == PWP_CLEANUP_UNKNOWN && f.closes == 1);
        uint64_t another = 0; assert(pwp_reserve(&owner, &another) == PWP_CLEANUP_UNKNOWN);
    }
}
static void no_republication_or_stale_token(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_OK);
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_ARGUMENT && f.ordered == 3);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK); uint64_t next = 0;
    assert(pwp_reserve(&owner, &next) == PWP_OK && next != token && pwp_attach(&owner, next, 7) == PWP_OK);
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_ARGUMENT && f.ordered == 4);
    assert(pwp_retire(&owner, next, close_handle, &f) == PWP_OK);
}
static void capacity_preflight_prevents_observation(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    for (unsigned i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i) {
        uint64_t other = 0; assert(pwp_reserve(&owner, &other) == PWP_OK && pwp_attach(&owner, other, 7) == PWP_OK);
        assert(pwp_publish(&owner, other) == PWP_OK);
    }
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_LIMIT);
    assert(f.verifies == 0 && f.flushes == 0 && f.closes == 1 && pwp_public_count(&owner) == PWP_PUBLIC_HANDLE_LIMIT);
}
static void poisoned_owner_never_publishes(void) {
    for (int mode = 0; mode < 2; ++mode) {
        pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
        owner.poisoned = mode == 0; f.poison_on_verify = mode == 1;
        assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(f.closes == 1 && !pwp_lookup(&owner, token)->published && pwp_lookup(&owner, token)->state == 3);
        assert(f.flushes == 0 && f.verifies == (mode == 1 ? 1u : 0u));
    }
}
int main(void) {
    exact_order_and_owned_lease(); bad_arguments_do_not_assume_ownership(); verification_failure_never_publishes();
    flush_failure_closes_without_retry(); uncertain_close_is_quarantined(); no_republication_or_stale_token();
    capacity_preflight_prevents_observation(); poisoned_owner_never_publishes();
    puts("8 portable new-lock custody groups PASS; NOT Windows sharing/ACL/namespace durability qualification"); return 0;
}
