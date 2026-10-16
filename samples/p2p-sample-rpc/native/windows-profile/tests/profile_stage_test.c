#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Deterministic callback contracts, not emulated Windows APIs or native durability evidence. */
typedef struct {
    unsigned writes, flushes, checks, deletes, closes;
    size_t size, quantum;
    int fail_write, zero_write, oversize_write, fail_flush, fail_check, fail_delete, fail_close;
    unsigned fail_check_number;
    pwp_stage *reentrant;
} fake;
static int mark_delete(void *context);
static int close_handle(void *context);
static int write_bytes(const unsigned char *data, size_t length, size_t *actual, void *context) {
    fake *f = context; assert(data && length && length <= 65536); ++f->writes;
    if (f->reentrant) assert(pwp_stage_discard(f->reentrant, mark_delete, close_handle, f) == PWP_BUSY);
    if (f->fail_write) return 0;
    *actual = f->zero_write ? 0 : f->oversize_write ? length+1 : length < f->quantum ? length : f->quantum;
    if (*actual <= length) f->size += *actual;
    return 1;
}
static int flush_bytes(void *context) { fake *f = context; ++f->flushes; return !f->fail_flush; }
static int verify_size(size_t size, void *context) {
    fake *f = context; ++f->checks; return !f->fail_check && f->checks != f->fail_check_number && size == f->size;
}
static int mark_delete(void *context) { fake *f = context; ++f->deletes; return !f->fail_delete; }
static int close_handle(void *context) {
    fake *f = context; ++f->closes;
    if (f->reentrant) assert(pwp_stage_discard(f->reentrant, mark_delete, close_handle, f) == PWP_CLEANUP_UNKNOWN);
    return !f->fail_close;
}
static fake defaults(void) { fake f = {0}; f.quantum = 65536; return f; }
static void stage_name_policy(void) {
    const char *valid = "pwp-stage-0123456789abcdef0123456789abcdef";
    uint16_t name[64] = {0}; size_t n = strlen(valid);
    for (size_t i = 0; i < n; ++i) name[i] = (uint16_t)valid[i];
    assert(pwp_stage_name(name, n)); assert(!pwp_stage_name(name, n-1));
    name[10] = 'G'; assert(!pwp_stage_name(name, n)); name[10] = 'A'; assert(!pwp_stage_name(name, n));
    name[10] = '0'; name[0] = 'P'; assert(!pwp_stage_name(name, n));
    assert(!pwp_stage_name(NULL, n)); assert(!pwp_stage_name(name, SIZE_MAX));
}
static void partial_and_zero_length(void) {
    unsigned char data[70000] = {0}; fake f = defaults(); f.quantum = 10000; pwp_stage s = {0};
    assert(pwp_stage_init(&s) == PWP_OK);
    assert(pwp_stage_fill(&s, data, sizeof(data), write_bytes, flush_bytes, verify_size, &f) == PWP_OK);
    assert(f.writes == 7 && f.flushes == 1 && f.checks == 2 && f.size == sizeof(data));
    assert(s.phase == PWP_STAGE_FLUSHED);
    assert(pwp_stage_fill(&s, data, 1, write_bytes, flush_bytes, verify_size, &f) == PWP_CLOSED);
    assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_OK);
    assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_OK);
    assert(f.deletes == 1 && f.closes == 1 && pwp_stage_init(&s) == PWP_CLOSED);
    s = (pwp_stage){0}; f = defaults(); assert(pwp_stage_init(&s) == PWP_OK);
    assert(pwp_stage_fill(&s, NULL, 0, write_bytes, flush_bytes, verify_size, &f) == PWP_OK);
    assert(f.writes == 0 && f.flushes == 1 && f.checks == 2);
    assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_OK);
}
static void bounds_before_callbacks(void) {
    fake f = defaults(); pwp_stage s = {0}; unsigned char byte = 1;
    assert(pwp_stage_init(&s) == PWP_OK);
    assert(pwp_stage_fill(&s, &byte, PWP_RECORD_LIMIT+1, write_bytes, flush_bytes, verify_size, &f) == PWP_ARGUMENT);
    assert(pwp_stage_fill(&s, NULL, 1, write_bytes, flush_bytes, verify_size, &f) == PWP_ARGUMENT);
    assert(pwp_stage_fill(&s, &byte, 1, NULL, flush_bytes, verify_size, &f) == PWP_ARGUMENT);
    assert(!f.writes && !f.flushes && !f.checks && s.phase == PWP_STAGE_OWNED);
    assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_OK);
    s = (pwp_stage){0}; assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_ARGUMENT);
    assert(f.deletes == 1 && f.closes == 1);
}
static void rejected_progress_and_failures(void) {
    unsigned char data[8] = {0};
    for (int failure = 0; failure < 6; ++failure) {
        fake f = defaults(); pwp_stage s = {0}; assert(pwp_stage_init(&s) == PWP_OK);
        f.fail_write = failure == 0; f.zero_write = failure == 1; f.oversize_write = failure == 2;
        f.fail_flush = failure == 3; f.fail_check = failure == 4; f.fail_check_number = failure == 5 ? 2u : 0u;
        assert(pwp_stage_fill(&s, data, sizeof(data), write_bytes, flush_bytes, verify_size, &f) != PWP_OK);
        assert(s.phase == PWP_STAGE_FAILED);
        unsigned writes = f.writes;
        assert(pwp_stage_fill(&s, data, sizeof(data), write_bytes, flush_bytes, verify_size, &f) == PWP_CLOSED);
        assert(f.writes == writes && f.flushes == (failure == 3 || failure == 5 ? 1u : 0u));
        assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_OK);
        assert(f.deletes == 1 && f.closes == 1);
    }
}
static void cleanup_uncertainty_retained(void) {
    for (int failure = 1; failure <= 3; ++failure) {
        fake f = defaults(); pwp_stage s = {0}; assert(pwp_stage_init(&s) == PWP_OK);
        f.fail_delete = failure & 1; f.fail_close = failure & 2;
        assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(s.phase == PWP_STAGE_QUARANTINED && f.deletes == 1 && f.closes == 1);
        assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(f.deletes == 1 && f.closes == 1);
    }
}
static void close_reentry_and_unfilled(void) {
    fake f = defaults(); pwp_stage s = {0}; assert(pwp_stage_init(&s) == PWP_OK); f.reentrant = &s;
    assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_OK);
    assert(f.deletes == 1 && f.closes == 1);
}
static void full_record_and_inflight_discard(void) {
    static const unsigned char data[PWP_RECORD_LIMIT] = {0}; fake f = defaults(); pwp_stage s = {0};
    assert(pwp_stage_init(&s) == PWP_OK); f.reentrant = &s;
    assert(pwp_stage_fill(&s, data, sizeof(data), write_bytes, flush_bytes, verify_size, &f) == PWP_OK);
    assert(f.writes == 4 && f.flushes == 1 && f.checks == 2 && f.size == PWP_RECORD_LIMIT);
    assert(f.deletes == 0 && f.closes == 0);
    assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_OK);
    assert(f.deletes == 1 && f.closes == 1);
}
typedef struct { pwp_stage stage; fake callbacks; } owned_stage;
static int retire_stage(uintptr_t resource, void *context) {
    owned_stage *s = context; assert(resource == 7);
    return pwp_stage_discard(&s->stage, mark_delete, close_handle, &s->callbacks) == PWP_OK;
}
static void owner_retains_stage_uncertainty(void) {
    for (int fail = 0; fail < 2; ++fail) {
        pwp_owner owner; pwp_owner_init(&owner); uint64_t token = 0;
        owned_stage stage = {0}; stage.callbacks = defaults(); stage.callbacks.fail_delete = fail;
        assert(pwp_stage_init(&stage.stage) == PWP_OK);
        assert(pwp_reserve(&owner, &token) == PWP_OK && pwp_attach(&owner, token, 7) == PWP_OK);
        assert(pwp_publish(&owner, token) == PWP_OK);
        pwp_result expected = fail ? PWP_CLEANUP_UNKNOWN : PWP_OK;
        assert(pwp_retire_all(&owner, retire_stage, &stage) == expected);
        assert(pwp_retire_all(&owner, retire_stage, &stage) == expected);
        assert(stage.callbacks.deletes == 1 && stage.callbacks.closes == 1);
        assert(owner.poisoned == fail && pwp_lookup(&owner, token)->state == (fail ? 4u : 3u));
        assert(pwp_public_count(&owner) == (fail ? 1u : 0u));
        if (fail) assert(pwp_reserve(&owner, &token) == PWP_CLEANUP_UNKNOWN);
    }
}
static void stages_never_export_regular_metadata(void) {
    assert(pwp_regular_metadata(PWP_STAGE_EMPTY));
    pwp_stage s = {0}; assert(pwp_stage_init(&s) == PWP_OK);
    assert(!pwp_regular_metadata(s.phase));
    for (unsigned phase = PWP_STAGE_OWNED; phase <= PWP_STAGE_QUARANTINED; ++phase)
        assert(!pwp_regular_metadata((pwp_stage_phase)phase));
    assert(!pwp_regular_metadata((pwp_stage_phase)100));
    /* A stage's identity is not evidence for an ordinary durable record, even after a successful file flush. */
    fake f = defaults(); unsigned char data[1] = {0};
    assert(pwp_stage_fill(&s, data, sizeof(data), write_bytes, flush_bytes, verify_size, &f) == PWP_OK);
    assert(!pwp_regular_metadata(s.phase));
    assert(pwp_stage_discard(&s, mark_delete, close_handle, &f) == PWP_OK);
    assert(!pwp_regular_metadata(s.phase));
}
int main(void) {
    stage_name_policy(); partial_and_zero_length(); bounds_before_callbacks(); rejected_progress_and_failures();
    cleanup_uncertainty_retained(); close_reentry_and_unfilled(); full_record_and_inflight_discard();
    owner_retains_stage_uncertainty(); stages_never_export_regular_metadata();
    puts("9 portable uncommitted-stage contract groups PASS; NOT Windows OS or durability qualification"); return 0;
}
