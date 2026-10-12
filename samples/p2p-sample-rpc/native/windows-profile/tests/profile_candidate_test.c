#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { VERIFY = 1, WRITE, FLUSH, REWIND, READ };
typedef struct {
    pwp_candidate candidate;
    unsigned char *input, *stored;
    size_t count, size, position, write_chunk, read_chunk, largest_write, largest_read;
    size_t verified_sizes[3];
    unsigned calls, writes, flushes, rewinds, reads, verifies, trace[128];
    unsigned fail_write, zero_write, oversized_write, fail_read, zero_read, oversized_read, wrong_read;
    unsigned fail_verify;
    int fail_flush, fail_rewind, extra_tail, fail_eof, oversized_eof, partial_error, reenter;
} fixture;

static int write_bytes(const unsigned char *bytes, size_t count, size_t *actual, void *opaque);
static int flush_bytes(void *opaque);
static int rewind_bytes(void *opaque);
static int read_bytes(unsigned char *bytes, size_t capacity, size_t *actual, void *opaque);
static int verify_bytes(size_t expected_size, void *opaque);
static pwp_result fill(fixture *f) {
    return pwp_candidate_fill(&f->candidate, f->input, f->count,
        write_bytes, flush_bytes, rewind_bytes, read_bytes, verify_bytes, f);
}
static fixture *new_fixture(size_t count) {
    assert(count <= PWP_RECORD_LIMIT);
    fixture *f = calloc(1, sizeof(*f)); assert(f);
    f->count = count;
    f->stored = calloc(PWP_RECORD_LIMIT+1, 1); assert(f->stored);
    if (count) {
        f->input = malloc(count); assert(f->input);
        for (size_t i = 0; i < count; ++i) f->input[i] = (unsigned char)(i*17u+1u);
    }
    f->candidate.prepared_size = PWP_RECORD_LIMIT+1;
    assert(pwp_candidate_init(&f->candidate) == PWP_OK && f->candidate.prepared_size == 0);
    return f;
}
static void destroy_fixture(fixture *f) {
    pwp_clear(f->input, f->count); free(f->input);
    pwp_clear(f->stored, PWP_RECORD_LIMIT+1); free(f->stored);
    pwp_clear(f, sizeof(*f)); free(f);
}
static void observe(fixture *f, unsigned event) {
    assert(f->candidate.phase == PWP_CANDIDATE_FILLING);
    assert(f->candidate.prepared_size == 0);
    assert(f->calls < sizeof(f->trace)/sizeof(f->trace[0]));
    f->trace[f->calls++] = event;
    if (f->reenter) {
        unsigned before = f->calls;
        assert(pwp_candidate_init(&f->candidate) == PWP_CLOSED);
        assert(fill(f) == PWP_CLOSED);
        assert(f->calls == before && f->candidate.phase == PWP_CANDIDATE_FILLING);
    }
}
static int write_bytes(const unsigned char *bytes, size_t count, size_t *actual, void *opaque) {
    fixture *f = opaque; observe(f, WRITE); ++f->writes;
    assert(bytes == f->input+f->size && actual && count && count <= 65536);
    assert(count <= f->count-f->size);
    if (count > f->largest_write) f->largest_write = count;
    if (f->writes == f->oversized_write) { *actual = count+1; return 1; }
    if (f->writes == f->zero_write) { *actual = 0; return 1; }
    if (f->writes == f->fail_write && !f->partial_error) { *actual = 0; return 0; }
    size_t taken = f->write_chunk && f->write_chunk < count ? f->write_chunk : count;
    if (f->writes == f->fail_write && taken > 3) taken = 3;
    memcpy(f->stored+f->size, bytes, taken); f->size += taken; *actual = taken;
    return f->writes != f->fail_write;
}
static int flush_bytes(void *opaque) {
    fixture *f = opaque; observe(f, FLUSH); ++f->flushes;
    assert(f->size == f->count && f->flushes == 1);
    return !f->fail_flush;
}
static int rewind_bytes(void *opaque) {
    fixture *f = opaque; observe(f, REWIND); ++f->rewinds;
    assert(f->flushes == 1 && f->verifies == 2 && f->rewinds == 1);
    f->position = 0;
    return !f->fail_rewind;
}
static int read_bytes(unsigned char *bytes, size_t capacity, size_t *actual, void *opaque) {
    fixture *f = opaque; observe(f, READ); ++f->reads;
    assert(bytes && actual && capacity && capacity <= 4096 && f->rewinds == 1);
    if (capacity > f->largest_read) f->largest_read = capacity;
    /* Same fixed scratch is clean before each bounded read, including after shorter chunks. */
    for (size_t i = 0; i < capacity; ++i) assert(bytes[i] == 0);
    if (f->position == f->size) {
        assert(capacity == 1);
        if (f->oversized_eof) { *actual = 2; return 1; }
        if (f->extra_tail) { bytes[0] = 0xa5; *actual = 1; return 1; }
        *actual = 0; return !f->fail_eof;
    }
    if (f->reads == f->oversized_read) { *actual = capacity+1; return 1; }
    if (f->reads == f->zero_read) { *actual = 0; return 1; }
    if (f->reads == f->fail_read && !f->partial_error) { *actual = 0; return 0; }
    size_t taken = f->size-f->position;
    if (taken > capacity) taken = capacity;
    if (f->read_chunk && taken > f->read_chunk) taken = f->read_chunk;
    if (f->reads == f->fail_read && taken > 3) taken = 3;
    memcpy(bytes, f->stored+f->position, taken); f->position += taken; *actual = taken;
    if (f->reads == f->wrong_read) bytes[taken-1] ^= 0x80;
    return f->reads != f->fail_read;
}
static int verify_bytes(size_t expected_size, void *opaque) {
    fixture *f = opaque; observe(f, VERIFY); ++f->verifies;
    assert(f->verifies <= 3 && expected_size == (f->verifies == 1 ? 0 : f->count));
    f->verified_sizes[f->verifies-1] = expected_size;
    if (f->verifies == 2) assert(f->flushes == 1);
    if (f->verifies == 3) assert(f->rewinds == 1 && f->position == f->size && f->reads);
    return f->verifies != f->fail_verify && f->size == expected_size;
}
static void expect_failure(fixture *f, pwp_result expected) {
    assert(fill(f) == expected && f->candidate.phase == PWP_CANDIDATE_FAILED);
    assert(f->candidate.prepared_size == 0);
    unsigned calls = f->calls;
    assert(fill(f) == PWP_CLOSED && pwp_candidate_init(&f->candidate) == PWP_CLOSED);
    assert(f->calls == calls && f->candidate.phase == PWP_CANDIDATE_FAILED && f->candidate.prepared_size == 0);
}
static size_t wide(const char *text, uint16_t *output) {
    size_t length = strlen(text);
    for (size_t i = 0; i < length; ++i) output[i] = (unsigned char)text[i];
    return length;
}
static void candidate_names(void) {
    uint16_t name[96] = {0};
    size_t count = wide("pwp-pending-0123456789abcdef0123456789abcdef", name);
    assert(count == 44 && pwp_candidate_name(name, count));
    assert(!pwp_stage_name(name, count));
    assert(!pwp_candidate_name(NULL, count));
    for (size_t size = 0; size < count; ++size) assert(!pwp_candidate_name(name, size));
    assert(!pwp_candidate_name(name, count+1));
    const uint16_t bad[] = {'A', 'g', '-', '.', '/', '\\', ':', 0, 0xd800};
    for (size_t i = 0; i < count; ++i) {
        uint16_t saved = name[i];
        for (size_t j = 0; j < sizeof(bad)/sizeof(bad[0]); ++j) {
            if (bad[j] == saved) continue;
            name[i] = bad[j]; assert(!pwp_candidate_name(name, count));
        }
        name[i] = saved;
    }
    count = wide("pwp-stage-0123456789abcdef0123456789abcdef", name);
    assert(!pwp_candidate_name(name, count));
}
static void candidate_initialization_and_phases(void) {
    assert(pwp_candidate_init(NULL) == PWP_ARGUMENT);
    pwp_candidate empty = {0};
    assert(pwp_candidate_init(&empty) == PWP_OK && empty.phase == PWP_CANDIDATE_OWNED);
    assert(empty.prepared_size == 0);
    assert(pwp_candidate_init(&empty) == PWP_CLOSED && empty.phase == PWP_CANDIDATE_OWNED);
    const pwp_candidate_phase phases[] = {PWP_CANDIDATE_EMPTY, PWP_CANDIDATE_FILLING,
        PWP_CANDIDATE_VERIFIED, PWP_CANDIDATE_FAILED, PWP_CANDIDATE_RENAMING,
        PWP_CANDIDATE_RENAMED, PWP_CANDIDATE_UNCERTAIN, (pwp_candidate_phase)99};
    for (size_t i = 0; i < sizeof(phases)/sizeof(phases[0]); ++i) {
        fixture *f = new_fixture(1); f->candidate.phase = phases[i];
        f->candidate.prepared_size = 17;
        assert(fill(f) == PWP_CLOSED && f->calls == 0 && f->candidate.phase == phases[i]);
        assert(f->candidate.prepared_size == 17);
        destroy_fixture(f);
    }
}
static void candidate_invalid_inputs(void) {
    for (unsigned which = 0; which < 8; ++which) {
        fixture *f = new_fixture(1);
        if (which != 7) f->candidate.prepared_size = SIZE_MAX;
        pwp_result result = pwp_candidate_fill(which == 7 ? NULL : &f->candidate,
            which == 0 ? NULL : f->input, which == 1 ? (size_t)PWP_RECORD_LIMIT+1 : 1,
            which == 2 ? NULL : write_bytes, which == 3 ? NULL : flush_bytes,
            which == 4 ? NULL : rewind_bytes, which == 5 ? NULL : read_bytes,
            which == 6 ? NULL : verify_bytes, f);
        assert(result == PWP_ARGUMENT && f->calls == 0);
        assert(f->candidate.prepared_size == 0);
        if (which != 7) {
            assert(f->candidate.phase == PWP_CANDIDATE_FAILED);
            assert(fill(f) == PWP_CLOSED && f->calls == 0);
        } else assert(f->candidate.phase == PWP_CANDIDATE_OWNED);
        destroy_fixture(f);
    }
}
static void candidate_empty_and_order(void) {
    fixture *f = new_fixture(0);
    f->candidate.prepared_size = SIZE_MAX;
    assert(!f->input && fill(f) == PWP_OK && f->candidate.phase == PWP_CANDIDATE_VERIFIED);
    assert(f->candidate.prepared_size == 0);
    const unsigned expected[] = {VERIFY, FLUSH, VERIFY, REWIND, READ, VERIFY};
    assert(f->calls == sizeof(expected)/sizeof(expected[0]) && !memcmp(f->trace, expected, sizeof(expected)));
    assert(f->writes == 0 && f->reads == 1 && f->verifies == 3 && f->largest_read == 1);
    destroy_fixture(f);
}
static void candidate_size_boundaries(void) {
    const size_t sizes[] = {1, 4095, 4096, 4097, 65535, 65536, 65537, PWP_RECORD_LIMIT-1, PWP_RECORD_LIMIT};
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
        fixture *f = new_fixture(sizes[i]);
        f->candidate.prepared_size = SIZE_MAX;
        assert(fill(f) == PWP_OK && f->candidate.phase == PWP_CANDIDATE_VERIFIED);
        assert(f->candidate.prepared_size == sizes[i]);
        assert(f->size == f->count && !memcmp(f->input, f->stored, f->count));
        assert(f->writes == (f->count+65535)/65536 && f->reads == (f->count+4095)/4096+1);
        assert(f->largest_write <= 65536 && f->largest_read <= 4096 && f->verifies == 3);
        assert(f->verified_sizes[0] == 0 && f->verified_sizes[1] == f->count &&
            f->verified_sizes[2] == f->count);
        destroy_fixture(f);
    }
}
static void candidate_full_order_and_short_progress(void) {
    fixture *f = new_fixture(4097);
    assert(fill(f) == PWP_OK);
    assert(f->candidate.prepared_size == 4097);
    const unsigned expected[] = {VERIFY, WRITE, FLUSH, VERIFY, REWIND, READ, READ, READ, VERIFY};
    assert(f->calls == sizeof(expected)/sizeof(expected[0]) && !memcmp(f->trace, expected, sizeof(expected)));
    destroy_fixture(f);
    f = new_fixture(513); f->write_chunk = 31; f->read_chunk = 37;
    assert(fill(f) == PWP_OK && f->writes == 17 && f->reads == 15 && f->verifies == 3);
    assert(f->candidate.prepared_size == 513);
    assert(!memcmp(f->input, f->stored, f->count)); destroy_fixture(f);
    f = new_fixture(17); f->write_chunk = f->read_chunk = 1;
    assert(fill(f) == PWP_OK && f->writes == 17 && f->reads == 18);
    assert(f->candidate.prepared_size == 17); destroy_fixture(f);
}
static void candidate_write_failures(void) {
    for (unsigned call = 1; call <= 2; ++call) for (int partial = 0; partial <= 1; ++partial) {
        fixture *f = new_fixture(65537); f->fail_write = call; f->partial_error = partial;
        expect_failure(f, PWP_OS);
        assert(f->writes == call && f->verifies == 1 && !f->flushes && !f->reads);
        assert(f->size == (call == 2 ? 65536u : 0u) + (partial ? (call == 2 ? 1u : 3u) : 0u));
        destroy_fixture(f);
    }
}
static void candidate_invalid_write_progress(void) {
    for (int oversized = 0; oversized <= 1; ++oversized) {
        fixture *f = new_fixture(1);
        if (oversized) f->oversized_write = 1; else f->zero_write = 1;
        expect_failure(f, PWP_OS); assert(f->writes == 1 && !f->size && !f->flushes);
        destroy_fixture(f);
    }
}
static void candidate_flush_and_rewind_failures(void) {
    fixture *f = new_fixture(7); f->fail_flush = 1;
    expect_failure(f, PWP_OS); assert(f->flushes == 1 && f->verifies == 1 && !f->rewinds && !f->reads);
    destroy_fixture(f);
    f = new_fixture(7); f->fail_rewind = 1;
    expect_failure(f, PWP_OS); assert(f->flushes == 1 && f->verifies == 2 && f->rewinds == 1 && !f->reads);
    destroy_fixture(f);
}
static void candidate_initial_and_postflush_verification(void) {
    fixture *f = new_fixture(7); f->fail_verify = 1;
    expect_failure(f, PWP_POLICY); assert(f->calls == 1 && !f->writes && !f->flushes);
    destroy_fixture(f);
    f = new_fixture(7); f->fail_verify = 2;
    expect_failure(f, PWP_POLICY); assert(f->verifies == 2 && f->flushes == 1 && !f->rewinds && !f->reads);
    destroy_fixture(f);
}
static void candidate_read_failures(void) {
    for (unsigned call = 1; call <= 2; ++call) for (int partial = 0; partial <= 1; ++partial) {
        fixture *f = new_fixture(4097); f->fail_read = call; f->partial_error = partial;
        expect_failure(f, PWP_OS); assert(f->reads == call && f->verifies == 2);
        destroy_fixture(f);
    }
}
static void candidate_invalid_read_progress(void) {
    for (int oversized = 0; oversized <= 1; ++oversized) {
        fixture *f = new_fixture(7);
        if (oversized) f->oversized_read = 1; else f->zero_read = 1;
        expect_failure(f, PWP_OS); assert(f->reads == 1 && f->verifies == 2);
        destroy_fixture(f);
    }
}
static void candidate_wrong_readback_bytes(void) {
    for (unsigned call = 1; call <= 2; ++call) {
        fixture *f = new_fixture(4097); f->wrong_read = call;
        expect_failure(f, PWP_POLICY); assert(f->reads == call && f->verifies == 2);
        destroy_fixture(f);
    }
}
static void candidate_eof_failures(void) {
    const size_t sizes[] = {0, 7};
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) for (unsigned kind = 0; kind < 3; ++kind) {
        fixture *f = new_fixture(sizes[i]);
        if (kind == 0) f->extra_tail = 1;
        if (kind == 1) f->fail_eof = 1;
        if (kind == 2) f->oversized_eof = 1;
        expect_failure(f, kind == 0 ? PWP_POLICY : PWP_OS);
        assert(f->reads == (sizes[i] ? 2u : 1u) && f->verifies == 2);
        destroy_fixture(f);
    }
}
static void candidate_postread_verification_and_no_repeat(void) {
    fixture *f = new_fixture(7); f->fail_verify = 3;
    expect_failure(f, PWP_POLICY); assert(f->verifies == 3 && f->reads == 2);
    destroy_fixture(f);
    f = new_fixture(7); assert(fill(f) == PWP_OK);
    assert(f->candidate.prepared_size == 7);
    unsigned calls = f->calls;
    assert(fill(f) == PWP_CLOSED && pwp_candidate_init(&f->candidate) == PWP_CLOSED);
    assert(f->calls == calls && f->candidate.phase == PWP_CANDIDATE_VERIFIED && f->candidate.prepared_size == 7);
    destroy_fixture(f);
}
static void candidate_reentry_from_every_callback(void) {
    fixture *f = new_fixture(7); f->reenter = 1;
    assert(fill(f) == PWP_OK && f->candidate.phase == PWP_CANDIDATE_VERIFIED);
    assert(f->candidate.prepared_size == 7);
    assert(f->writes == 1 && f->flushes == 1 && f->rewinds == 1 && f->reads == 2 && f->verifies == 3);
    destroy_fixture(f);
}
int main(void) {
    candidate_names(); candidate_initialization_and_phases(); candidate_invalid_inputs(); candidate_empty_and_order();
    candidate_size_boundaries(); candidate_full_order_and_short_progress(); candidate_write_failures();
    candidate_invalid_write_progress(); candidate_flush_and_rewind_failures();
    candidate_initial_and_postflush_verification(); candidate_read_failures(); candidate_invalid_read_progress();
    candidate_wrong_readback_bytes(); candidate_eof_failures(); candidate_postread_verification_and_no_repeat();
    candidate_reentry_from_every_callback();
    puts("16 portable candidate-controller groups PASS; NOT Windows OS or durable-publication qualification");
    return 0;
}
