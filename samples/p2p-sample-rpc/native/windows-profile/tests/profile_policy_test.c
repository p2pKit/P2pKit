#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static size_t utf16(const char *s, uint16_t *out) {
    size_t n = strlen(s); for (size_t i = 0; i < n; ++i) out[i] = (unsigned char)s[i]; return n;
}
static void cleanup_result_precedence(void) {
    const pwp_result results[] = {PWP_OK, PWP_ARGUMENT, PWP_POLICY, PWP_OS, PWP_BUSY,
        PWP_CLOSED, PWP_LIMIT, PWP_NOT_FOUND, PWP_CLEANUP_UNKNOWN, PWP_UNIMPLEMENTED};
    /* Exercise the actual result selector used after native admission, not Windows error injection. */
    for (size_t i = 0; i < sizeof(results)/sizeof(results[0]); ++i) {
        assert(pwp_cleanup_result(results[i], 0, 0) == results[i]);
        assert(pwp_cleanup_result(results[i], 1, 0) == PWP_CLEANUP_UNKNOWN);
        assert(pwp_cleanup_result(results[i], 0, 1) == PWP_CLEANUP_UNKNOWN);
        assert(pwp_cleanup_result(results[i], 1, 1) == PWP_CLEANUP_UNKNOWN);
        assert(pwp_cleanup_result(results[i], -1, 0) == PWP_CLEANUP_UNKNOWN);
        assert(pwp_cleanup_result(results[i], 0, 2) == PWP_CLEANUP_UNKNOWN);
    }
    /* Unknown candidate codes retain their identity only when both cleanup flags are clear. */
    assert(pwp_cleanup_result((pwp_result)255, 0, 0) == (pwp_result)255);
    assert(pwp_cleanup_result((pwp_result)255, 1, 0) == PWP_CLEANUP_UNKNOWN);
    assert(pwp_cleanup_result((pwp_result)255, 0, 1) == PWP_CLEANUP_UNKNOWN);
}
static void component_policy(void) {
    const char *good[] = {"a", "A0", "identity.vault", "lock_file-42"};
    const char *bad[] = {"", ".", "..", "a.", "a ", "a/b", "a\\b", "a:b", "CON", "con.txt",
        "LPT9.lock", "COM1", "nul", "PRN", "AUX", "a?", "a\n"}; uint16_t out[100];
    for (size_t i = 0; i < sizeof(good)/sizeof(*good); ++i) assert(pwp_component(out, utf16(good[i], out)));
    for (size_t i = 0; i < sizeof(bad)/sizeof(*bad); ++i) assert(!pwp_component(out, utf16(bad[i], out)));
    for (size_t i = 0; i < 100; ++i) out[i] = 'a';
    assert(pwp_component(out, 96)); assert(!pwp_component(out, 97)); assert(!pwp_component(NULL, 1));
    out[0] = 0xd800; assert(!pwp_component(out, 1));
}
static void absolute_policy(void) {
    const char *good[] = {"C:\\Users\\Owner\\AppData\\Local", "D:\\A B\\C"};
    const char *bad[] = {"C:x", "C:\\", "\\\\server\\x", "\\\\?\\C:\\x", "C:/a", "C:\\a\\",
        "C:\\a\\..\\b", "C:\\a.", "C:\\a ", "C:\\a:stream", "C:\\CON", "C:\\a\\LPT1.log"};
    uint16_t out[200];
    for (size_t i = 0; i < sizeof(good)/sizeof(*good); ++i) assert(pwp_absolute_path(out, utf16(good[i], out)));
    for (size_t i = 0; i < sizeof(bad)/sizeof(*bad); ++i) assert(!pwp_absolute_path(out, utf16(bad[i], out)));
    size_t n = utf16("C:\\a", out); out[n++] = 0xd83d; out[n++] = 0xde00;
    assert(pwp_absolute_path(out, n)); assert(!pwp_absolute_path(out, n-1));
    out[n-2] = 0xde00; assert(!pwp_absolute_path(out, n));
}
static void final_path_policy(void) {
    uint16_t expected[100], actual[100]; size_t en = utf16("C:\\Users\\Owner", expected);
    size_t an = utf16("\\\\?\\c:\\users\\owner", actual); assert(pwp_final_path(expected, en, actual, an));
    an = utf16("\\\\?\\C:\\Users\\OTHER", actual); assert(!pwp_final_path(expected, en, actual, an));
    an = utf16("\\\\?\\UNC\\Users\\Owner", actual); assert(!pwp_final_path(expected, en, actual, an));
    assert(!pwp_final_path(expected, en, actual, 3));
}
static void directory_case_query_policy(void) {
    assert(pwp_directory_case_policy(1, 0));
    assert(!pwp_directory_case_policy(0, 0));
    assert(!pwp_directory_case_policy(-1, 0));
    assert(!pwp_directory_case_policy(2, 0));
    for (unsigned bit = 0; bit < 32; ++bit) {
        uint32_t flag = UINT32_C(1) << bit;
        assert(!pwp_directory_case_policy(1, flag));
        assert(!pwp_directory_case_policy(0, flag));
    }
    assert(!pwp_directory_case_policy(1, UINT32_MAX));
}
static void case_sensitive_directory_rejects_folded_alias(void) {
    uint16_t requested[100], held[100];
    size_t requested_length = utf16("C:\\Private\\ALPHA", requested);
    size_t held_length = utf16("\\\\?\\C:\\Private\\alpha", held);
    /* Existing ASCII folding is intentional only after every directory is admitted as insensitive.
     * This models the authorization order, not an executed NTFS file lookup. */
    int same_folded_name = pwp_final_path(requested, requested_length, held, held_length);
    assert(same_folded_name);
    assert(pwp_directory_case_policy(1, 0) && same_folded_name);
    assert(!(pwp_directory_case_policy(1, 1) && same_folded_name));
    assert(!(pwp_directory_case_policy(0, 0) && same_folded_name));
    assert(!(pwp_directory_case_policy(1, 2) && same_folded_name));
}
static void acl_policy(void) {
    uint8_t types[2] = {0,0}, flags[2] = {3,3}; uint32_t masks[2] = {0x1f01ff,0x1f01ff}; int sid[2] = {1,2};
    assert(pwp_acl_shape(0x1004, 1, 2, types, flags, masks, 1, sid, 1));
    assert(!pwp_acl_shape(4, 1, 2, types, flags, masks, 1, sid, 1));
    assert(!pwp_acl_shape(0x1004, 1, 3, types, flags, masks, 1, sid, 1));
    assert(!pwp_acl_shape(0x1004, 1, 2, types, flags, masks, 0, sid, 1));
    for (unsigned i = 0; i < 256; ++i) {
        flags[0] = (uint8_t)i;
        assert(pwp_acl_shape(0x1004, 1, 2, types, flags, masks, 1, sid, 1) == (i == 3));
    }
    flags[0] = 3; sid[1] = 1; assert(!pwp_acl_shape(0x1004, 1, 2, types, flags, masks, 1, sid, 1));
    sid[1] = 3; assert(!pwp_acl_shape(0x1004, 1, 2, types, flags, masks, 1, sid, 1));
    sid[1] = 2; masks[0] = 0xffffffff; assert(!pwp_acl_shape(0x1004, 1, 2, types, flags, masks, 1, sid, 1));
    masks[0] = 0x1f01ff; flags[0] = flags[1] = 0;
    assert(pwp_acl_shape(0x1004, 1, 2, types, flags, masks, 1, sid, 0));
}
static void streams_policy(void) {
    unsigned char raw[64] = {0}; raw[4] = 14; raw[8] = 5; raw[16] = 16;
    const unsigned char name[] = {':',0,':',0,'$',0,'D',0,'A',0,'T',0,'A',0}; memcpy(raw+24, name, sizeof(name));
    assert(pwp_stream_record(raw, sizeof(raw), 5, 0));
    for (size_t n = 0; n < 38; ++n) assert(!pwp_stream_record(raw, n, 5, 0));
    raw[0] = 40; assert(!pwp_stream_record(raw, sizeof(raw), 5, 0)); raw[0] = 0;
    raw[26] = 's'; assert(!pwp_stream_record(raw, sizeof(raw), 5, 0)); raw[26] = ':';
    assert(!pwp_stream_record(raw, sizeof(raw), 6, 0)); assert(!pwp_stream_record(raw, sizeof(raw), 5, 1));
    assert(pwp_stream_record(NULL, 0, 0, 1)); assert(!pwp_stream_record(NULL, 0, 0, 0));
}
static void directory_index_size_policy(void) {
    const uint64_t sizes[] = {0, 4096, 32768, (uint64_t)PWP_RECORD_LIMIT+1, INT64_MAX};
    unsigned char raw[64] = {0}; raw[4] = 14;
    const unsigned char name[] = {':',0,':',0,'$',0,'D',0,'A',0,'T',0,'A',0};
    memcpy(raw+24, name, sizeof(name));
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
        /* NTFS index growth changes directory EOF without adding a data stream. */
        assert(pwp_stream_record(NULL, 0, sizes[i], 1));
        assert(!pwp_stream_record(NULL, 1, sizes[i], 1));
        assert(!pwp_stream_record(NULL, 0, sizes[i], 0));
        /* A reported unnamed directory data stream must still be empty. */
        assert(pwp_stream_record(raw, sizeof(raw), sizes[i], 1));
        assert(pwp_stream_record(raw, sizeof(raw), sizes[i], 0) == (sizes[i] == 0));
        for (size_t n = 0; n < 38; ++n) assert(!pwp_stream_record(raw, n, sizes[i], 1));
    }
    assert(!pwp_stream_record(NULL, 0, (uint64_t)INT64_MAX+1, 1));
    assert(!pwp_stream_record(NULL, 0, UINT64_MAX, 1));
    assert(!pwp_stream_record(raw, sizeof(raw), (uint64_t)INT64_MAX+1, 1));
    assert(!pwp_stream_record(raw, sizeof(raw), UINT64_MAX, 1));
}
static void directory_streams_refuse_payload_or_aliases(void) {
    unsigned char raw[64] = {0}; raw[4] = 14;
    const unsigned char name[] = {':',0,':',0,'$',0,'D',0,'A',0,'T',0,'A',0};
    memcpy(raw+24, name, sizeof(name));
    raw[8] = 1; assert(!pwp_stream_record(raw, sizeof(raw), 4096, 1)); raw[8] = 0;
    raw[9] = 16; /* Matching a 4096-byte index does not authorize directory data. */
    assert(!pwp_stream_record(raw, sizeof(raw), 4096, 1));
    assert(pwp_stream_record(raw, sizeof(raw), 4096, 0)); raw[9] = 0;
    raw[15] = 0x80; assert(!pwp_stream_record(raw, sizeof(raw), 4096, 1)); raw[15] = 0;
    raw[23] = 0x80; assert(!pwp_stream_record(raw, sizeof(raw), 4096, 1)); raw[23] = 0;
    raw[0] = 40; assert(!pwp_stream_record(raw, sizeof(raw), 4096, 1)); raw[0] = 0;
    raw[26] = 's'; assert(!pwp_stream_record(raw, sizeof(raw), 4096, 1)); raw[26] = ':';
    raw[4] = 12; assert(!pwp_stream_record(raw, sizeof(raw), 4096, 1)); raw[4] = 14;
    assert(pwp_stream_record(raw, sizeof(raw), 4096, 1));
}
typedef struct { unsigned calls; uintptr_t fail; uintptr_t order[128]; } close_context;
static int close_count(uintptr_t raw, void *opaque) {
    close_context *c = opaque; c->order[c->calls++] = raw; return raw != c->fail;
}
static void exact_close(void) {
    pwp_owner owner; pwp_owner_init(&owner); close_context c = {0}; uint64_t token = 0;
    assert(pwp_reserve(&owner, &token) == PWP_OK); assert(token > 0);
    assert(pwp_attach(&owner, token, 7) == PWP_OK);
    assert(pwp_attach(&owner, token, 8) == PWP_ARGUMENT);
    assert(pwp_retire(&owner, token, close_count, &c) == PWP_OK);
    assert(pwp_retire(&owner, token, close_count, &c) == PWP_OK); assert(c.calls == 1);
    uint64_t later; assert(pwp_reserve(&owner, &later) == PWP_OK); assert(later > token);
    assert(!pwp_lookup(&owner, token)); assert(pwp_retire(&owner, later, close_count, &c) == PWP_OK);
    assert(c.calls == 1); /* Inert pre-allocation ownership requires no physical close. */
}
static void failed_close(void) {
    pwp_owner owner; pwp_owner_init(&owner); close_context c = {.fail=1}; uint64_t a, b, later;
    assert(pwp_reserve(&owner, &a) == PWP_OK); assert(pwp_attach(&owner, a, 1) == PWP_OK);
    assert(pwp_reserve(&owner, &b) == PWP_OK); assert(pwp_attach(&owner, b, 2) == PWP_OK);
    assert(pwp_retire(&owner, a, close_count, &c) == PWP_CLEANUP_UNKNOWN);
    assert(pwp_lookup(&owner, a)->resource == 1); assert(pwp_reserve(&owner, &later) == PWP_CLEANUP_UNKNOWN);
    assert(pwp_retire_all(&owner, close_count, &c) == PWP_CLEANUP_UNKNOWN);
    assert(c.calls == 2 && c.order[1] == 2);
    assert(pwp_retire_all(&owner, close_count, &c) == PWP_CLEANUP_UNKNOWN); assert(c.calls == 2);
}
static void bounds_and_reverse_order(void) {
    pwp_owner owner; pwp_owner_init(&owner); close_context c = {0}; uint64_t token;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        assert(pwp_reserve(&owner, &token) == PWP_OK); assert(pwp_attach(&owner, token, i+1) == PWP_OK);
    }
    assert(pwp_reserve(&owner, &token) == PWP_LIMIT);
    assert(pwp_retire_all(&owner, close_count, &c) == PWP_OK); assert(c.calls == PWP_HANDLE_LIMIT);
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) assert(c.order[i] == PWP_HANDLE_LIMIT-i);
    owner.next = (uint64_t)INT64_MAX+1; assert(pwp_reserve(&owner, &token) == PWP_LIMIT);
}
static void public_bound_and_inert_retirement(void) {
    pwp_owner owner; pwp_owner_init(&owner); close_context c = {0}; uint64_t first = 0, last = 0;
    for (size_t i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i) {
        uint64_t token;
        assert(pwp_reserve(&owner, &token) == PWP_OK);
        assert(pwp_attach(&owner, token, i+1) == PWP_OK);
        assert(pwp_publish(&owner, token) == PWP_OK);
        if (!first) first = token;
    }
    assert(pwp_public_count(&owner) == PWP_PUBLIC_HANDLE_LIMIT);
    assert(pwp_reserve(&owner, &last) == PWP_OK);
    assert(pwp_attach(&owner, last, 99) == PWP_OK);
    assert(pwp_publish(&owner, last) == PWP_LIMIT);
    assert(pwp_retire(&owner, last, close_count, &c) == PWP_OK);
    assert(pwp_retire(&owner, first, close_count, &c) == PWP_OK);
    assert(pwp_public_count(&owner) == PWP_PUBLIC_HANDLE_LIMIT-1);
    assert(pwp_reserve(&owner, &last) == PWP_OK);
    assert(pwp_retire(&owner, last, close_count, &c) == PWP_OK);
    assert(c.calls == 2); /* Reserved native-open failure has no raw handle and leaks no capacity. */
    assert(pwp_retire_all(&owner, close_count, &c) == PWP_OK);
    assert(pwp_public_count(&owner) == 0);
}
static void raw_token_and_append_bounds(void) {
    assert(!pwp_token_valid(0)); assert(!pwp_token_valid(UINT64_MAX));
    assert(pwp_token_valid(1)); assert(pwp_token_valid(INT64_MAX));
    uint16_t path[20] = {0}, name[16] = {0}; size_t n = utf16("RpcProfile", name);
    (void)utf16("C:\\a", path); path[4] = 0; path[19] = 0xbeef;
    uint16_t original[20]; memcpy(original, path, sizeof(path));
    assert(!pwp_append_path(path, 15, name, n)); assert(memcmp(original, path, sizeof(path)) == 0);
    assert(pwp_append_path(path, 16, name, n)); assert(path[15] == 0 && path[19] == 0xbeef);
    for (size_t i = 0; i < 20; ++i) path[i] = 'a';
    memcpy(original, path, sizeof(path));
    assert(!pwp_append_path(path, 20, name, n)); assert(memcmp(original, path, sizeof(path)) == 0);
}
static void put32(unsigned char *bytes, size_t offset, uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) bytes[offset+i] = (unsigned char)(value >> (i*8));
}
static void directory_row(unsigned char *bytes, size_t capacity, const char *name, uint32_t next) {
    memset(bytes, 0, capacity); size_t n = strlen(name); assert(104+n*2 <= capacity);
    put32(bytes, 0, next); put32(bytes, 60, (uint32_t)(n*2));
    for (size_t i = 0; i < n; ++i) bytes[104+i*2] = (unsigned char)name[i];
}
static void directory_valid_records(void) {
    unsigned char raw[512]; pwp_directory_names *names = calloc(1, sizeof(*names)); assert(names);
    directory_row(raw, sizeof(raw), "alpha", 120);
    directory_row(raw+120, sizeof(raw)-120, "beta", 0);
    raw[68] = 6; raw[70] = 'C'; raw[72] = 'O'; raw[74] = 'N'; /* Short alias is never an output name. */
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_OK);
    assert(names->count == 2 && names->lengths[0] == 5 && names->names[0][0] == 'a');
    memset(names, 0, sizeof(*names)); directory_row(raw, sizeof(raw), ".", 112);
    directory_row(raw+112, sizeof(raw)-112, "..", 0);
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_OK && names->count == 0);
    free(names);
}
static void directory_offsets_and_truncation(void) {
    unsigned char raw[512]; pwp_directory_names *names = calloc(1, sizeof(*names)); assert(names);
    for (size_t size = 0; size < 114; ++size) {
        directory_row(raw, sizeof(raw), "alpha", 0);
        assert(pwp_directory_decode(raw, size, names) == PWP_POLICY && names->count == 0);
    }
    uint32_t offsets[] = {1, 104, 112, 119, 121, 512, UINT32_MAX};
    for (size_t i = 0; i < sizeof(offsets)/sizeof(*offsets); ++i) {
        directory_row(raw, sizeof(raw), "alpha", offsets[i]);
        assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY && names->count == 0);
    }
    directory_row(raw, sizeof(raw), "alpha", 256);
    directory_row(raw+256, sizeof(raw)-256, "beta", 0);
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_OK && names->count == 2);
    memset(names, 0, sizeof(*names)); raw[120] = 1;
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY && names->count == 0);
    directory_row(raw, sizeof(raw), "alpha", 0); raw[120] = 1;
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY); /* Hidden trailing record/data. */
    directory_row(raw, sizeof(raw), "alpha", 0); raw[114] = 0xff;
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_OK); /* At most final alignment padding. */
    memset(names, 0, sizeof(*names));
    assert(pwp_directory_decode(raw, PWP_DIRECTORY_BUFFER_LIMIT+1, names) == PWP_POLICY);
    free(names);
}
static void directory_names_and_metadata_policy(void) {
    unsigned char raw[512]; pwp_directory_names *names = calloc(1, sizeof(*names)); assert(names);
    const char *invalid[] = {"CON.txt", "a:b", "a/b", "a.", "bad name"};
    for (size_t i = 0; i < sizeof(invalid)/sizeof(*invalid); ++i) {
        directory_row(raw, sizeof(raw), invalid[i], 0);
        assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY && names->count == 0);
    }
    char longest[PWP_COMPONENT_LIMIT+1]; memset(longest, 'a', PWP_COMPONENT_LIMIT); longest[PWP_COMPONENT_LIMIT] = 0;
    directory_row(raw, sizeof(raw), longest, 0);
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_OK && names->lengths[0] == PWP_COMPONENT_LIMIT);
    memset(names, 0, sizeof(*names));
    uint32_t lengths[] = {0, 1, 193, 194, UINT32_MAX};
    for (size_t i = 0; i < sizeof(lengths)/sizeof(*lengths); ++i) {
        directory_row(raw, sizeof(raw), "alpha", 0); put32(raw, 60, lengths[i]);
        assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY);
    }
    directory_row(raw, sizeof(raw), "a", 0); raw[104] = 0; raw[105] = 0xd8;
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY);
    uint32_t flags[] = {0x400, 0x1000};
    for (size_t i = 0; i < 2; ++i) {
        directory_row(raw, sizeof(raw), "a", 0); put32(raw, 56, flags[i]);
        assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY);
    }
    directory_row(raw, sizeof(raw), "a", 0); put32(raw, 40, PWP_RECORD_LIMIT+1);
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY);
    directory_row(raw, sizeof(raw), "a", 0); raw[55] = 0x80;
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY);
    free(names);
}
static void directory_aggregate_limits_and_aliases(void) {
    unsigned char raw[512]; pwp_directory_names *names = calloc(1, sizeof(*names)); assert(names);
    directory_row(raw, sizeof(raw), "alpha", 0);
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_OK);
    directory_row(raw, sizeof(raw), "ALPHA", 0);
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY && names->count == 0);
    directory_row(raw, sizeof(raw), "alpha", 120);
    directory_row(raw+120, sizeof(raw)-120, "alpha", 0);
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY && names->count == 0);
    for (unsigned i = 0; i < PWP_DIRECTORY_LIMIT; ++i) {
        char name[16]; (void)snprintf(name, sizeof(name), "file%04u", i);
        directory_row(raw, sizeof(raw), name, 0);
        assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_OK && names->count == i+1);
    }
    directory_row(raw, sizeof(raw), "overflow", 0);
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_LIMIT && names->count == 0);
    names->count = PWP_DIRECTORY_LIMIT+1;
    assert(pwp_directory_decode(raw, sizeof(raw), names) == PWP_POLICY && names->count == 0);
    free(names);
}
static void clear_bytes(void) {
    unsigned char bytes[32]; memset(bytes, 0xfe, sizeof(bytes)); pwp_clear(bytes, sizeof(bytes));
    for (size_t i = 0; i < sizeof(bytes); ++i) assert(bytes[i] == 0);
}
int main(void) {
    cleanup_result_precedence();
    component_policy(); absolute_policy(); final_path_policy(); acl_policy(); streams_policy();
    directory_index_size_policy(); directory_streams_refuse_payload_or_aliases();
    directory_case_query_policy(); case_sensitive_directory_rejects_folded_alias();
    exact_close(); failed_close(); bounds_and_reverse_order(); public_bound_and_inert_retirement(); raw_token_and_append_bounds(); directory_valid_records(); directory_offsets_and_truncation();
    directory_names_and_metadata_policy(); directory_aggregate_limits_and_aliases(); clear_bytes();
    puts("20 portable C policy/ownership groups PASS; NOT Windows OS qualification"); return 0;
}
