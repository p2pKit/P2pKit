#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void refuse(const unsigned char *bytes, size_t capacity, size_t returned, size_t header,
                   uintptr_t address) {
    size_t offset = 99, length = 99;
    assert(!pwp_token_sid_view(bytes, capacity, returned, header, address, &offset, &length));
    assert(offset == 0 && length == 0);
}
static void valid_sid_sizes(void) {
    _Alignas(8) unsigned char bytes[128] = {0};
    for (size_t header = 8; header <= 16; header += 8) {
        bytes[header] = 1;
        for (unsigned count = 0; count <= 15; ++count) {
            bytes[header+1] = (unsigned char)count;
            size_t size = 8+4*count, offset = 0, length = 0;
            assert(pwp_token_sid_view(bytes, sizeof(bytes), header+size, header,
                                     (uintptr_t)(bytes+header), &offset, &length));
            assert(offset == header && length == size);
            /* Extra returned padding is allowed, but never expands the SID itself. */
            assert(pwp_token_sid_view(bytes, sizeof(bytes), sizeof(bytes), header,
                                     (uintptr_t)(bytes+header), &offset, &length));
            assert(offset == header && length == size);
        }
    }
    /* Returned token data may place its SID after padding beyond the fixed SDK header. */
    memset(bytes, 0, sizeof(bytes)); bytes[24] = 1; bytes[25] = 2;
    size_t offset = 0, length = 0;
    assert(pwp_token_sid_view(bytes, sizeof(bytes), 40, 16, (uintptr_t)(bytes+24), &offset, &length));
    assert(offset == 24 && length == 16);
}
static void query_bounds(void) {
    _Alignas(8) unsigned char bytes[32] = {0}; bytes[16] = 1; bytes[17] = 2;
    uintptr_t sid = (uintptr_t)(bytes+16);
    for (size_t n = 0; n < sizeof(bytes); ++n) refuse(bytes, sizeof(bytes), n, 16, sid);
    refuse(bytes, sizeof(bytes), sizeof(bytes)+1, 16, sid);
    refuse(bytes, 0, 0, 16, sid);
    refuse(bytes, PWP_TOKEN_BUFFER_LIMIT+1, sizeof(bytes), 16, sid);
    refuse(bytes, SIZE_MAX, SIZE_MAX, 16, sid);
    refuse(bytes, sizeof(bytes), SIZE_MAX, 16, sid);
    refuse(bytes, sizeof(bytes), sizeof(bytes), 0, sid);
    refuse(bytes, sizeof(bytes), sizeof(bytes), SIZE_MAX, sid);
    refuse(NULL, sizeof(bytes), sizeof(bytes), 16, sid);
}
static void foreign_and_unaligned_pointers(void) {
    _Alignas(8) unsigned char bytes[64] = {0}; bytes[16] = 1;
    uintptr_t base = (uintptr_t)bytes;
    refuse(bytes, sizeof(bytes), sizeof(bytes), 16, 0);
    refuse(bytes, sizeof(bytes), sizeof(bytes), 16, base-1);
    refuse(bytes, sizeof(bytes), sizeof(bytes), 16, UINTPTR_MAX);
    for (size_t n = 0; n < 16; ++n) refuse(bytes, sizeof(bytes), sizeof(bytes), 16, base+n);
    for (size_t n = sizeof(bytes)-7; n <= sizeof(bytes)+8; ++n)
        refuse(bytes, sizeof(bytes), sizeof(bytes), 16, base+n);
    for (size_t n = 1; n < 4; ++n) {
        bytes[16+n] = 1;
        refuse(bytes, sizeof(bytes), sizeof(bytes), 16, base+16+n);
        bytes[16+n] = 0;
    }
}
static void malformed_sid_header(void) {
    _Alignas(8) unsigned char bytes[32] = {0};
    uintptr_t address = (uintptr_t)(bytes+16);
    for (unsigned revision = 0; revision < 256; ++revision) {
        if (revision == 1) continue;
        bytes[16] = (unsigned char)revision;
        refuse(bytes, sizeof(bytes), sizeof(bytes), 16, address);
    }
    bytes[16] = 1;
    for (unsigned count = 3; count < 256; ++count) {
        bytes[17] = (unsigned char)count;
        refuse(bytes, sizeof(bytes), sizeof(bytes), 16, address);
    }
}
static void no_read_outside_returned_view(void) {
    /* Exact allocation makes ASan exercise end-of-buffer reads, not merely padded storage. */
    _Alignas(8) unsigned char bytes[24] = {0}; bytes[16] = 1; bytes[17] = 1;
    refuse(bytes, sizeof(bytes), sizeof(bytes), 16, (uintptr_t)(bytes+16));
    refuse(bytes, sizeof(bytes), sizeof(bytes), 16, (uintptr_t)(bytes+20));
    refuse(bytes, sizeof(bytes), sizeof(bytes), 16, (uintptr_t)(bytes+24));
}
static void invalid_outputs(void) {
    _Alignas(8) unsigned char bytes[32] = {0}; bytes[16] = 1;
    size_t out = 99;
    assert(!pwp_token_sid_view(bytes, sizeof(bytes), sizeof(bytes), 16,
                              (uintptr_t)(bytes+16), NULL, &out));
    assert(out == 0); out = 99;
    assert(!pwp_token_sid_view(bytes, sizeof(bytes), sizeof(bytes), 16,
                              (uintptr_t)(bytes+16), &out, NULL));
    assert(out == 0);
}
int main(void) {
    valid_sid_sizes(); query_bounds(); foreign_and_unaligned_pointers(); malformed_sid_header();
    no_read_outside_returned_view(); invalid_outputs();
    puts("6 token SID view regression groups passed (portable bytes, not Windows token execution)");
    return 0;
}
