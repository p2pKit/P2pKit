/* Portable controller/owner controls only. They do not emulate Windows metadata, sharing, atomic rename
 * or crash durability. Native callbacks must independently prove the real file/ACL/lease predicates. */
#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

enum { BEFORE = 1, TARGET_VERIFY, TARGET_CLOSE, RENAME, AFTER, FLUSH };
typedef struct {
    pwp_owner owner;
    pwp_roles roles;
    pwp_candidate candidate;
    pwp_role_grant grant;
    uint64_t root, profile, identity, vault, independent, source, target, reused;
    uint64_t expected_source_id, observed_source_id, target_id;
    size_t expected_count;
    unsigned calls, trace[16], befores, targets, closes, renames, afters, flushes, reenter;
    unsigned fail_before, fail_after, change_grant_at, poison_at, change_source_at;
    unsigned physical_closes[32], close_order[32], close_count;
    int fail_target, fail_close, fail_rename, fail_flush, fail_candidate_close;
    int replace_seen, name_changed, failed_rename_changes_name, reused_slot;
} fixture;
static int before(size_t count, void *opaque);
static int verify_target(void *opaque);
static int close_target(uintptr_t resource, void *opaque);
static int rename_target(int replace, void *opaque);
static int after(size_t count, void *opaque);
static int flush(void *opaque);
static pwp_result apply(fixture *f) {
    return pwp_candidate_replace(&f->candidate, &f->owner, f->target, before, verify_target,
                                 close_target, rename_target, after, flush, f);
}
static uintptr_t resource(uint64_t token) { return (uintptr_t)(0x10000u+token); }
static uint64_t own(fixture *f, int publish) {
    uint64_t token = 0;
    assert(pwp_reserve(&f->owner, &token) == PWP_OK && token < 32);
    assert(pwp_attach(&f->owner, token, resource(token)) == PWP_OK);
    if (publish) assert(pwp_publish(&f->owner, token) == PWP_OK);
    return token;
}
static void initialize(fixture *f, int existing, size_t size) {
    memset(f, 0, sizeof(*f)); pwp_owner_init(&f->owner); pwp_roles_init(&f->roles);
    assert(pwp_roles_begin_root(&f->roles, &f->owner) == PWP_OK);
    f->root = own(f, 1);
    assert(pwp_roles_bind_root(&f->roles, &f->owner, f->root) == PWP_OK);
    f->profile = own(f, 1);
    assert(pwp_roles_bind_lease(&f->roles, &f->owner, f->root, PWP_LEASE_PROFILE, f->profile) == PWP_OK);
    f->identity = own(f, 1);
    assert(pwp_roles_bind_identity(&f->roles, &f->owner, f->root, f->identity) == PWP_OK);
    f->vault = own(f, 1);
    assert(pwp_roles_bind_lease(&f->roles, &f->owner, f->identity, PWP_LEASE_VAULT, f->vault) == PWP_OK);
    f->independent = own(f, 1);
    pwp_role_grant root_grant;
    assert(pwp_roles_capture(&f->roles, &f->owner, f->root, &root_grant) == PWP_OK);
    assert(pwp_roles_bind_stage(&f->roles, &f->owner, f->independent, &root_grant) == PWP_OK);
    f->source = own(f, 1);
    assert(pwp_roles_capture(&f->roles, &f->owner, f->identity, &f->grant) == PWP_OK);
    assert(pwp_roles_bind_stage(&f->roles, &f->owner, f->source, &f->grant) == PWP_OK);
    if (existing) f->target = own(f, 0);
    f->candidate.phase = PWP_CANDIDATE_VERIFIED; f->candidate.prepared_size = size;
    f->expected_count = size; f->expected_source_id = f->observed_source_id = 21;
    f->target_id = 22; f->replace_seen = -1;
    assert(f->source == 6 && f->target == (existing ? 7u : 0u));
}
static int original_authority(const fixture *f) {
    if (pwp_roles_check_grant(&f->roles, &f->owner, &f->grant) != PWP_OK ||
        pwp_roles_check_stage(&f->roles, &f->owner, f->source) != PWP_OK) return 0;
    const uint64_t retained[] = {f->root, f->profile, f->identity, f->vault, f->source};
    for (size_t i = 0; i < sizeof(retained)/sizeof(retained[0]); ++i) {
        uint64_t token = retained[i];
        const pwp_owned_handle *held = NULL;
        for (size_t j = 0; j < PWP_HANDLE_LIMIT; ++j)
            if (f->owner.slots[j].token == token) held = &f->owner.slots[j];
        if (!held || held->state != 2 || !held->published || held->resource != resource(token) ||
            f->physical_closes[token]) return 0;
    }
    return 1;
}
static void observe(fixture *f, unsigned event) {
    assert(f->candidate.phase == PWP_CANDIDATE_RENAMING);
    assert(f->candidate.prepared_size == f->expected_count && f->calls < 16);
    f->trace[f->calls++] = event;
    if (f->reenter & (1u << (f->calls-1))) {
        unsigned calls = f->calls;
        assert(apply(f) == PWP_CLOSED && f->calls == calls);
        assert(pwp_candidate_rename_new(&f->candidate, NULL, NULL, NULL, NULL, f) == PWP_CLOSED);
        assert(pwp_candidate_init(&f->candidate) == PWP_CLOSED && !pwp_candidate_close_ok(&f->candidate, 1));
    }
}
static int before(size_t count, void *opaque) {
    fixture *f = opaque; observe(f, BEFORE); ++f->befores;
    assert(count == f->expected_count && f->befores <= 2 && !f->renames);
    if (f->befores == 2 && f->target) {
        assert(f->targets == 1 && f->closes == 1 && !f->fail_close);
        if (f->reused_slot) {
            /* Real source verification can reserve a thread-token slot after target close. Prove the
             * controller never dereferences its former owner pointer or looks up the consumed token. */
            pwp_owned_handle *old = pwp_lookup(&f->owner, f->target);
            assert(old && old->state == 3);
            f->reused = own(f, 0);
            assert(pwp_lookup(&f->owner, f->reused) == old && !pwp_lookup(&f->owner, f->target));
        }
    }
    if (f->change_grant_at == f->befores) ++f->grant.vault;
    if (f->change_source_at == f->befores) ++f->observed_source_id;
    if (f->poison_at == f->befores) f->owner.poisoned = 1;
    return f->fail_before != f->befores && f->expected_source_id == f->observed_source_id && original_authority(f);
}
static int verify_target(void *opaque) {
    fixture *f = opaque; observe(f, TARGET_VERIFY); ++f->targets;
    pwp_owned_handle *held = pwp_lookup(&f->owner, f->target);
    assert(f->target && f->befores == 1 && f->targets == 1 && !f->closes);
    assert(held && held->state == 2 && !held->published && held->resource == resource(f->target));
    return !f->fail_target && f->target_id != f->observed_source_id && original_authority(f);
}
static void record_close(fixture *f, uint64_t token) {
    assert(token && token < 32 && f->close_count < 32 && ++f->physical_closes[token] == 1);
    f->close_order[f->close_count++] = (unsigned)token;
}
static int close_target(uintptr_t value, void *opaque) {
    fixture *f = opaque; observe(f, TARGET_CLOSE); ++f->closes;
    pwp_owned_handle *held = pwp_lookup(&f->owner, f->target);
    assert(f->target && f->befores == 1 && f->closes == 1 && !f->renames);
    assert(held && held->state == 4 && !held->published && value == resource(f->target));
    record_close(f, f->target);
    assert(pwp_retire(&f->owner, f->target, close_target, f) == PWP_CLEANUP_UNKNOWN);
    return !f->fail_close;
}
static int rename_target(int replace, void *opaque) {
    fixture *f = opaque; observe(f, RENAME); ++f->renames;
    assert(f->befores == 2 && f->renames == 1 && !f->afters && !f->flushes);
    assert(replace == (f->target != 0) && f->closes == (unsigned)(f->target != 0));
    assert(original_authority(f)); f->replace_seen = replace;
    if (!f->fail_rename || f->failed_rename_changes_name) f->name_changed = 1;
    return !f->fail_rename;
}
static int after(size_t count, void *opaque) {
    fixture *f = opaque; observe(f, AFTER); ++f->afters;
    assert(count == f->expected_count && f->name_changed && f->renames == 1 && f->afters <= 2);
    assert(f->flushes == f->afters-1);
    return f->fail_after != f->afters && original_authority(f);
}
static int flush(void *opaque) {
    fixture *f = opaque; observe(f, FLUSH); ++f->flushes;
    assert(f->renames == 1 && f->afters == 1 && f->flushes == 1 && f->name_changed);
    return !f->fail_flush && original_authority(f);
}
static int close_original(uintptr_t value, void *opaque) {
    fixture *f = opaque;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        pwp_owned_handle *held = &f->owner.slots[i];
        if (held->state != 4 || held->resource != value) continue;
        uint64_t token = held->token;
        assert(value == resource(token)); record_close(f, token);
        return token == f->source ? pwp_candidate_close_ok(&f->candidate, !f->fail_candidate_close) : 1;
    }
    assert(0); return 0;
}
static void no_retry(fixture *f, pwp_candidate_phase phase) {
    unsigned calls = f->calls;
    assert(f->candidate.phase == phase && apply(f) == PWP_CLOSED && f->calls == calls);
    assert(pwp_candidate_rename_new(&f->candidate, NULL, NULL, NULL, NULL, f) == PWP_CLOSED);
    assert(f->candidate.prepared_size == f->expected_count);
}
static void clean_drain(fixture *f) {
    assert(pwp_roles_retire_all(&f->roles, &f->owner, close_original, f) == PWP_OK);
    assert(!f->owner.poisoned && !f->roles.root);
    unsigned count = f->target ? 7 : 6;
    if (f->reused) ++count;
    assert(f->close_count == count);
    for (unsigned i = 1; i <= count; ++i) assert(f->physical_closes[i] == 1);
}
static size_t wide(const char *text, uint16_t *name) {
    size_t count = strlen(text);
    for (size_t i = 0; i < count; ++i) name[i] = (unsigned char)text[i];
    return count;
}
static void identity_target_scope_only(void) {
    uint16_t name[96] = {0};
    size_t count = wide("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.aesgcm", name);
    assert(count == 71 && pwp_candidate_replace_target(name, count, 1));
    const int invalid_scopes[] = {-1, 0, 2, 99};
    for (size_t i = 0; i < sizeof(invalid_scopes)/sizeof(invalid_scopes[0]); ++i)
        assert(!pwp_candidate_replace_target(name, count, invalid_scopes[i]));
    assert(!pwp_candidate_replace_target(NULL, count, 1));
    for (size_t size = 0; size <= 96; ++size)
        assert(pwp_candidate_replace_target(name, size, 1) == (size == count));
    assert(!pwp_candidate_replace_target(name, SIZE_MAX, 1));
}
static void malformed_and_reserved_targets(void) {
    uint16_t name[96] = {0};
    size_t count = wide("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.aesgcm", name);
    const uint16_t invalid[] = {'A', 'F', 'g', '/', '\\', ':', '.', 0, 0xd800, 0xffff};
    for (size_t i = 0; i < count; ++i) {
        uint16_t saved = name[i];
        for (size_t j = 0; j < sizeof(invalid)/sizeof(invalid[0]); ++j) if (saved != invalid[j]) {
            name[i] = invalid[j]; assert(!pwp_candidate_replace_target(name, count, 1));
        }
        name[i] = saved;
    }
    const char *reserved[] = {"profile.header", "profile.lock", "vault.lock", "identity",
        "pwp-pending-0123456789abcdef0123456789abcdef", "pwp-stage-0123456789abcdef0123456789abcdef"};
    for (size_t i = 0; i < sizeof(reserved)/sizeof(reserved[0]); ++i) {
        count = wide(reserved[i], name);
        assert(!pwp_candidate_replace_target(name, count, 0) && !pwp_candidate_replace_target(name, count, 1));
    }
}
static void null_arguments_retain_probe(void) {
    fixture f; initialize(&f, 1, 1);
    assert(pwp_candidate_replace(NULL, &f.owner, f.target, before, verify_target,
                                 close_target, rename_target, after, flush, &f) == PWP_ARGUMENT);
    assert(pwp_candidate_replace(&f.candidate, NULL, f.target, before, verify_target,
                                 close_target, rename_target, after, flush, &f) == PWP_ARGUMENT);
    assert(!f.calls && pwp_lookup(&f.owner, f.target)->state == 2);
    assert(f.candidate.phase == PWP_CANDIDATE_VERIFIED); clean_drain(&f);
}
static void missing_callbacks_retain_probe(void) {
    for (int existing = 0; existing <= 1; ++existing) for (unsigned which = 0; which < 6; ++which) {
        fixture f; initialize(&f, existing, 1);
        assert(pwp_candidate_replace(&f.candidate, &f.owner, f.target, which == 0 ? NULL : before,
            which == 1 ? NULL : verify_target, which == 2 ? NULL : close_target,
            which == 3 ? NULL : rename_target, which == 4 ? NULL : after,
            which == 5 ? NULL : flush, &f) == PWP_ARGUMENT);
        assert(!f.calls && f.candidate.phase == PWP_CANDIDATE_VERIFIED);
        if (existing) assert(pwp_lookup(&f.owner, f.target)->state == 2);
        clean_drain(&f);
    }
}
static void nonverified_states_never_adopt_probe(void) {
    const pwp_candidate_phase phases[] = {PWP_CANDIDATE_EMPTY, PWP_CANDIDATE_OWNED, PWP_CANDIDATE_FILLING,
        PWP_CANDIDATE_FAILED, PWP_CANDIDATE_RENAMING, PWP_CANDIDATE_RENAMED, PWP_CANDIDATE_UNCERTAIN,
        (pwp_candidate_phase)-1, (pwp_candidate_phase)99};
    for (size_t i = 0; i < sizeof(phases)/sizeof(phases[0]); ++i) {
        fixture f; initialize(&f, 1, 1); f.candidate.phase = phases[i];
        assert(apply(&f) == PWP_CLOSED && !f.calls && f.candidate.phase == phases[i]);
        assert(pwp_lookup(&f.owner, f.target)->state == 2 && !f.physical_closes[f.target]);
    }
}
static void corrupt_sizes_are_terminal_without_adoption(void) {
    const size_t sizes[] = {(size_t)PWP_RECORD_LIMIT+1, SIZE_MAX};
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
        fixture f; initialize(&f, 1, sizes[i]);
        assert(apply(&f) == PWP_ARGUMENT && !f.calls);
        assert(pwp_lookup(&f.owner, f.target)->state == 2); no_retry(&f, PWP_CANDIDATE_FAILED);
        clean_drain(&f);
    }
}
static void only_fresh_unpublished_targets_are_adopted(void) {
    for (unsigned which = 0; which < 7; ++which) {
        fixture f; initialize(&f, 1, 1); uint64_t supplied = f.target;
        pwp_owned_handle *held = pwp_lookup(&f.owner, f.target);
        if (which == 0) supplied = UINT64_MAX;
        if (which == 1) supplied = 1000;
        if (which == 2) held->state = 1;
        if (which == 3) held->state = 3;
        if (which == 4) held->state = 4;
        if (which == 5) held->resource = 0;
        if (which == 6) assert(pwp_publish(&f.owner, f.target) == PWP_OK);
        assert(pwp_candidate_replace(&f.candidate, &f.owner, supplied, before, verify_target,
                                     close_target, rename_target, after, flush, &f) == PWP_ARGUMENT);
        assert(!f.calls && !f.close_count && f.candidate.phase == PWP_CANDIDATE_VERIFIED);
    }
    fixture f; initialize(&f, 1, 1);
    const uint64_t borrowed[] = {f.root, f.profile, f.identity, f.vault, f.independent, f.source};
    for (size_t i = 0; i < sizeof(borrowed)/sizeof(borrowed[0]); ++i)
        assert(pwp_candidate_replace(&f.candidate, &f.owner, borrowed[i], before, verify_target,
                                     close_target, rename_target, after, flush, &f) == PWP_ARGUMENT);
    assert(!f.calls && original_authority(&f)); clean_drain(&f);
}
static void preexisting_poison_never_adopts_probe(void) {
    fixture f; initialize(&f, 1, 1); f.owner.poisoned = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.calls);
    assert(f.candidate.phase == PWP_CANDIDATE_VERIFIED && pwp_lookup(&f.owner, f.target)->state == 2);
}
static void existing_target_success_order(void) {
    const size_t sizes[] = {0, 1, 4096, 4097, 65536, PWP_RECORD_LIMIT};
    const unsigned order[] = {BEFORE, TARGET_VERIFY, TARGET_CLOSE, BEFORE, RENAME, AFTER, FLUSH, AFTER};
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
        fixture f; initialize(&f, 1, sizes[i]);
        assert(apply(&f) == PWP_OK && f.calls == 8 && !memcmp(f.trace, order, sizeof(order)));
        assert(f.replace_seen == 1 && f.targets == 1 && f.closes == 1 && f.name_changed);
        assert(original_authority(&f) && f.close_count == 1 && pwp_lookup(&f.owner, f.target)->state == 3);
        no_retry(&f, PWP_CANDIDATE_RENAMED); clean_drain(&f);
    }
}
static void absent_target_is_create_only(void) {
    fixture f; initialize(&f, 0, 4097);
    const unsigned order[] = {BEFORE, BEFORE, RENAME, AFTER, FLUSH, AFTER};
    assert(apply(&f) == PWP_OK && f.calls == 6 && !memcmp(f.trace, order, sizeof(order)));
    assert(!f.targets && !f.closes && f.replace_seen == 0 && !f.close_count && original_authority(&f));
    no_retry(&f, PWP_CANDIDATE_RENAMED); clean_drain(&f);
}
static void preverification_refusal_still_retires_probe(void) {
    fixture f; initialize(&f, 1, 1); f.fail_before = 1;
    const unsigned order[] = {BEFORE, TARGET_CLOSE};
    assert(apply(&f) == PWP_POLICY && f.calls == 2 && !memcmp(f.trace, order, sizeof(order)));
    assert(!f.targets && f.closes == 1 && !f.renames && !f.name_changed && original_authority(&f));
    no_retry(&f, PWP_CANDIDATE_FAILED); clean_drain(&f);
}
static void unsafe_target_refusal_still_retires_probe(void) {
    fixture f; initialize(&f, 1, 1); f.fail_target = 1;
    const unsigned order[] = {BEFORE, TARGET_VERIFY, TARGET_CLOSE};
    assert(apply(&f) == PWP_POLICY && f.calls == 3 && !memcmp(f.trace, order, sizeof(order)));
    assert(f.befores == 1 && !f.renames && !f.name_changed && original_authority(&f));
    no_retry(&f, PWP_CANDIDATE_FAILED); clean_drain(&f);
}
static void same_identity_target_refuses_before_rename(void) {
    fixture f; initialize(&f, 1, 1); f.target_id = f.observed_source_id;
    assert(apply(&f) == PWP_POLICY && f.targets == 1 && f.closes == 1 && !f.renames);
    no_retry(&f, PWP_CANDIDATE_FAILED); clean_drain(&f);
}
static void target_close_uncertainty_never_renames(void) {
    for (unsigned refused = 0; refused < 3; ++refused) {
        fixture f; initialize(&f, 1, 1); f.fail_close = 1;
        f.fail_before = refused == 1 ? 1 : 0; f.fail_target = refused == 2;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.closes == 1 && !f.renames && !f.name_changed);
        assert(f.owner.poisoned && pwp_lookup(&f.owner, f.target)->state == 4);
        assert(pwp_lookup(&f.owner, f.source)->state == 2 && !f.physical_closes[f.source]);
        no_retry(&f, PWP_CANDIDATE_FAILED);
        assert(pwp_roles_retire_all(&f.roles, &f.owner, close_original, &f) == PWP_CLEANUP_UNKNOWN);
        assert(f.close_count == 7 && f.physical_closes[f.target] == 1);
        assert(pwp_roles_retire_all(&f.roles, &f.owner, close_original, &f) == PWP_CLEANUP_UNKNOWN);
        assert(f.close_count == 7 && f.physical_closes[f.source] == 1);
    }
}
static void revalidation_after_probe_close_is_required(void) {
    fixture f; initialize(&f, 1, 1); f.fail_before = 2;
    assert(apply(&f) == PWP_POLICY && f.calls == 4 && f.befores == 2 && f.closes == 1 && !f.renames);
    assert(!f.name_changed && original_authority(&f)); no_retry(&f, PWP_CANDIDATE_FAILED); clean_drain(&f);
}
static void changed_grants_or_source_block_namespace_attempt(void) {
    for (unsigned when = 1; when <= 2; ++when) for (int kind = 0; kind < 2; ++kind) {
        fixture f; initialize(&f, 1, 1);
        if (kind == 0) f.change_grant_at = when; else f.change_source_at = when;
        assert(apply(&f) == PWP_POLICY && f.befores == when && f.closes == 1 && !f.renames);
        no_retry(&f, PWP_CANDIDATE_FAILED); clean_drain(&f);
    }
}
static void new_owner_poison_blocks_namespace_attempt(void) {
    for (unsigned when = 1; when <= 2; ++when) {
        fixture f; initialize(&f, 1, 1); f.poison_at = when;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.befores == when && f.closes == 1 && !f.renames);
        assert(f.owner.poisoned && pwp_lookup(&f.owner, f.target)->state == 3);
        no_retry(&f, PWP_CANDIDATE_FAILED);
    }
}
static void retired_probe_slot_can_be_reused(void) {
    fixture f; initialize(&f, 1, 1); f.reused_slot = 1;
    assert(apply(&f) == PWP_OK && f.reused == 8 && f.replace_seen == 1 && f.closes == 1);
    assert(!pwp_lookup(&f.owner, f.target) && pwp_lookup(&f.owner, f.reused)->state == 2);
    assert(original_authority(&f)); clean_drain(&f);
}
static void rename_failure_never_falls_back(void) {
    for (int existing = 0; existing <= 1; ++existing) for (int changed = 0; changed <= 1; ++changed) {
        fixture f; initialize(&f, existing, 1); f.fail_rename = 1; f.failed_rename_changes_name = changed;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.renames == 1 && !f.afters && !f.flushes);
        assert(f.replace_seen == existing && f.name_changed == changed);
        no_retry(&f, PWP_CANDIDATE_UNCERTAIN);
        assert(!pwp_candidate_close_ok(&f.candidate, 1));
    }
}
static void postattempt_failures_remain_uncertain(void) {
    for (unsigned step = 0; step < 3; ++step) {
        fixture f; initialize(&f, 1, 1);
        if (step == 0) f.fail_after = 1;
        if (step == 1) f.fail_flush = 1;
        if (step == 2) f.fail_after = 2;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.name_changed && f.renames == 1);
        assert(f.calls == step+6 && f.close_count == 1 && pwp_lookup(&f.owner, f.source)->state == 2);
        no_retry(&f, PWP_CANDIDATE_UNCERTAIN);
    }
}
static void callbacks_cannot_reenter_the_candidate(void) {
    for (unsigned mask = 1; mask <= 255; ++mask) {
        fixture f; initialize(&f, 1, 1); f.reenter = mask;
        assert(apply(&f) == PWP_OK && f.calls == 8 && f.renames == 1 && f.closes == 1);
        no_retry(&f, PWP_CANDIDATE_RENAMED); clean_drain(&f);
    }
}
static void candidate_and_leases_remain_owned_until_real_close(void) {
    fixture f; initialize(&f, 1, 1);
    assert(apply(&f) == PWP_OK && f.close_count == 1 && original_authority(&f));
    assert(pwp_roles_retire(&f.roles, &f.owner, f.profile, close_original, &f) == PWP_BUSY);
    assert(pwp_roles_retire(&f.roles, &f.owner, f.vault, close_original, &f) == PWP_BUSY);
    assert(pwp_roles_retire(&f.roles, &f.owner, f.identity, close_original, &f) == PWP_BUSY);
    assert(f.close_count == 1 && original_authority(&f)); clean_drain(&f);
    for (unsigned i = 0; i < 7; ++i) assert(f.close_order[i] == 7-i);
}
static void uncertain_candidate_close_drains_independent_owners(void) {
    fixture f; initialize(&f, 1, 1); f.fail_after = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.close_count == 1);
    f.owner.poisoned = 1; /* Actual native wrapper seals admission without pre-retiring the source. */
    assert(pwp_roles_retire_all(&f.roles, &f.owner, close_original, &f) == PWP_CLEANUP_UNKNOWN);
    assert(f.close_count == 7 && pwp_lookup(&f.owner, f.source)->state == 4);
    assert(pwp_lookup(&f.owner, f.source)->resource == resource(f.source));
    for (unsigned i = 0; i < 7; ++i) assert(f.close_order[i] == 7-i && f.physical_closes[i+1] == 1);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, close_original, &f) == PWP_CLEANUP_UNKNOWN);
    assert(f.close_count == 7 && f.roles.root == f.root);
}
static void successful_replace_close_failure_is_not_retried(void) {
    fixture f; initialize(&f, 1, 1);
    assert(apply(&f) == PWP_OK); f.fail_candidate_close = 1;
    assert(pwp_roles_retire_all(&f.roles, &f.owner, close_original, &f) == PWP_CLEANUP_UNKNOWN);
    assert(f.close_count == 7 && f.owner.poisoned && pwp_lookup(&f.owner, f.source)->state == 4);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, close_original, &f) == PWP_CLEANUP_UNKNOWN);
    assert(f.close_count == 7);
}
int main(void) {
    identity_target_scope_only(); malformed_and_reserved_targets(); null_arguments_retain_probe();
    missing_callbacks_retain_probe(); nonverified_states_never_adopt_probe();
    corrupt_sizes_are_terminal_without_adoption(); only_fresh_unpublished_targets_are_adopted();
    preexisting_poison_never_adopts_probe(); existing_target_success_order(); absent_target_is_create_only();
    preverification_refusal_still_retires_probe(); unsafe_target_refusal_still_retires_probe();
    same_identity_target_refuses_before_rename(); target_close_uncertainty_never_renames();
    revalidation_after_probe_close_is_required(); changed_grants_or_source_block_namespace_attempt();
    new_owner_poison_blocks_namespace_attempt(); retired_probe_slot_can_be_reused();
    rename_failure_never_falls_back(); postattempt_failures_remain_uncertain();
    callbacks_cannot_reenter_the_candidate(); candidate_and_leases_remain_owned_until_real_close();
    uncertain_candidate_close_drains_independent_owners(); successful_replace_close_failure_is_not_retried();
    puts("24 portable replacement controller/ownership groups PASS; NOT Windows OS/crash qualification");
    return 0;
}
