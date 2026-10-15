#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Exercises the production controller only, not Windows deletion/sharing/durability semantics. */
typedef struct {
    pwp_owner *owner; uint64_t token;
    char order[8]; size_t count;
    int reject_verify, fail_mark, reject_pending, fail_close;
    char poison_at;
    int reenter; unsigned reentries;
} fake;
static pwp_result run(fake *f);
static void record(fake *f, char action) {
    assert(f->count < sizeof(f->order)); f->order[f->count++] = action;
    assert(pwp_lookup(f->owner, f->token)->state == 4);
    if (f->reenter) {
        size_t before = f->count; assert(run(f) == PWP_ARGUMENT);
        assert(f->count == before); ++f->reentries;
    }
    if (f->poison_at == action) f->owner->poisoned = 1;
}
static int verify(void *c) { fake *f = c; record(f, 'V'); return !f->reject_verify; }
static int mark(void *c) { fake *f = c; record(f, 'M'); return !f->fail_mark; }
static int pending(void *c) { fake *f = c; record(f, 'P'); return !f->reject_pending; }
static int close_handle(uintptr_t resource, void *c) {
    fake *f = c; assert(resource == 7); record(f, 'C'); return !f->fail_close;
}
static fake allocated(pwp_owner *o) {
    fake f = {0}; f.owner = o; pwp_owner_init(o);
    assert(pwp_reserve(o, &f.token) == PWP_OK && pwp_attach(o, f.token, 7) == PWP_OK); return f;
}
static pwp_result run(fake *f) {
    return pwp_delete_intent_finish(f->owner, f->token, verify, mark, pending, close_handle, f);
}
static void shape_is_exact_and_bit_preserving(void) {
    const uint64_t good[] = {1, UINT64_C(0x8000000000000001), 0, 8, 0x2ff, 1};
    assert(pwp_expected_file(good, 6, good[1]));
    assert(!pwp_expected_file(NULL, 6, good[1]));
    assert(!pwp_expected_file(good, 5, good[1]) && !pwp_expected_file(good, 7, good[1]));
    assert(!pwp_expected_file(good, 6, 0) && !pwp_expected_file(good, 6, 3));
    const uint64_t bad_values[] = {2, 0, 0, 0, 0x1ff, 2};
    for (size_t i = 0; i < 6; ++i) {
        if (i == 2) continue;
        uint64_t copy[6]; memcpy(copy, good, sizeof(copy)); copy[i] = bad_values[i];
        assert(!pwp_expected_file(copy, 6, copy[1]));
    }
    uint64_t copy[6]; memcpy(copy, good, sizeof(copy)); copy[2] = UINT64_MAX; copy[3] = 0;
    assert(pwp_expected_file(copy, 6, copy[1])); copy[4] = 0; assert(!pwp_expected_file(copy, 6, copy[1]));
}
static void success_is_exact_intent_readback_and_retirement(void) {
    pwp_owner o; fake f = allocated(&o); assert(run(&f) == PWP_OK);
    assert(f.count == 4 && memcmp(f.order, "VMPC", 4) == 0);
    assert(!o.poisoned && pwp_lookup(&o, f.token)->state == 3 && !pwp_lookup(&o, f.token)->resource);
    assert(pwp_public_count(&o) == 0);
    assert(pwp_retire_all(&o, close_handle, &f) == PWP_OK && f.count == 4);
}
static void invalid_arguments_never_take_ownership(void) {
    pwp_owner o; fake f = allocated(&o);
    assert(pwp_delete_intent_finish(NULL, f.token, verify, mark, pending, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_delete_intent_finish(&o, 0, verify, mark, pending, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_delete_intent_finish(&o, f.token, NULL, mark, pending, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_delete_intent_finish(&o, f.token, verify, NULL, pending, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_delete_intent_finish(&o, f.token, verify, mark, NULL, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_delete_intent_finish(&o, f.token, verify, mark, pending, NULL, &f) == PWP_ARGUMENT);
    assert(f.count == 0 && pwp_lookup(&o, f.token)->state == 2);
    assert(run(&f) == PWP_OK);
}
static void published_lease_is_not_borrowed(void) {
    pwp_owner o; fake f = allocated(&o); assert(pwp_publish(&o, f.token) == PWP_OK);
    assert(run(&f) == PWP_ARGUMENT && f.count == 0 && pwp_lookup(&o, f.token)->state == 2);
    assert(pwp_retire_all(&o, close_handle, &f) == PWP_OK && f.count == 1);
}
static void verification_failure_closes_without_mark(void) {
    pwp_owner o; fake f = allocated(&o); f.reject_verify = 1;
    assert(run(&f) == PWP_POLICY && f.count == 2 && memcmp(f.order, "VC", 2) == 0);
    assert(!o.poisoned && pwp_lookup(&o, f.token)->state == 3);
}
static void uncertain_mark_or_pending_is_never_retried(void) {
    for (int mode = 0; mode < 2; ++mode) {
        pwp_owner o; fake f = allocated(&o); f.fail_mark = mode == 0; f.reject_pending = mode == 1;
        assert(run(&f) == PWP_CLEANUP_UNKNOWN && o.poisoned);
        assert(f.count == (mode == 0 ? 3u : 4u));
        assert(memcmp(f.order, mode == 0 ? "VMC" : "VMPC", f.count) == 0);
        assert(pwp_lookup(&o, f.token)->state == 4 && pwp_lookup(&o, f.token)->resource == 7);
        size_t before = f.count; assert(pwp_retire_all(&o, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(run(&f) == PWP_ARGUMENT && f.count == before);
        uint64_t other = 0; assert(pwp_reserve(&o, &other) == PWP_CLEANUP_UNKNOWN);
    }
}
static void uncertain_close_retains_original_resource(void) {
    for (int mode = 0; mode < 3; ++mode) {
        pwp_owner o; fake f = allocated(&o); f.fail_close = 1;
        f.reject_verify = mode == 0; f.fail_mark = mode == 1;
        assert(run(&f) == PWP_CLEANUP_UNKNOWN && o.poisoned);
        assert(pwp_lookup(&o, f.token)->state == 4 && pwp_lookup(&o, f.token)->resource == 7);
        size_t before = f.count; assert(pwp_retire_all(&o, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(f.count == before);
    }
}
static void poison_before_mutation_prevents_mark(void) {
    for (int mode = 0; mode < 2; ++mode) {
        pwp_owner o; fake f = allocated(&o); o.poisoned = mode == 0; f.poison_at = mode == 1 ? 'V' : 0;
        assert(run(&f) == PWP_CLEANUP_UNKNOWN);
        assert(f.count == (mode == 0 ? 1u : 2u));
        assert(memcmp(f.order, mode == 0 ? "C" : "VC", f.count) == 0);
        assert(pwp_lookup(&o, f.token)->state == 3);
    }
}
static void poison_after_mutation_quarantines_even_when_closed(void) {
    const char steps[] = {'M', 'P', 'C'};
    for (size_t i = 0; i < sizeof(steps); ++i) {
        pwp_owner o; fake f = allocated(&o); f.poison_at = steps[i];
        assert(run(&f) == PWP_CLEANUP_UNKNOWN && o.poisoned && f.order[f.count-1] == 'C');
        assert(pwp_lookup(&o, f.token)->state == 4 && pwp_lookup(&o, f.token)->resource == 7);
        size_t before = f.count; assert(pwp_retire_all(&o, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(f.count == before);
    }
}
static void stale_token_cannot_mutate_new_resource(void) {
    pwp_owner o; fake f = allocated(&o); assert(run(&f) == PWP_OK); uint64_t old = f.token, next = 0;
    assert(pwp_reserve(&o, &next) == PWP_OK && next != old && pwp_attach(&o, next, 7) == PWP_OK);
    assert(run(&f) == PWP_ARGUMENT && f.count == 4 && pwp_lookup(&o, next)->state == 2);
    f.token = next; f.count = 0; assert(run(&f) == PWP_OK && f.count == 4);
}
static void every_callback_reentry_is_rejected_without_nested_actions(void) {
    pwp_owner o; fake f = allocated(&o); f.reenter = 1;
    assert(run(&f) == PWP_OK && f.reentries == 4 && f.count == 4 && memcmp(f.order, "VMPC", 4) == 0);
    assert(pwp_lookup(&o, f.token)->state == 3 && !o.poisoned);
    assert(pwp_retire_all(&o, close_handle, &f) == PWP_OK && f.reentries == 4 && f.count == 4);
}
int main(void) {
    shape_is_exact_and_bit_preserving(); success_is_exact_intent_readback_and_retirement();
    invalid_arguments_never_take_ownership(); published_lease_is_not_borrowed();
    verification_failure_closes_without_mark(); uncertain_mark_or_pending_is_never_retried();
    uncertain_close_retains_original_resource(); poison_before_mutation_prevents_mark();
    poison_after_mutation_quarantines_even_when_closed(); stale_token_cannot_mutate_new_resource();
    every_callback_reentry_is_rejected_without_nested_actions();
    puts("11 portable delete-intent groups PASS; NOT Windows deletion or namespace durability qualification"); return 0;
}
