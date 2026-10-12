#include "profile_policy.h"
#include <string.h>
#include <stdlib.h>

pwp_result pwp_cleanup_result(pwp_result result, int failed, int poisoned) {
    return failed || poisoned ? PWP_CLEANUP_UNKNOWN : result;
}

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

void pwp_roles_init(pwp_roles *roles) { memset(roles, 0, sizeof(*roles)); }
pwp_lease_role pwp_lease_name(const uint16_t *name, size_t length) {
    static const char *names[] = {"profile.lock", "vault.lock"};
    if (!name || !length || length > PWP_COMPONENT_LIMIT) return PWP_LEASE_NONE;
    for (size_t kind = 0; kind < 2; ++kind) {
        size_t i = 0;
        if (length != strlen(names[kind])) continue;
        while (i < length && name[i] == (uint16_t)names[kind][i]) ++i;
        if (i == length) return kind == 0 ? PWP_LEASE_PROFILE : PWP_LEASE_VAULT;
    }
    return PWP_LEASE_NONE;
}
static int role_live(const pwp_owner *owner, uint64_t token) {
    if (!pwp_token_valid(token)) return 0;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        const pwp_owned_handle *h = &owner->slots[i];
        if (h->token == token) return h->state == 2 && h->published && h->resource;
    }
    return 0;
}
static int roles_present(const pwp_roles *roles) {
    if (roles->root || roles->identity || roles->profile || roles->vault ||
        roles->vault_profile || roles->vault_directory) return 1;
    for (size_t i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i) if (roles->stages[i].token) return 1;
    return 0;
}
static int role_bound(const pwp_roles *roles, uint64_t token) {
    if (token == roles->root || token == roles->identity || token == roles->profile || token == roles->vault)
        return 1;
    for (size_t i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i) if (roles->stages[i].token == token) return 1;
    return 0;
}
static int owners_retired(const pwp_owner *owner) {
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i)
        if (owner->slots[i].state != 0 && owner->slots[i].state != 3) return 0;
    return 1;
}
static pwp_result role_root_ready(const pwp_roles *roles, const pwp_owner *owner) {
    if (!roles || !owner) return PWP_ARGUMENT;
    if (owner->poisoned) return PWP_CLEANUP_UNKNOWN;
    if (roles->retiring_all) return PWP_BUSY;
    return !roles->opening && role_live(owner, roles->root) ? PWP_OK : PWP_POLICY;
}
pwp_result pwp_roles_begin_root(pwp_roles *roles, const pwp_owner *owner) {
    if (!roles || !owner) return PWP_ARGUMENT;
    if (owner->poisoned) return PWP_CLEANUP_UNKNOWN;
    if (roles->opening || roles->retiring_all || roles_present(roles) || !owners_retired(owner)) return PWP_BUSY;
    if (!pwp_token_valid(owner->next)) return PWP_LIMIT;
    roles->root_floor = owner->next; roles->opening = 1;
    return PWP_OK;
}
pwp_result pwp_roles_bind_root(pwp_roles *roles, const pwp_owner *owner, uint64_t token) {
    if (!roles || !owner || !pwp_token_valid(token)) return PWP_ARGUMENT;
    if (owner->poisoned) return PWP_CLEANUP_UNKNOWN;
    if (roles->retiring_all || roles_present(roles)) return PWP_BUSY;
    if (!roles->opening || token < roles->root_floor || !role_live(owner, token)) return PWP_POLICY;
    roles->root = token; roles->opening = 0;
    return PWP_OK;
}
pwp_result pwp_roles_identity_admit(const pwp_roles *roles, const pwp_owner *owner, uint64_t parent) {
    pwp_result result = role_root_ready(roles, owner);
    if (result != PWP_OK) return result;
    if (parent != roles->root) return PWP_POLICY;
    return roles->identity ? PWP_BUSY : PWP_OK;
}
pwp_result pwp_roles_bind_identity(pwp_roles *roles, const pwp_owner *owner, uint64_t parent, uint64_t token) {
    pwp_result result = pwp_roles_identity_admit(roles, owner, parent);
    if (result != PWP_OK) return result;
    if (token <= parent || role_bound(roles, token) || !role_live(owner, token)) return PWP_POLICY;
    roles->identity = token;
    return PWP_OK;
}
static int profile_role_live(const pwp_roles *roles, const pwp_owner *owner) {
    return roles->profile > roles->root && role_live(owner, roles->profile);
}
static int vault_role_live(const pwp_roles *roles, const pwp_owner *owner) {
    return profile_role_live(roles, owner) && role_live(owner, roles->identity) &&
        roles->vault > roles->profile && roles->vault_directory == roles->identity &&
        roles->vault_profile == roles->profile && role_live(owner, roles->vault);
}
pwp_result pwp_roles_lease_admit(const pwp_roles *roles, const pwp_owner *owner,
                                uint64_t directory, pwp_lease_role role) {
    if (role != PWP_LEASE_PROFILE && role != PWP_LEASE_VAULT) return PWP_ARGUMENT;
    pwp_result result = role_root_ready(roles, owner);
    if (result != PWP_OK) return result;
    if (role == PWP_LEASE_PROFILE) {
        if (directory != roles->root) return PWP_POLICY;
        if (roles->profile || roles->vault) return PWP_BUSY;
        for (size_t i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i)
            if (roles->stages[i].token) return PWP_BUSY;
        return PWP_OK;
    }
    if (directory != roles->identity || !role_live(owner, directory) || !profile_role_live(roles, owner))
        return PWP_POLICY;
    if (roles->vault || roles->vault_profile || roles->vault_directory) return PWP_BUSY;
    for (size_t i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i)
        if (roles->stages[i].token && roles->stages[i].grant.vault) return PWP_BUSY;
    return PWP_OK;
}
pwp_result pwp_roles_bind_lease(pwp_roles *roles, const pwp_owner *owner,
                               uint64_t directory, pwp_lease_role role, uint64_t token) {
    pwp_result result = pwp_roles_lease_admit(roles, owner, directory, role);
    if (result != PWP_OK) return result;
    if (token <= directory || role_bound(roles, token) || !role_live(owner, token) ||
        (role == PWP_LEASE_VAULT && token <= roles->profile)) return PWP_POLICY;
    if (role == PWP_LEASE_PROFILE) roles->profile = token;
    else {
        roles->vault = token; roles->vault_profile = roles->profile; roles->vault_directory = directory;
    }
    return PWP_OK;
}
pwp_result pwp_roles_capture(const pwp_roles *roles, const pwp_owner *owner,
                            uint64_t directory, pwp_role_grant *grant) {
    if (!grant) return PWP_ARGUMENT;
    memset(grant, 0, sizeof(*grant));
    pwp_result result = role_root_ready(roles, owner);
    if (result != PWP_OK) return result;
    if (!profile_role_live(roles, owner)) return PWP_POLICY;
    uint64_t vault = 0;
    if (directory != roles->root) {
        if (directory != roles->identity || !vault_role_live(roles, owner)) return PWP_POLICY;
        vault = roles->vault;
    }
    grant->root = roles->root; grant->directory = directory; grant->profile = roles->profile; grant->vault = vault;
    return PWP_OK;
}
pwp_result pwp_roles_check_grant(const pwp_roles *roles, const pwp_owner *owner, const pwp_role_grant *grant) {
    if (!grant) return PWP_ARGUMENT;
    pwp_role_grant current;
    pwp_result result = pwp_roles_capture(roles, owner, grant->directory, &current);
    if (result != PWP_OK) return result;
    return current.root == grant->root && current.directory == grant->directory &&
        current.profile == grant->profile && current.vault == grant->vault ? PWP_OK : PWP_POLICY;
}
pwp_result pwp_roles_bind_stage(pwp_roles *roles, const pwp_owner *owner,
                               uint64_t token, const pwp_role_grant *grant) {
    pwp_result result = pwp_roles_check_grant(roles, owner, grant);
    if (result != PWP_OK) return result;
    if (role_bound(roles, token)) return PWP_BUSY;
    if (token <= grant->directory || token <= grant->profile || token <= grant->vault || !role_live(owner, token))
        return PWP_POLICY;
    for (size_t i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i) if (!roles->stages[i].token) {
        roles->stages[i].token = token; roles->stages[i].grant = *grant;
        return PWP_OK;
    }
    return PWP_LIMIT;
}
pwp_result pwp_roles_check_stage(const pwp_roles *roles, const pwp_owner *owner, uint64_t token) {
    pwp_result result = role_root_ready(roles, owner);
    if (result != PWP_OK) return result;
    if (!role_live(owner, token)) return PWP_POLICY;
    for (size_t i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i)
        if (roles->stages[i].token == token) return pwp_roles_check_grant(roles, owner, &roles->stages[i].grant);
    return PWP_POLICY;
}
pwp_result pwp_roles_retire(pwp_roles *roles, pwp_owner *owner, uint64_t token,
                           pwp_close_callback close, void *context) {
    if (!roles || !owner || !close) return PWP_ARGUMENT;
    pwp_owned_handle *handle = pwp_lookup(owner, token);
    if (!handle) return PWP_ARGUMENT;
    if (handle->state == 3 || handle->state == 4) return pwp_retire(owner, token, close, context);
    /* A partial unpublished vault/stage can also poison ownership. Do not release its granting parents
     * independently just because it never acquired a public stage/lease record. Root cleanup owns that case. */
    if (owner->poisoned && (token == roles->root || token == roles->identity ||
        token == roles->profile || token == roles->vault)) return PWP_CLEANUP_UNKNOWN;
    if (token == roles->root) return PWP_BUSY;
    if ((token == roles->profile || token == roles->identity) && roles->vault) return PWP_BUSY;
    for (size_t i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i) {
        const pwp_role_stage *stage = &roles->stages[i];
        if (stage->token && (stage->grant.profile == token || stage->grant.vault == token ||
            stage->grant.directory == token)) return PWP_BUSY;
    }
    pwp_result result = pwp_retire(owner, token, close, context);
    if (result != PWP_OK) return result;
    if (token == roles->profile) roles->profile = 0;
    if (token == roles->identity) roles->identity = 0;
    if (token == roles->vault) roles->vault = roles->vault_profile = roles->vault_directory = 0;
    for (size_t i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i)
        if (roles->stages[i].token == token) memset(&roles->stages[i], 0, sizeof(roles->stages[i]));
    return PWP_OK;
}
pwp_result pwp_roles_retire_all(pwp_roles *roles, pwp_owner *owner, pwp_close_callback close, void *context) {
    if (!roles || !owner || !close) return PWP_ARGUMENT;
    if (roles->retiring_all) return PWP_BUSY;
    roles->retiring_all = 1;
    /* Deliberately bypass ordinary dependency/poison admission so no independent original close is skipped. */
    pwp_result result = pwp_retire_all(owner, close, context);
    roles->retiring_all = 0;
    if (result != PWP_OK || owner->poisoned || !owners_retired(owner)) {
        owner->poisoned = 1;
        return PWP_CLEANUP_UNKNOWN;
    }
    pwp_roles_init(roles); /* owner.next and every original ownership record remain untouched. */
    return PWP_OK;
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

int pwp_candidate_name(const uint16_t *name, size_t length) {
    static const char prefix[] = "pwp-pending-";
    if (!name || length != sizeof(prefix)-1+32) return 0;
    for (size_t i = 0; i < sizeof(prefix)-1; ++i) if (name[i] != (uint16_t)prefix[i]) return 0;
    for (size_t i = sizeof(prefix)-1; i < length; ++i)
        if (!digit(name[i]) && !(name[i] >= 'a' && name[i] <= 'f')) return 0;
    return 1;
}
pwp_result pwp_candidate_init(pwp_candidate *candidate) {
    if (!candidate) return PWP_ARGUMENT;
    if (candidate->phase != PWP_CANDIDATE_EMPTY) return PWP_CLOSED;
    candidate->prepared_size = 0;
    candidate->phase = PWP_CANDIDATE_OWNED;
    return PWP_OK;
}
pwp_result pwp_candidate_fill(pwp_candidate *candidate, const unsigned char *bytes, size_t count,
                             pwp_stage_write write, pwp_stage_action flush, pwp_stage_action rewind,
                             pwp_candidate_read read, pwp_stage_verify verify, void *context) {
    unsigned char scratch[4096] = {0};
    pwp_result result = PWP_ARGUMENT;
    if (!candidate) goto done;
    if (candidate->phase != PWP_CANDIDATE_OWNED) { result = PWP_CLOSED; goto done; }
    candidate->prepared_size = 0;
    candidate->phase = PWP_CANDIDATE_FAILED;
    if ((!bytes && count) || count > PWP_RECORD_LIMIT || !write || !flush || !rewind || !read || !verify) goto done;
    candidate->phase = PWP_CANDIDATE_FILLING;
    result = PWP_POLICY;
    if (!verify(0, context)) goto failed;
    size_t offset = 0;
    while (offset < count) {
        size_t requested = count-offset, actual = 0;
        if (requested > 65536) requested = 65536;
        result = PWP_OS;
        if (!write(bytes+offset, requested, &actual, context) || !actual || actual > requested) goto failed;
        offset += actual;
    }
    result = PWP_OS;
    if (!flush(context)) goto failed;
    result = PWP_POLICY;
    if (!verify(count, context)) goto failed;
    result = PWP_OS;
    if (!rewind(context)) goto failed;
    offset = 0;
    while (offset < count) {
        size_t requested = count-offset, actual = 0;
        if (requested > sizeof(scratch)) requested = sizeof(scratch);
        result = PWP_OS;
        if (!read(scratch, requested, &actual, context) || !actual || actual > requested) goto failed;
        result = PWP_POLICY;
        if (memcmp(scratch, bytes+offset, actual) != 0) goto failed;
        pwp_clear(scratch, sizeof(scratch));
        offset += actual;
    }
    size_t actual = 0;
    result = PWP_OS;
    if (!read(scratch, 1, &actual, context) || actual > 1) goto failed;
    result = PWP_POLICY;
    if (actual || !verify(count, context)) goto failed;
    candidate->prepared_size = count;
    candidate->phase = PWP_CANDIDATE_VERIFIED;
    result = PWP_OK;
    goto done;
failed:
    candidate->prepared_size = 0;
    candidate->phase = PWP_CANDIDATE_FAILED;
done:
    pwp_clear(scratch, sizeof(scratch));
    return result;
}

int pwp_candidate_target(const uint16_t *name, size_t length, int identity_scope) {
    static const char header[] = "profile.header", suffix[] = ".aesgcm";
    if (!name || (identity_scope != 0 && identity_scope != 1)) return 0;
    if (!identity_scope) {
        if (length != sizeof(header)-1) return 0;
        for (size_t i = 0; i < length; ++i) if (name[i] != (uint16_t)header[i]) return 0;
        return 1;
    }
    if (length != 64+sizeof(suffix)-1) return 0;
    for (size_t i = 0; i < 64; ++i)
        if (!digit(name[i]) && !(name[i] >= 'a' && name[i] <= 'f')) return 0;
    for (size_t i = 0; i < sizeof(suffix)-1; ++i) if (name[64+i] != (uint16_t)suffix[i]) return 0;
    return 1;
}
int pwp_candidate_replace_target(const uint16_t *name, size_t length, int identity_scope) {
    return identity_scope == 1 && pwp_candidate_target(name, length, 1);
}
pwp_result pwp_candidate_rename_new(pwp_candidate *candidate, pwp_stage_verify before,
                                   pwp_stage_action rename, pwp_stage_verify after,
                                   pwp_stage_action flush, void *context) {
    if (!candidate) return PWP_ARGUMENT;
    if (candidate->phase != PWP_CANDIDATE_VERIFIED) return PWP_CLOSED;
    if (candidate->prepared_size > PWP_RECORD_LIMIT) {
        candidate->phase = PWP_CANDIDATE_FAILED;
        return PWP_ARGUMENT;
    }
    if (!before || !rename || !after || !flush) return PWP_ARGUMENT;
    const size_t prepared_size = candidate->prepared_size;
    candidate->phase = PWP_CANDIDATE_RENAMING;
    if (!before(prepared_size, context)) {
        candidate->phase = PWP_CANDIDATE_FAILED;
        return PWP_POLICY;
    }
    if (!rename(context) || !after(prepared_size, context) || !flush(context) || !after(prepared_size, context)) {
        candidate->phase = PWP_CANDIDATE_UNCERTAIN;
        return PWP_CLEANUP_UNKNOWN;
    }
    candidate->phase = PWP_CANDIDATE_RENAMED;
    return PWP_OK;
}
pwp_result pwp_candidate_replace(pwp_candidate *candidate, pwp_owner *owner, uint64_t target,
                                 pwp_stage_verify before, pwp_stage_action target_verify,
                                 pwp_close_callback target_close, pwp_replace_action rename,
                                 pwp_stage_verify after, pwp_stage_action flush, void *context) {
    if (!candidate || !owner) return PWP_ARGUMENT;
    if (candidate->phase != PWP_CANDIDATE_VERIFIED) return PWP_CLOSED;
    if (candidate->prepared_size > PWP_RECORD_LIMIT) {
        candidate->phase = PWP_CANDIDATE_FAILED;
        return PWP_ARGUMENT;
    }
    if (!before || !target_verify || !target_close || !rename || !after || !flush) return PWP_ARGUMENT;
    pwp_owned_handle *held = target ? pwp_lookup(owner, target) : NULL;
    if (target && (!held || held->state != 2 || !held->resource || held->published)) return PWP_ARGUMENT;
    if (owner->poisoned) return PWP_CLEANUP_UNKNOWN;
    const size_t prepared_size = candidate->prepared_size;
    candidate->phase = PWP_CANDIDATE_RENAMING; /* The fresh target's ownership transfers here. */
    int verified = before(prepared_size, context);
    if (verified && target) verified = target_verify(context);
    /* Close even after verification refuses. Never read held again: later source verification can
     * reserve/reuse this retired registry slot. Only the numeric existence decision survives close. */
    pwp_result cleanup = target ? pwp_retire(owner, target, target_close, context) : PWP_OK;
    if (cleanup != PWP_OK || owner->poisoned) {
        candidate->phase = PWP_CANDIDATE_FAILED;
        return PWP_CLEANUP_UNKNOWN;
    }
    int reverified = verified && before(prepared_size, context);
    if (!reverified || owner->poisoned) {
        candidate->phase = PWP_CANDIDATE_FAILED;
        return owner->poisoned ? PWP_CLEANUP_UNKNOWN : PWP_POLICY;
    }
    if (!rename(target != 0, context) || !after(prepared_size, context) ||
        !flush(context) || !after(prepared_size, context)) {
        candidate->phase = PWP_CANDIDATE_UNCERTAIN;
        return PWP_CLEANUP_UNKNOWN;
    }
    candidate->phase = PWP_CANDIDATE_RENAMED;
    return PWP_OK;
}
int pwp_candidate_close_ok(const pwp_candidate *candidate, int os_closed) {
    if (!candidate || os_closed != 1) return 0;
    return candidate->phase == PWP_CANDIDATE_OWNED || candidate->phase == PWP_CANDIDATE_VERIFIED ||
        candidate->phase == PWP_CANDIDATE_FAILED || candidate->phase == PWP_CANDIDATE_RENAMED;
}

int pwp_directory_sync_access(int query_succeeded, uint32_t granted_access) {
    return query_succeeded == 1 && granted_access == PWP_DIRECTORY_SYNC_ACCESS;
}
pwp_result pwp_directory_sync_apply(pwp_directory_sync *sync, pwp_stage_action verify,
                                    pwp_stage_action flush, void *context) {
    if (!sync) return PWP_ARGUMENT;
    if (sync->phase != PWP_SYNC_READY) return PWP_CLOSED;
    if (!verify || !flush) return PWP_ARGUMENT;
    sync->phase = PWP_SYNC_RUNNING;
    if (!verify(context)) {
        sync->phase = PWP_SYNC_READY;
        return PWP_POLICY;
    }
    if (!flush(context) || !verify(context)) {
        sync->phase = PWP_SYNC_UNCERTAIN;
        return PWP_CLEANUP_UNKNOWN;
    }
    sync->phase = PWP_SYNC_READY;
    return PWP_OK;
}
int pwp_directory_sync_close_ok(const pwp_directory_sync *sync, int os_closed) {
    return sync && sync->phase == PWP_SYNC_READY && os_closed == 1;
}

int pwp_record_write_request(const uint16_t *pending, size_t pending_length,
                             const uint16_t *target, size_t target_length, size_t count,
                             int identity_scope, int replace) {
    return count <= PWP_RECORD_LIMIT && (replace == 0 || replace == 1) &&
        pwp_candidate_name(pending, pending_length) &&
        (replace ? pwp_candidate_replace_target(target, target_length, identity_scope) :
                   pwp_candidate_target(target, target_length, identity_scope));
}
static pwp_result record_result(pwp_result result) {
    return (unsigned)result <= PWP_UNIMPLEMENTED ? result : PWP_CLEANUP_UNKNOWN;
}
pwp_result pwp_record_write_apply(pwp_record_write *write, pwp_record_prepare prepare,
                                  pwp_record_action publish, pwp_record_action sync,
                                  pwp_record_action close, pwp_record_uncertain uncertain, void *context) {
    if (!write) return PWP_ARGUMENT;
    if (write->phase != PWP_WRITE_NEW) return PWP_CLOSED;
    if (write->candidate || !prepare || !publish || !sync || !close || !uncertain) return PWP_ARGUMENT;
    write->phase = PWP_WRITE_PREPARING;
    uint64_t token = 0;
    pwp_result result = record_result(prepare(&token, context));
    write->candidate = token;
    if (!pwp_token_valid(token)) {
        /* No raw handle/token reconstruction, and no close of an invalid or missing owner. */
        if (token || result == PWP_OK || result == PWP_CLEANUP_UNKNOWN) {
            write->phase = PWP_WRITE_UNCERTAIN;
            uncertain(0, context);
            return PWP_CLEANUP_UNKNOWN;
        }
        write->phase = PWP_WRITE_FAILED;
        return result;
    }
    if (result == PWP_OK) {
        write->phase = PWP_WRITE_PUBLISHING;
        result = record_result(publish(token, context));
        if (result == PWP_OK) {
            write->phase = PWP_WRITE_SYNCING;
            /* Even an ordinary sync-admission refusal occurs after name publication now. */
            if (sync(token, context) != PWP_OK) result = PWP_CLEANUP_UNKNOWN;
        }
    }
    int sealed = result == PWP_CLEANUP_UNKNOWN;
    if (sealed) {
        write->phase = PWP_WRITE_UNCERTAIN;
        uncertain(token, context);
    }
    write->phase = PWP_WRITE_CLOSING;
    if (close(token, context) != PWP_OK) {
        result = PWP_CLEANUP_UNKNOWN;
        if (!sealed) {
            write->phase = PWP_WRITE_UNCERTAIN;
            uncertain(token, context);
        }
    }
    write->phase = result == PWP_OK ? PWP_WRITE_COMPLETE :
        result == PWP_CLEANUP_UNKNOWN ? PWP_WRITE_UNCERTAIN : PWP_WRITE_FAILED;
    return result;
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

int pwp_expected_child_directory(const uint64_t *parent, const uint64_t *child, size_t count) {
    if (!parent || !child || count != PWP_IDENTITY_WORDS) return 0;
    return parent[0] == 1 && child[0] == 1 && parent[1] != 0 && parent[1] == child[1] &&
        (parent[2] != 0 || parent[3] != 0) && (child[2] != 0 || child[3] != 0) &&
        (parent[2] != child[2] || parent[3] != child[3]) &&
        parent[4] == 0x1ff && child[4] == 0x1ff && parent[5] == 1 && child[5] == 1;
}
int pwp_vault_directory_scope(const uint64_t *root, const uint64_t *identity, size_t count,
                               const uint16_t *root_path, size_t root_length,
                               const uint16_t *identity_path, size_t identity_length) {
    static const char suffix[] = "\\identity";
    if (!root_path || !identity_path || !root_length || root_length >= PWP_PATH_LIMIT ||
        identity_length >= PWP_PATH_LIMIT || identity_length < root_length ||
        identity_length-root_length != sizeof(suffix)-1 ||
        !pwp_expected_child_directory(root, identity, count)) return 0;
    /* Root paths already passed the native KnownFolder/handle policy. Do not normalize or repair them. */
    for (size_t i = 0; i < root_length; ++i)
        if (lower(root_path[i]) != lower(identity_path[i])) return 0;
    for (size_t i = 0; i < sizeof(suffix)-1; ++i)
        if (lower(identity_path[root_length+i]) != (uint16_t)suffix[i]) return 0;
    return 1;
}
int pwp_expected_lock_file(const uint64_t *directory, const uint64_t *file, size_t count) {
    return directory && count == PWP_IDENTITY_WORDS && directory[0] == 1 &&
        (directory[2] != 0 || directory[3] != 0) && directory[4] == 0x1ff && directory[5] == 1 &&
        pwp_expected_file(file, count, directory[1]) &&
        (directory[2] != file[2] || directory[3] != file[3]);
}
pwp_result pwp_child_finish(pwp_owner *owner, uint64_t token, pwp_lock_action verify,
                            pwp_close_callback close, void *context) {
    pwp_owned_handle *h = pwp_lookup(owner, token);
    if (!h || h->state != 2 || h->published || !verify || !close) return PWP_ARGUMENT;
    pwp_result result = PWP_CLEANUP_UNKNOWN;
    if (owner->poisoned) goto failed;
    result = PWP_LIMIT;
    if (pwp_public_count(owner) >= PWP_PUBLIC_HANDLE_LIMIT) goto failed;
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

int pwp_exact_name_absence(uint32_t status, int null_handle) {
    return status == UINT32_C(0xc0000034) && null_handle == 1; /* STATUS_OBJECT_NAME_NOT_FOUND */
}
pwp_result pwp_name_absence_finish(pwp_owner *owner, uint64_t probe, uint32_t status, int null_handle,
                                   pwp_lock_action verify, pwp_close_callback close, void *context) {
    pwp_owned_handle *held = pwp_lookup(owner, probe);
    if (!held || held->published || (held->state != 1 && held->state != 2) ||
        (held->state == 1 && held->resource) || (held->state == 2 && !held->resource) ||
        (null_handle != 0 && null_handle != 1) || !verify || !close) return PWP_ARGUMENT;
    const int missing = pwp_exact_name_absence(status, null_handle) && held->state == 1 && !held->resource;
    /* Snapshot the observation first. Native verification may reuse this retired reservation/owner slot. */
    pwp_result cleanup = pwp_retire(owner, probe, close, context);
    if (cleanup != PWP_OK || owner->poisoned) return PWP_CLEANUP_UNKNOWN;
    return missing && verify(context) && !owner->poisoned ? PWP_NOT_FOUND : PWP_CLEANUP_UNKNOWN;
}
pwp_result pwp_record_delete_apply(pwp_record_delete *deletion, pwp_record_step remove,
                                   pwp_record_step absent, pwp_record_step sync,
                                   pwp_delete_uncertain uncertain, void *context) {
    if (!deletion) return PWP_ARGUMENT;
    if (deletion->phase != PWP_DELETE_NEW) return PWP_CLOSED;
    if (!remove || !absent || !sync || !uncertain) return PWP_ARGUMENT;
    deletion->phase = PWP_DELETE_INTENT;
    pwp_result result = record_result(remove(context));
    if (result == PWP_OK) {
        deletion->phase = PWP_DELETE_OBSERVING;
        if (absent(context) != PWP_NOT_FOUND) result = PWP_CLEANUP_UNKNOWN;
        else {
            deletion->phase = PWP_DELETE_SYNCING;
            if (sync(context) != PWP_OK) result = PWP_CLEANUP_UNKNOWN;
        }
    }
    deletion->phase = result == PWP_OK ? PWP_DELETE_COMPLETE :
        result == PWP_CLEANUP_UNKNOWN ? PWP_DELETE_UNCERTAIN : PWP_DELETE_FAILED;
    if (result == PWP_CLEANUP_UNKNOWN) uncertain(context);
    return result;
}
