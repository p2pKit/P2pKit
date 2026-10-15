#include "../profile_policy.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* Instrument the actual shared allocator via compile-time libc hooks; never emulate a Windows API. */
static unsigned allocations, releases, calls;
static int fail_allocation;
static unsigned char *live;
static size_t live_count;
void *pwp_test_calloc(size_t count, size_t size) {
    assert(!live && count <= PWP_RECORD_LIMIT && size == 1); ++allocations;
    if (fail_allocation) return NULL;
    live_count = count; live = calloc(count, size); assert(live); return live;
}
void pwp_test_free(void *bytes) {
    if (!bytes) { assert(!live); return; }
    assert(bytes == live);
    for (size_t i = 0; i < live_count; ++i) assert(live[i] == 0);
    ++releases; free(bytes); live = NULL; live_count = 0;
}
static pwp_result use_buffer(unsigned char *bytes, size_t count, void *context) {
    ++calls;
    assert(count == 0 ? bytes == NULL : bytes == live && count == live_count);
    for (size_t i = 0; i < count; ++i) assert(bytes[i] == 0);
    if (count) memset(bytes, 0xa5, count);
    return *(pwp_result *)context;
}
static void clear_before_release_for_every_outcome(void) {
    for (int code = PWP_OK; code <= PWP_UNIMPLEMENTED; ++code) {
        pwp_result result = (pwp_result)code;
        unsigned before = releases;
        assert(pwp_buffer_apply(PWP_RECORD_LIMIT, use_buffer, &result) == result);
        assert(releases == before+1 && !live);
    }
}
static void zero_length_owns_no_allocation(void) {
    unsigned before = allocations, called = calls; pwp_result result = PWP_OK;
    assert(pwp_buffer_apply(0, use_buffer, &result) == PWP_OK);
    assert(allocations == before && calls == called+1 && !live);
}
static void invalid_requests_never_allocate_or_call(void) {
    unsigned before = allocations, called = calls; pwp_result result = PWP_OK;
    assert(pwp_buffer_apply(PWP_RECORD_LIMIT+1, use_buffer, &result) == PWP_ARGUMENT);
    assert(pwp_buffer_apply(SIZE_MAX, use_buffer, &result) == PWP_ARGUMENT);
    assert(pwp_buffer_apply(1, NULL, &result) == PWP_ARGUMENT);
    assert(allocations == before && calls == called && !live);
}
static void allocation_failure_never_calls_or_releases(void) {
    unsigned before = allocations, released = releases, called = calls; pwp_result result = PWP_OK;
    fail_allocation = 1;
    assert(pwp_buffer_apply(8, use_buffer, &result) == PWP_LIMIT);
    assert(allocations == before+1 && releases == released && calls == called && !live);
    fail_allocation = 0;
    assert(pwp_buffer_apply(8, use_buffer, &result) == PWP_OK && releases == released+1);
}
int main(void) {
    clear_before_release_for_every_outcome(); zero_length_owns_no_allocation();
    invalid_requests_never_allocate_or_call(); allocation_failure_never_calls_or_releases();
    puts("4 portable bounded-buffer lifecycle groups PASS; NOT Windows admission/runtime qualification"); return 0;
}
