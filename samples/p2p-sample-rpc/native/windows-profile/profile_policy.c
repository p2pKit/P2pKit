#include "profile_policy.h"
#include <string.h>
#include <stdlib.h>

int pwp_token_valid(uint64_t token) { return token > 0 && token <= INT64_MAX; }

static uint16_t lower(uint16_t c) { return c >= 'A' && c <= 'Z' ? (uint16_t)(c + 32) : c; }
static int letter(uint16_t c) { return lower(c) >= 'a' && lower(c) <= 'z'; }
static int digit(uint16_t c) { return c >= '0' && c <= '9'; }
static int word(const uint16_t *s, size_t n, const char *value) {
    if (n != strlen(value)) return 0;
    for (size_t i = 0; i < n; ++i) if (lower(s[i]) != (uint16_t)value[i]) return 0;
    return 1;
}
int pwp_component(const uint16_t *s, size_t n) {
    if (!s || n == 0 || n > PWP_COMPONENT_LIMIT || (!letter(s[0]) && !digit(s[0])) || s[n-1] == '.') return 0;
    size_t stem = n;
    for (size_t i = 0; i < n; ++i) {
        if (!letter(s[i]) && !digit(s[i]) && s[i] != '.' && s[i] != '_' && s[i] != '-') return 0;
        if (s[i] == '.' && stem == n) stem = i;
    }
    if (word(s, stem, "con") || word(s, stem, "prn") || word(s, stem, "aux") || word(s, stem, "nul")) return 0;
    if (stem == 4 && s[3] >= '1' && s[3] <= '9' &&
        (word(s, 3, "com") || word(s, 3, "lpt"))) return 0;
    return 1;
}
int pwp_append_path(uint16_t *path, size_t capacity, const uint16_t *name, size_t length) {
    if (!path || capacity == 0 || capacity > PWP_PATH_LIMIT || !pwp_component(name, length)) return 0;
    size_t used = 0;
    while (used < capacity && path[used]) ++used;
    if (used == 0 || used == capacity || capacity-used < length+2) return 0;
    /* Check all bounds before the first write; no secure-CRT invalid-parameter termination path. */
    path[used++] = '\\';
    memcpy(path+used, name, length*sizeof(uint16_t)); path[used+length] = 0;
    return 1;
}
/* KnownFolder ancestors may contain spaces/Unicode, unlike profile-relative names. */
int pwp_absolute_path(const uint16_t *s, size_t n) {
    if (!s || n < 4 || n >= PWP_PATH_LIMIT - 32 || !letter(s[0]) || s[1] != ':' || s[2] != '\\') return 0;
    size_t start = 3, depth = 0;
    for (size_t i = 3; i <= n; ++i) {
        if (i == n || s[i] == '\\') {
            if (i == start || ++depth > 60 || s[i-1] == ' ' || s[i-1] == '.' || i - start > 255) return 0;
            if ((i - start == 1 && s[start] == '.') ||
                (i - start == 2 && s[start] == '.' && s[start+1] == '.')) return 0;
            size_t stem = start;
            while (stem < i && s[stem] != '.') ++stem;
            if (word(s+start, stem-start, "con") || word(s+start, stem-start, "prn") ||
                word(s+start, stem-start, "aux") || word(s+start, stem-start, "nul") ||
                word(s+start, stem-start, "conin$") || word(s+start, stem-start, "conout$") ||
                word(s+start, stem-start, "clock$")) return 0;
            if (stem-start == 4 && (word(s+start, 3, "com") || word(s+start, 3, "lpt")) &&
                ((s[start+3] >= '1' && s[start+3] <= '9') || s[start+3] == 0xb9 ||
                  s[start+3] == 0xb2 || s[start+3] == 0xb3)) return 0;
            start = i+1;
        } else {
            uint16_t c = s[i];
            if (c < 32 || c == 127 || c == ':' || c == '/' || c == '<' || c == '>' ||
                c == '"' || c == '|' || c == '?' || c == '*') return 0;
            if (c >= 0xd800 && c <= 0xdbff) {
                if (i+1 >= n || s[i+1] < 0xdc00 || s[i+1] > 0xdfff) return 0;
                ++i;
            } else if (c >= 0xdc00 && c <= 0xdfff) return 0;
        }
    }
    return 1;
}
int pwp_final_path(const uint16_t *expected, size_t en, const uint16_t *actual, size_t an) {
    if (!expected || !actual || en > PWP_PATH_LIMIT - 4 || an != en+4 ||
        actual[0] != '\\' || actual[1] != '\\' || actual[2] != '?' || actual[3] != '\\') return 0;
    for (size_t i = 0; i < en; ++i) if (lower(expected[i]) != lower(actual[i+4])) return 0;
    return 1;
}
int pwp_directory_case_policy(int query_succeeded, uint32_t flags) {
    return query_succeeded == 1 && flags == 0;
}
static uint32_t u32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static uint64_t u64(const unsigned char *p) { return u32(p) | (uint64_t)u32(p+4)<<32; }
pwp_result pwp_directory_decode(const unsigned char *bytes, size_t length, pwp_directory_names *names) {
    if (!names) return PWP_ARGUMENT;
    pwp_result result = PWP_POLICY;
    if (!bytes || length < 104 || length > PWP_DIRECTORY_BUFFER_LIMIT || names->count > PWP_DIRECTORY_LIMIT)
        goto failed;
    size_t position = 0, records = 0;
    for (;;) {
        if (length-position < 104 || ++records > PWP_DIRECTORY_LIMIT+2) goto failed;
        const unsigned char *row = bytes+position;
        uint32_t next = u32(row), name_bytes = u32(row+60), attributes = u32(row+56);
        uint64_t size = u64(row+40), allocation = u64(row+48);
        if (!name_bytes || name_bytes > PWP_COMPONENT_LIMIT*2 || name_bytes % 2 ||
            name_bytes > length-position-104 || size > INT64_MAX || allocation > INT64_MAX ||
            (attributes & (0x400u | 0x1000u)) || (!(attributes & 0x10u) && size > PWP_RECORD_LIMIT)) goto failed;
        uint16_t name[PWP_COMPONENT_LIMIT+1] = {0};
        size_t count = name_bytes/2;
        for (size_t i = 0; i < count; ++i) name[i] = (uint16_t)(row[104+i*2] | (uint16_t)row[105+i*2]<<8);
        int dot = count == 1 && name[0] == '.';
        int dots = count == 2 && name[0] == '.' && name[1] == '.';
        if (!dot && !dots) {
            if (!pwp_component(name, count)) goto failed;
            if (names->count == PWP_DIRECTORY_LIMIT) { result = PWP_LIMIT; goto failed; }
            for (size_t i = 0; i < names->count; ++i) {
                if (names->lengths[i] != count) continue;
                size_t j = 0;
                while (j < count && lower(names->names[i][j]) == lower(name[j])) ++j;
                if (j == count) goto failed;
            }
            names->lengths[names->count] = (uint16_t)count;
            memcpy(names->names[names->count], name, (count+1)*sizeof(uint16_t)); ++names->count;
        }
        if (!next) {
            /* Caller zeroes the bounded OS buffer. At most seven final alignment bytes are padding. */
            size_t tail = position + ((104+name_bytes+7u)/8u)*8u;
            for (size_t i = tail; i < length; ++i) if (bytes[i] != 0) goto failed;
            return PWP_OK;
        }
        if (next % 8 || next < 104+name_bytes || next >= length-position) goto failed;
        size_t after_record = ((104+name_bytes+7u)/8u)*8u;
        for (size_t i = after_record; i < next; ++i) if (row[i] != 0) goto failed;
        position += next;
    }
failed:
    pwp_clear(names, sizeof(*names));
    return result;
}
int pwp_stream_record(const unsigned char *p, size_t n, uint64_t size, int directory) {
    static const unsigned char name[] = {':',0,':',0,'$',0,'D',0,'A',0,'T',0,'A',0};
    if (!p) return n == 0 && directory && size == 0;
    if (n < 24+sizeof(name) || u32(p) != 0 || u32(p+4) != sizeof(name) ||
        u64(p+8) != size || u64(p+16) > INT64_MAX || (directory && size != 0)) return 0;
    return memcmp(p+24, name, sizeof(name)) == 0;
}
int pwp_acl_shape(uint16_t control, uint32_t revision, uint32_t count,
                  const uint8_t types[2], const uint8_t flags[2], const uint32_t masks[2],
                  int user, const int sid[2], int directory) {
    if (!types || !flags || !masks || !sid || !user || revision != 1 || count != 2 ||
        (control & 0x1004u) != 0x1004u) return 0;
    for (size_t i = 0; i < 2; ++i) {
        if (types[i] != 0 || flags[i] != (directory ? 3 : 0) || masks[i] != 0x001f01ffu) return 0;
    }
    return (sid[0] == 1 && sid[1] == 2) || (sid[0] == 2 && sid[1] == 1);
}
void pwp_clear(void *p, size_t n) { volatile unsigned char *b = p; while (n--) *b++ = 0; }
pwp_result pwp_buffer_apply(size_t count, pwp_buffer_action action, void *context) {
    if (count > PWP_RECORD_LIMIT || !action) return PWP_ARGUMENT;
    unsigned char *bytes = count ? calloc(count, 1) : NULL;
    if (count && !bytes) return PWP_LIMIT;
    pwp_result result = action(bytes, count, context);
    pwp_clear(bytes, count); free(bytes);
    return result;
}
void pwp_owner_init(pwp_owner *o) { memset(o, 0, sizeof(*o)); o->next = 1; }
pwp_owned_handle *pwp_lookup(pwp_owner *o, uint64_t token) {
    if (!o || !pwp_token_valid(token)) return NULL;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) if (o->slots[i].token == token) return &o->slots[i];
    return NULL;
}
pwp_result pwp_reserve(pwp_owner *o, uint64_t *token) {
    if (!o || !token) return PWP_ARGUMENT;
    if (o->poisoned) return PWP_CLEANUP_UNKNOWN;
    if (!o->next || o->next > INT64_MAX) return PWP_LIMIT;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) if ((o->slots[i].state == 0 || o->slots[i].state == 3)) {
        o->slots[i].token = o->next++; o->slots[i].state = 1; o->slots[i].published = 0; *token = o->slots[i].token; return PWP_OK;
    }
    return PWP_LIMIT;
}
size_t pwp_public_count(const pwp_owner *o) {
    size_t count = 0;
    if (!o) return PWP_PUBLIC_HANDLE_LIMIT;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i)
        if (o->slots[i].published && o->slots[i].state != 3) ++count;
    return count;
}
pwp_result pwp_publish(pwp_owner *o, uint64_t token) {
    pwp_owned_handle *h = pwp_lookup(o, token);
    if (!h || h->state != 2 || h->published) return PWP_ARGUMENT;
    if (o->poisoned) return PWP_CLEANUP_UNKNOWN;
    if (pwp_public_count(o) >= PWP_PUBLIC_HANDLE_LIMIT) return PWP_LIMIT;
    h->published = 1;
    return PWP_OK;
}
pwp_result pwp_attach(pwp_owner *o, uint64_t token, uintptr_t resource) {
    pwp_owned_handle *h = pwp_lookup(o, token);
    if (!h || h->state != 1 || !resource) return PWP_ARGUMENT;
    h->resource = resource; h->state = 2; return PWP_OK;
}
pwp_result pwp_retire(pwp_owner *o, uint64_t token, pwp_close_callback close, void *context) {
    pwp_owned_handle *h = pwp_lookup(o, token);
    if (!h || !close) return PWP_ARGUMENT;
    if (h->state == 4) return PWP_CLEANUP_UNKNOWN;
    if (h->state == 3) return PWP_OK;
    if (h->state != 1 && h->state != 2) return PWP_CLOSED;
    h->state = 4; /* In-flight and failed close are never re-entered or retried. */
    if (h->resource && !close(h->resource, context)) { o->poisoned = 1; return PWP_CLEANUP_UNKNOWN; }
    h->resource = 0; h->state = 3; return PWP_OK;
}
pwp_result pwp_retire_all(pwp_owner *o, pwp_close_callback close, void *context) {
    if (!o || !close) return PWP_ARGUMENT;
    pwp_result result = PWP_OK;
    uint64_t before = UINT64_MAX;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        uint64_t next = 0;
        for (size_t j = 0; j < PWP_HANDLE_LIMIT; ++j)
            if (o->slots[j].state && o->slots[j].token < before && o->slots[j].token > next)
                next = o->slots[j].token;
        if (!next) break;
        pwp_result r = pwp_retire(o, next, close, context);
        if (result == PWP_OK && r != PWP_OK) result = r;
        before = next;
    }
    return result;
}

int pwp_stage_name(const uint16_t *name, size_t length) {
    static const char prefix[] = "pwp-stage-";
    if (!name || length != sizeof(prefix)-1+32) return 0;
    for (size_t i = 0; i < sizeof(prefix)-1; ++i) if (name[i] != (uint16_t)prefix[i]) return 0;
    for (size_t i = sizeof(prefix)-1; i < length; ++i)
        if (!digit(name[i]) && !(name[i] >= 'a' && name[i] <= 'f')) return 0;
    return 1;
}
int pwp_regular_metadata(pwp_stage_phase phase) { return phase == PWP_STAGE_EMPTY; }
pwp_result pwp_stage_init(pwp_stage *stage) {
    if (!stage) return PWP_ARGUMENT;
    if (stage->phase != PWP_STAGE_EMPTY) return PWP_CLOSED;
    stage->phase = PWP_STAGE_OWNED; return PWP_OK;
}
pwp_result pwp_stage_fill(pwp_stage *stage, const unsigned char *bytes, size_t length,
                         pwp_stage_write write, pwp_stage_action flush, pwp_stage_verify verify, void *context) {
    if (!stage || (!bytes && length) || length > PWP_RECORD_LIMIT || !write || !flush || !verify)
        return PWP_ARGUMENT;
    if (stage->phase != PWP_STAGE_OWNED) return PWP_CLOSED;
    stage->phase = PWP_STAGE_FILLING;
    pwp_result result = PWP_POLICY;
    if (!verify(0, context)) goto failed;
    size_t offset = 0;
    while (offset < length) {
        size_t count = length-offset, actual = 0;
        if (count > 65536) count = 65536;
        if (!write(bytes+offset, count, &actual, context) || !actual || actual > count) {
            result = PWP_OS; goto failed;
        }
        offset += actual;
    }
    if (!flush(context)) { result = PWP_OS; goto failed; }
    if (!verify(length, context)) goto failed;
    stage->phase = PWP_STAGE_FLUSHED; return PWP_OK;
failed:
    stage->phase = PWP_STAGE_FAILED; return result;
}
pwp_result pwp_stage_discard(pwp_stage *stage, pwp_stage_action mark_delete,
                            pwp_stage_action close, void *context) {
    if (!stage || !mark_delete || !close || stage->phase == PWP_STAGE_EMPTY) return PWP_ARGUMENT;
    if (stage->phase == PWP_STAGE_RETIRED) return PWP_OK;
    if (stage->phase == PWP_STAGE_RETIRING || stage->phase == PWP_STAGE_QUARANTINED) return PWP_CLEANUP_UNKNOWN;
    if (stage->phase == PWP_STAGE_FILLING) return PWP_BUSY;
    if (stage->phase != PWP_STAGE_OWNED && stage->phase != PWP_STAGE_FLUSHED && stage->phase != PWP_STAGE_FAILED)
        return PWP_ARGUMENT;
    stage->phase = PWP_STAGE_RETIRING;
    int deleted = mark_delete(context);
    int closed = close(context); /* Independent release is still attempted after deletion uncertainty. */
    stage->phase = deleted && closed ? PWP_STAGE_RETIRED : PWP_STAGE_QUARANTINED;
    return stage->phase == PWP_STAGE_RETIRED ? PWP_OK : PWP_CLEANUP_UNKNOWN;
}

pwp_result pwp_lock_finish(pwp_owner *owner, uint64_t token, pwp_lock_action verify,
                           pwp_lock_action flush, pwp_close_callback close, void *context) {
    pwp_owned_handle *h = pwp_lookup(owner, token);
    if (!h || h->state != 2 || h->published || !verify || !flush || !close) return PWP_ARGUMENT;
    pwp_result result = PWP_CLEANUP_UNKNOWN;
    if (owner->poisoned) goto failed;
    result = PWP_LIMIT;
    if (pwp_public_count(owner) >= PWP_PUBLIC_HANDLE_LIMIT) goto failed;
    result = PWP_POLICY;
    if (!verify(context)) goto failed;
    result = PWP_CLEANUP_UNKNOWN;
    if (owner->poisoned) goto failed;
    result = PWP_OS;
    if (!flush(context)) goto failed;
    result = PWP_CLEANUP_UNKNOWN;
    if (owner->poisoned) goto failed;
    result = PWP_POLICY;
    if (!verify(context)) goto failed;
    result = pwp_publish(owner, token);
    if (result == PWP_OK) return PWP_OK;
failed:
    if (pwp_retire(owner, token, close, context) != PWP_OK || owner->poisoned) return PWP_CLEANUP_UNKNOWN;
    return result;
}

int pwp_expected_file(const uint64_t *words, size_t count, uint64_t parent_volume) {
    return words && count == PWP_IDENTITY_WORDS && words[0] == 1 && parent_volume != 0 &&
        words[1] == parent_volume && (words[2] != 0 || words[3] != 0) && words[4] == 0x2ff && words[5] == 1;
}
typedef struct {
    pwp_owner *owner;
    pwp_lock_action verify, mark, pending_verify;
    pwp_close_callback close;
    void *context;
    pwp_result result;
} pwp_delete_context;
static int delete_and_close(uintptr_t resource, void *opaque) {
    pwp_delete_context *c = opaque;
    int attempted = 0, confirmed = 0;
    c->result = PWP_CLEANUP_UNKNOWN;
    if (!c->owner->poisoned) {
        int verified = c->verify(c->context);
        if (!c->owner->poisoned) {
            c->result = PWP_POLICY;
            if (verified) {
                attempted = 1; c->result = PWP_CLEANUP_UNKNOWN;
                if (c->mark(c->context) && !c->owner->poisoned &&
                    c->pending_verify(c->context) && !c->owner->poisoned) {
                    confirmed = 1; c->result = PWP_OK;
                }
            }
        }
    }
    int closed = c->close(resource, c->context); /* Never skip independent exact-handle release. */
    return closed && (!attempted || (confirmed && !c->owner->poisoned));
}
pwp_result pwp_delete_intent_finish(pwp_owner *owner, uint64_t token, pwp_lock_action verify,
                                    pwp_lock_action mark, pwp_lock_action pending_verify,
                                    pwp_close_callback close, void *context) {
    pwp_owned_handle *h = pwp_lookup(owner, token);
    if (!h || h->state != 2 || h->published || !verify || !mark || !pending_verify || !close)
        return PWP_ARGUMENT;
    pwp_delete_context operation = {owner, verify, mark, pending_verify, close, context, PWP_CLEANUP_UNKNOWN};
    /* Retiring before callbacks prevents re-entry; callback uses the saved resource, not live-token lookup. */
    pwp_result retired = pwp_retire(owner, token, delete_and_close, &operation);
    return retired != PWP_OK || owner->poisoned ? PWP_CLEANUP_UNKNOWN : operation.result;
}
