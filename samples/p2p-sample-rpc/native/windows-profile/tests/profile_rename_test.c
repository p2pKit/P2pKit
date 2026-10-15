/* Portable controller/owner tests only. No Windows header, syscall, filesystem, or durability model. */
#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

enum { BEFORE = 1, RENAME, AFTER, FLUSH };
typedef struct {
    pwp_candidate candidate;
    size_t count;
    unsigned calls, befores, renames, afters, flushes, trace[16];
    unsigned fail_after, reenter;
    int fail_before, fail_rename, fail_flush, failed_rename_changes_name, name_changed;
    pwp_owner *owner;
    pwp_roles *roles;
    uint64_t token;
    pwp_role_grant grant;
} fixture;

static int before_rename(size_t count, void *opaque);
static int rename_once(void *opaque);
static int after_rename(size_t count, void *opaque);
static int flush_renamed(void *opaque);
static pwp_result run_rename(fixture *f) {
    return pwp_candidate_rename_new(&f->candidate, before_rename, rename_once, after_rename, flush_renamed, f);
}
static fixture prepared_fixture(size_t count) {
    fixture f = {0};
    /* Input-state fixture, not a claim that these bytes were written on Windows. */
    f.candidate.phase = PWP_CANDIDATE_VERIFIED;
    f.candidate.prepared_size = count;
    f.count = count;
    return f;
}
static int authority_current(fixture *f) {
    if (!f->owner && !f->roles) return 1;
    return f->owner && f->roles &&
        pwp_roles_check_stage(f->roles, f->owner, f->token) == PWP_OK &&
        pwp_roles_check_grant(f->roles, f->owner, &f->grant) == PWP_OK;
}
static void observe(fixture *f, unsigned event) {
    assert(f->candidate.phase == PWP_CANDIDATE_RENAMING && f->candidate.prepared_size == f->count);
    assert(f->calls < sizeof(f->trace)/sizeof(f->trace[0]));
    f->trace[f->calls++] = event;
    if (f->reenter & (1u << (f->calls-1))) {
        unsigned calls = f->calls;
        assert(run_rename(f) == PWP_CLOSED);
        assert(pwp_candidate_init(&f->candidate) == PWP_CLOSED);
        assert(pwp_candidate_fill(&f->candidate, NULL, 0, NULL, NULL, NULL, NULL, NULL, f) == PWP_CLOSED);
        assert(!pwp_candidate_close_ok(&f->candidate, 1));
        assert(f->calls == calls && f->candidate.phase == PWP_CANDIDATE_RENAMING);
        assert(f->candidate.prepared_size == f->count);
    }
}
static int before_rename(size_t count, void *opaque) {
    fixture *f = opaque; observe(f, BEFORE); ++f->befores;
    assert(count == f->count && f->befores == 1 && !f->renames && !f->afters && !f->flushes);
    return !f->fail_before && authority_current(f);
}
static int rename_once(void *opaque) {
    fixture *f = opaque; observe(f, RENAME); ++f->renames;
    assert(f->befores == 1 && f->renames == 1 && !f->afters && !f->flushes);
    if (!f->fail_rename || f->failed_rename_changes_name) f->name_changed = 1;
    return !f->fail_rename && authority_current(f);
}
static int after_rename(size_t count, void *opaque) {
    fixture *f = opaque; observe(f, AFTER); ++f->afters;
    assert(count == f->count && f->name_changed && f->befores == 1 && f->renames == 1);
    assert(f->afters <= 2 && f->flushes == f->afters-1);
    return f->afters != f->fail_after && authority_current(f);
}
static int flush_renamed(void *opaque) {
    fixture *f = opaque; observe(f, FLUSH); ++f->flushes;
    assert(f->name_changed && f->befores == 1 && f->renames == 1 && f->afters == 1 && f->flushes == 1);
    return !f->fail_flush && authority_current(f);
}
static void no_repeat(fixture *f, pwp_candidate_phase phase) {
    unsigned calls = f->calls;
    assert(f->candidate.phase == phase && f->candidate.prepared_size == f->count);
    assert(run_rename(f) == PWP_CLOSED);
    assert(pwp_candidate_rename_new(&f->candidate, NULL, NULL, NULL, NULL, NULL) == PWP_CLOSED);
    assert(pwp_candidate_init(&f->candidate) == PWP_CLOSED);
    assert(pwp_candidate_fill(&f->candidate, NULL, 0, NULL, NULL, NULL, NULL, NULL, f) == PWP_CLOSED);
    assert(f->calls == calls && f->candidate.phase == phase && f->candidate.prepared_size == f->count);
}
static size_t wide(const char *text, uint16_t *name) {
    size_t count = strlen(text);
    for (size_t i = 0; i < count; ++i) name[i] = (unsigned char)text[i];
    return count;
}
static void root_target(void) {
    uint16_t name[96] = {0};
    size_t count = wide("profile.header", name);
    assert(count == 14 && pwp_candidate_target(name, count, 0));
    assert(!pwp_candidate_target(name, count, 1));
    const uint16_t invalid[] = {'A', '-', '/', '\\', ':', '.', 0, 0xd800, 0xffff};
    for (size_t i = 0; i < count; ++i) {
        uint16_t saved = name[i];
        for (size_t j = 0; j < sizeof(invalid)/sizeof(invalid[0]); ++j) {
            if (invalid[j] == saved) continue;
            name[i] = invalid[j]; assert(!pwp_candidate_target(name, count, 0));
        }
        name[i] = saved;
    }
}
static void identity_target(void) {
    uint16_t name[96] = {0};
    size_t count = wide("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.aesgcm", name);
    assert(count == 71 && pwp_candidate_target(name, count, 1));
    assert(!pwp_candidate_target(name, count, 0));
    const uint16_t invalid[] = {'A', 'F', 'g', 'G', '-', '/', '\\', ':', '.', 0, 0xd800, 0xffff};
    for (size_t i = 0; i < count; ++i) {
        uint16_t saved = name[i];
        for (size_t j = 0; j < sizeof(invalid)/sizeof(invalid[0]); ++j) {
            if (invalid[j] == saved) continue;
            name[i] = invalid[j]; assert(!pwp_candidate_target(name, count, 1));
        }
        name[i] = saved;
    }
    for (size_t i = 0; i < 64; ++i) name[i] = '0';
    assert(pwp_candidate_target(name, count, 1));
    for (size_t i = 0; i < 64; ++i) name[i] = 'f';
    assert(pwp_candidate_target(name, count, 1));
}
static void target_lengths_and_scopes(void) {
    uint16_t name[96] = {0};
    const char *valid[] = {"profile.header",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.aesgcm"};
    for (int scope = 0; scope <= 1; ++scope) {
        size_t count = wide(valid[scope], name);
        assert(!pwp_candidate_target(NULL, count, scope));
        for (size_t length = 0; length <= 96; ++length)
            assert(pwp_candidate_target(name, length, scope) == (length == count));
        assert(!pwp_candidate_target(name, SIZE_MAX, scope));
        assert(!pwp_candidate_target(name, count, -1));
        assert(!pwp_candidate_target(name, count, 2));
    }
    const char *reserved[] = {"profile.lock", "vault.lock", "identity", "PROFILE.HEADER",
        "pwp-pending-0123456789abcdef0123456789abcdef", "pwp-stage-0123456789abcdef0123456789abcdef"};
    for (size_t i = 0; i < sizeof(reserved)/sizeof(reserved[0]); ++i) {
        size_t count = wide(reserved[i], name);
        assert(!pwp_candidate_target(name, count, 0) && !pwp_candidate_target(name, count, 1));
    }
}
static void null_candidate(void) {
    fixture f = prepared_fixture(1);
    assert(pwp_candidate_rename_new(NULL, before_rename, rename_once, after_rename, flush_renamed, &f) == PWP_ARGUMENT);
    assert(pwp_candidate_rename_new(NULL, NULL, NULL, NULL, NULL, NULL) == PWP_ARGUMENT);
    assert(!f.calls && f.candidate.phase == PWP_CANDIDATE_VERIFIED && f.candidate.prepared_size == 1);
}
static void wrong_phases(void) {
    const pwp_candidate_phase phases[] = {PWP_CANDIDATE_EMPTY, PWP_CANDIDATE_OWNED,
        PWP_CANDIDATE_FILLING, PWP_CANDIDATE_FAILED, PWP_CANDIDATE_RENAMING,
        PWP_CANDIDATE_RENAMED, PWP_CANDIDATE_UNCERTAIN, (pwp_candidate_phase)99, (pwp_candidate_phase)-1};
    for (size_t i = 0; i < sizeof(phases)/sizeof(phases[0]); ++i) {
        fixture f = prepared_fixture(7); f.candidate.phase = phases[i];
        assert(run_rename(&f) == PWP_CLOSED && !f.calls);
        assert(f.candidate.phase == phases[i] && f.candidate.prepared_size == 7);
        f.candidate.prepared_size = SIZE_MAX;
        assert(run_rename(&f) == PWP_CLOSED && !f.calls);
        assert(f.candidate.phase == phases[i] && f.candidate.prepared_size == SIZE_MAX);
    }
}
static void invalid_callbacks_preserve_verified(void) {
    const size_t counts[] = {0, 1, PWP_RECORD_LIMIT};
    for (size_t i = 0; i < sizeof(counts)/sizeof(counts[0]); ++i) for (unsigned which = 0; which < 4; ++which) {
        fixture f = prepared_fixture(counts[i]);
        assert(pwp_candidate_rename_new(&f.candidate, which == 0 ? NULL : before_rename,
            which == 1 ? NULL : rename_once, which == 2 ? NULL : after_rename,
            which == 3 ? NULL : flush_renamed, &f) == PWP_ARGUMENT);
        assert(!f.calls && f.candidate.phase == PWP_CANDIDATE_VERIFIED && f.candidate.prepared_size == counts[i]);
        assert(run_rename(&f) == PWP_OK && f.calls == 5);
    }
}
static void corrupted_count_is_terminal(void) {
    const size_t counts[] = {(size_t)PWP_RECORD_LIMIT+1, SIZE_MAX};
    for (size_t i = 0; i < sizeof(counts)/sizeof(counts[0]); ++i) {
        fixture f = prepared_fixture(counts[i]);
        assert(run_rename(&f) == PWP_ARGUMENT && !f.calls);
        no_repeat(&f, PWP_CANDIDATE_FAILED);
        assert(pwp_candidate_close_ok(&f.candidate, 1));
        f = prepared_fixture(counts[i]);
        assert(pwp_candidate_rename_new(&f.candidate, NULL, NULL, NULL, NULL, NULL) == PWP_ARGUMENT);
        assert(f.candidate.phase == PWP_CANDIDATE_FAILED && !f.calls);
    }
}
static void success_order_and_size_boundaries(void) {
    const size_t counts[] = {0, 1, 4095, 4096, 4097, 65535, 65536, 65537, PWP_RECORD_LIMIT-1, PWP_RECORD_LIMIT};
    const unsigned order[] = {BEFORE, RENAME, AFTER, FLUSH, AFTER};
    for (size_t i = 0; i < sizeof(counts)/sizeof(counts[0]); ++i) {
        fixture f = prepared_fixture(counts[i]);
        assert(run_rename(&f) == PWP_OK && f.candidate.phase == PWP_CANDIDATE_RENAMED);
        assert(f.calls == 5 && !memcmp(f.trace, order, sizeof(order)) && f.name_changed);
        assert(f.befores == 1 && f.renames == 1 && f.afters == 2 && f.flushes == 1);
        assert(f.candidate.prepared_size == counts[i] && pwp_candidate_close_ok(&f.candidate, 1));
    }
}
static void preverification_failure_does_not_attempt(void) {
    fixture f = prepared_fixture(7); f.fail_before = 1;
    assert(run_rename(&f) == PWP_POLICY && f.calls == 1 && f.trace[0] == BEFORE);
    assert(!f.renames && !f.afters && !f.flushes && !f.name_changed);
    no_repeat(&f, PWP_CANDIDATE_FAILED);
    assert(pwp_candidate_close_ok(&f.candidate, 1));
}
static void rename_failure_is_ambiguous(void) {
    for (int changed = 0; changed <= 1; ++changed) {
        fixture f = prepared_fixture(7); f.fail_rename = 1; f.failed_rename_changes_name = changed;
        assert(run_rename(&f) == PWP_CLEANUP_UNKNOWN && f.calls == 2);
        assert(f.befores == 1 && f.renames == 1 && !f.afters && !f.flushes && f.name_changed == changed);
        no_repeat(&f, PWP_CANDIDATE_UNCERTAIN);
        assert(!pwp_candidate_close_ok(&f.candidate, 1));
    }
}
static void first_readback_failure(void) {
    fixture f = prepared_fixture(7); f.fail_after = 1;
    assert(run_rename(&f) == PWP_CLEANUP_UNKNOWN && f.calls == 3 && f.afters == 1 && !f.flushes);
    assert(f.name_changed); no_repeat(&f, PWP_CANDIDATE_UNCERTAIN);
}
static void flush_failure(void) {
    fixture f = prepared_fixture(7); f.fail_flush = 1;
    assert(run_rename(&f) == PWP_CLEANUP_UNKNOWN && f.calls == 4 && f.afters == 1 && f.flushes == 1);
    assert(f.name_changed); no_repeat(&f, PWP_CANDIDATE_UNCERTAIN);
}
static void final_readback_failure(void) {
    fixture f = prepared_fixture(7); f.fail_after = 2;
    assert(run_rename(&f) == PWP_CLEANUP_UNKNOWN && f.calls == 5 && f.afters == 2 && f.flushes == 1);
    assert(f.name_changed); no_repeat(&f, PWP_CANDIDATE_UNCERTAIN);
}
static void callback_reentry_keeps_original_operation(void) {
    for (unsigned mask = 1; mask <= 31; ++mask) {
        fixture f = prepared_fixture(7); f.reenter = mask;
        assert(run_rename(&f) == PWP_OK && f.calls == 5);
        no_repeat(&f, PWP_CANDIDATE_RENAMED);
    }
}
static void renamed_result_never_repeats(void) {
    fixture f = prepared_fixture(7);
    assert(run_rename(&f) == PWP_OK);
    no_repeat(&f, PWP_CANDIDATE_RENAMED);
    assert(pwp_candidate_close_ok(&f.candidate, 1) && !pwp_candidate_close_ok(&f.candidate, 0));
    assert(f.candidate.phase == PWP_CANDIDATE_RENAMED && f.candidate.prepared_size == 7);
}
static void close_result_matrix(void) {
    const pwp_candidate_phase phases[] = {PWP_CANDIDATE_EMPTY, PWP_CANDIDATE_OWNED,
        PWP_CANDIDATE_FILLING, PWP_CANDIDATE_VERIFIED, PWP_CANDIDATE_FAILED,
        PWP_CANDIDATE_RENAMING, PWP_CANDIDATE_RENAMED, PWP_CANDIDATE_UNCERTAIN,
        (pwp_candidate_phase)99, (pwp_candidate_phase)-1};
    const int outcomes[] = {-1, 0, 1, 2};
    for (size_t i = 0; i < sizeof(phases)/sizeof(phases[0]); ++i) {
        pwp_candidate candidate = {phases[i], 17};
        int stable = phases[i] == PWP_CANDIDATE_OWNED || phases[i] == PWP_CANDIDATE_VERIFIED ||
            phases[i] == PWP_CANDIDATE_FAILED || phases[i] == PWP_CANDIDATE_RENAMED;
        for (size_t j = 0; j < sizeof(outcomes)/sizeof(outcomes[0]); ++j) {
            assert(pwp_candidate_close_ok(&candidate, outcomes[j]) == (stable && outcomes[j] == 1));
            assert(candidate.phase == phases[i] && candidate.prepared_size == 17);
            assert(!pwp_candidate_close_ok(NULL, outcomes[j]));
        }
    }
}
static int empty_write(const unsigned char *bytes, size_t count, size_t *written, void *opaque) {
    (void)bytes; (void)count; (void)written; (void)opaque;
    assert(0); return 0;
}
static int empty_action(void *opaque) {
    pwp_candidate *candidate = opaque;
    assert(candidate->phase == PWP_CANDIDATE_FILLING && !candidate->prepared_size);
    return 1;
}
static int empty_verify(size_t count, void *opaque) {
    assert(!count); return empty_action(opaque);
}
static int empty_eof(unsigned char *bytes, size_t count, size_t *actual, void *opaque) {
    assert(bytes && count == 1 && actual && empty_action(opaque));
    *actual = 0; return 1;
}
static void prepare_empty(pwp_candidate *candidate) {
    memset(candidate, 0, sizeof(*candidate));
    assert(pwp_candidate_init(candidate) == PWP_OK);
    assert(pwp_candidate_fill(candidate, NULL, 0, empty_write, empty_action, empty_action,
        empty_eof, empty_verify, candidate) == PWP_OK);
    assert(candidate->phase == PWP_CANDIDATE_VERIFIED && !candidate->prepared_size);
}
static void actual_fill_then_rename(void) {
    fixture f = {0}; prepare_empty(&f.candidate);
    assert(run_rename(&f) == PWP_OK && f.candidate.phase == PWP_CANDIDATE_RENAMED);
    assert(f.calls == 5 && !f.candidate.prepared_size);
}

typedef struct {
    pwp_owner owner;
    pwp_roles roles;
    fixture subject;
    uint64_t root, profile, identity, vault, independent, candidate;
    unsigned closes[16], order[16], close_count;
    int os_closed;
} ownership;
static uintptr_t resource(uint64_t token) { return (uintptr_t)(0x10000u+token); }
static uint64_t publish_owner(ownership *f) {
    uint64_t token = 0;
    assert(pwp_reserve(&f->owner, &token) == PWP_OK && token < 16);
    assert(pwp_attach(&f->owner, token, resource(token)) == PWP_OK);
    assert(pwp_publish(&f->owner, token) == PWP_OK);
    return token;
}
static int physical_close_once(uintptr_t value, void *opaque) {
    ownership *f = opaque;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        pwp_owned_handle *handle = &f->owner.slots[i];
        if (handle->resource != value || handle->state != 4) continue;
        uint64_t token = handle->token;
        assert(token && token < 16 && value == resource(token));
        assert(++f->closes[token] == 1 && f->close_count < 16);
        f->order[f->close_count++] = (unsigned)token;
        /* This models the outcome AFTER a physical close attempt, never a reason to skip it. */
        if (token == f->candidate) return pwp_candidate_close_ok(&f->subject.candidate, f->os_closed);
        return 1;
    }
    assert(0); return 0;
}
static pwp_role_stage *candidate_grant(ownership *f) {
    for (size_t i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i)
        if (f->roles.stages[i].token == f->candidate) return &f->roles.stages[i];
    return NULL;
}
static void initialize_ownership(ownership *f) {
    memset(f, 0, sizeof(*f)); f->os_closed = 1;
    pwp_owner_init(&f->owner); pwp_roles_init(&f->roles);
    assert(pwp_roles_begin_root(&f->roles, &f->owner) == PWP_OK);
    f->root = publish_owner(f);
    assert(pwp_roles_bind_root(&f->roles, &f->owner, f->root) == PWP_OK);
    f->profile = publish_owner(f);
    assert(pwp_roles_bind_lease(&f->roles, &f->owner, f->root, PWP_LEASE_PROFILE, f->profile) == PWP_OK);
    f->identity = publish_owner(f);
    assert(pwp_roles_bind_identity(&f->roles, &f->owner, f->root, f->identity) == PWP_OK);
    f->vault = publish_owner(f);
    assert(pwp_roles_bind_lease(&f->roles, &f->owner, f->identity, PWP_LEASE_VAULT, f->vault) == PWP_OK);
    pwp_role_grant independent;
    assert(pwp_roles_capture(&f->roles, &f->owner, f->root, &independent) == PWP_OK);
    f->independent = publish_owner(f);
    assert(pwp_roles_bind_stage(&f->roles, &f->owner, f->independent, &independent) == PWP_OK);
    f->candidate = publish_owner(f);
    prepare_empty(&f->subject.candidate);
    f->subject.owner = &f->owner; f->subject.roles = &f->roles; f->subject.token = f->candidate;
    assert(pwp_roles_capture(&f->roles, &f->owner, f->identity, &f->subject.grant) == PWP_OK);
    assert(pwp_roles_bind_stage(&f->roles, &f->owner, f->candidate, &f->subject.grant) == PWP_OK);
    assert(f->candidate == 6 && candidate_grant(f));
}
static void all_original_closes_once(const ownership *f) {
    assert(f->close_count == 6);
    for (uint64_t token = 1; token <= f->candidate; ++token) assert(f->closes[token] == 1);
}
static void assert_quarantine(ownership *f) {
    pwp_owned_handle *handle = pwp_lookup(&f->owner, f->candidate);
    pwp_role_stage *grant = candidate_grant(f);
    assert(f->owner.poisoned && handle && handle->state == 4 && handle->published);
    assert(handle->resource == resource(f->candidate) && grant);
    assert(!memcmp(&grant->grant, &f->subject.grant, sizeof(grant->grant)));
}
static void renamed_owner_retains_grant_until_close(void) {
    ownership f; initialize_ownership(&f);
    assert(run_rename(&f.subject) == PWP_OK && !f.owner.poisoned && !f.close_count);
    assert(pwp_roles_check_stage(&f.roles, &f.owner, f.candidate) == PWP_OK);
    assert(pwp_roles_retire(&f.roles, &f.owner, f.profile, physical_close_once, &f) == PWP_BUSY);
    assert(pwp_roles_retire(&f.roles, &f.owner, f.vault, physical_close_once, &f) == PWP_BUSY);
    assert(pwp_roles_retire(&f.roles, &f.owner, f.identity, physical_close_once, &f) == PWP_BUSY);
    assert(!f.close_count && pwp_lookup(&f.owner, f.candidate)->state == 2);
    assert(pwp_roles_retire(&f.roles, &f.owner, f.candidate, physical_close_once, &f) == PWP_OK);
    assert(!candidate_grant(&f) && f.close_count == 1 && !f.owner.poisoned);
    assert(f.subject.candidate.phase == PWP_CANDIDATE_RENAMED);
    assert(pwp_roles_retire(&f.roles, &f.owner, f.candidate, physical_close_once, &f) == PWP_OK);
    assert(f.close_count == 1);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, physical_close_once, &f) == PWP_OK);
    all_original_closes_once(&f);
    assert(!f.roles.root && !f.roles.profile && !f.roles.vault && !f.owner.poisoned);
}
static void uncertain_explicit_close_retains_grant(void) {
    ownership f; initialize_ownership(&f); f.subject.fail_after = 1;
    assert(run_rename(&f.subject) == PWP_CLEANUP_UNKNOWN && !f.close_count);
    /* Native wrapper must seal on the returned uncertainty; the pure controller owns no session. */
    f.owner.poisoned = 1;
    assert(pwp_roles_retire(&f.roles, &f.owner, f.profile, physical_close_once, &f) == PWP_CLEANUP_UNKNOWN);
    assert(!f.close_count);
    assert(pwp_roles_retire(&f.roles, &f.owner, f.candidate, physical_close_once, &f) == PWP_CLEANUP_UNKNOWN);
    assert(f.os_closed == 1 && f.closes[f.candidate] == 1); assert_quarantine(&f);
    assert(pwp_roles_retire(&f.roles, &f.owner, f.candidate, physical_close_once, &f) == PWP_CLEANUP_UNKNOWN);
    assert(f.close_count == 1);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, physical_close_once, &f) == PWP_CLEANUP_UNKNOWN);
    all_original_closes_once(&f); assert_quarantine(&f);
    assert(f.closes[f.independent] == 1 && f.roles.root == f.root && f.roles.profile == f.profile);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, physical_close_once, &f) == PWP_CLEANUP_UNKNOWN);
    all_original_closes_once(&f);
    assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_CLEANUP_UNKNOWN);
}
static void uncertain_root_drain_does_not_skip_independents(void) {
    ownership f; initialize_ownership(&f); f.subject.fail_rename = 1;
    assert(run_rename(&f.subject) == PWP_CLEANUP_UNKNOWN);
    f.owner.poisoned = 1;
    assert(pwp_roles_retire_all(&f.roles, &f.owner, physical_close_once, &f) == PWP_CLEANUP_UNKNOWN);
    all_original_closes_once(&f); assert_quarantine(&f);
    for (unsigned i = 0; i < f.close_count; ++i) assert(f.order[i] == 6-i);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, physical_close_once, &f) == PWP_CLEANUP_UNKNOWN);
    all_original_closes_once(&f);
}
static void failed_physical_close_after_confirmed_rename(void) {
    ownership f; initialize_ownership(&f);
    assert(run_rename(&f.subject) == PWP_OK); f.os_closed = 0;
    assert(pwp_roles_retire(&f.roles, &f.owner, f.candidate, physical_close_once, &f) == PWP_CLEANUP_UNKNOWN);
    assert_quarantine(&f); assert(f.closes[f.candidate] == 1);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, physical_close_once, &f) == PWP_CLEANUP_UNKNOWN);
    all_original_closes_once(&f); assert_quarantine(&f);
}
static void preverification_failed_owner_can_retire_only(void) {
    ownership f; initialize_ownership(&f); f.subject.fail_before = 1;
    assert(run_rename(&f.subject) == PWP_POLICY && !f.subject.renames && !f.close_count);
    no_repeat(&f.subject, PWP_CANDIDATE_FAILED);
    assert(pwp_roles_retire(&f.roles, &f.owner, f.candidate, physical_close_once, &f) == PWP_OK);
    assert(!f.owner.poisoned && !candidate_grant(&f));
    assert(pwp_roles_retire_all(&f.roles, &f.owner, physical_close_once, &f) == PWP_OK);
    all_original_closes_once(&f);
}
static void changed_grant_rejects_before_attempt(void) {
    ownership f; initialize_ownership(&f);
    /* Adversarial ledger mutation models a stale grant; normal role retirement forbids this change. */
    candidate_grant(&f)->grant.profile = 0;
    assert(pwp_roles_check_stage(&f.roles, &f.owner, f.candidate) == PWP_POLICY);
    assert(run_rename(&f.subject) == PWP_POLICY && f.subject.calls == 1 && !f.subject.renames);
    no_repeat(&f.subject, PWP_CANDIDATE_FAILED);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, physical_close_once, &f) == PWP_OK);
    all_original_closes_once(&f);
}
int main(void) {
    root_target(); identity_target(); target_lengths_and_scopes(); null_candidate(); wrong_phases();
    invalid_callbacks_preserve_verified(); corrupted_count_is_terminal(); success_order_and_size_boundaries();
    preverification_failure_does_not_attempt(); rename_failure_is_ambiguous(); first_readback_failure();
    flush_failure(); final_readback_failure(); callback_reentry_keeps_original_operation();
    renamed_result_never_repeats(); close_result_matrix(); actual_fill_then_rename();
    renamed_owner_retains_grant_until_close(); uncertain_explicit_close_retains_grant();
    uncertain_root_drain_does_not_skip_independents(); failed_physical_close_after_confirmed_rename();
    preverification_failed_owner_can_retire_only(); changed_grant_rejects_before_attempt();
    puts("23 portable create-only rename/owner groups PASS; NOT Windows OS or durable-publication qualification");
    return 0;
}
