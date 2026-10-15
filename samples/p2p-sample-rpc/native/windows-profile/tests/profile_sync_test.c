/* Portable controller/owner tests, NOT an emulation of NTFS, access tokens, syscalls or crash durability. */
#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

enum { VERIFY = 1, FLUSH };
typedef struct {
    pwp_directory_sync sync;
    unsigned verifies, flushes, calls, trace[16], reenter;
    unsigned fail_verify, alter_grant_at_verify, alter_identity_at_verify;
    int fail_flush;
    uint64_t expected_identity, observed_identity;
    pwp_owner *owner;
    pwp_roles *roles;
    pwp_role_grant grant;
} fixture;
static int verify_directory(void *opaque);
static int flush_directory(void *opaque);
static pwp_result apply(fixture *f) {
    return pwp_directory_sync_apply(&f->sync, verify_directory, flush_directory, f);
}
static void observe(fixture *f, unsigned event) {
    assert(f->sync.phase == PWP_SYNC_RUNNING && f->calls < sizeof(f->trace)/sizeof(f->trace[0]));
    f->trace[f->calls++] = event;
    if (f->reenter & (1u << (f->calls-1))) {
        unsigned calls = f->calls;
        assert(apply(f) == PWP_CLOSED && f->calls == calls && f->sync.phase == PWP_SYNC_RUNNING);
        assert(!pwp_directory_sync_close_ok(&f->sync, 1));
    }
}
static int verify_directory(void *opaque) {
    fixture *f = opaque; observe(f, VERIFY); ++f->verifies;
    if (f->alter_identity_at_verify == f->verifies) ++f->observed_identity;
    if (f->alter_grant_at_verify == f->verifies) {
        assert(f->roles); ++f->grant.profile; /* Stale captured generation, not a Windows race model. */
    }
    return f->fail_verify != f->verifies && f->expected_identity == f->observed_identity &&
        ((!f->owner && !f->roles) || (f->owner && f->roles &&
            pwp_roles_check_grant(f->roles, f->owner, &f->grant) == PWP_OK));
}
static int flush_directory(void *opaque) {
    fixture *f = opaque; observe(f, FLUSH); ++f->flushes;
    return !f->fail_flush;
}
static void no_retry(fixture *f) {
    unsigned calls = f->calls;
    assert(f->sync.phase == PWP_SYNC_UNCERTAIN);
    assert(apply(f) == PWP_CLOSED && f->calls == calls);
    assert(pwp_directory_sync_apply(&f->sync, NULL, NULL, NULL) == PWP_CLOSED);
    assert(f->sync.phase == PWP_SYNC_UNCERTAIN && !pwp_directory_sync_close_ok(&f->sync, 1));
}
static void exact_access_readback(void) {
    assert(pwp_directory_sync_access(1, PWP_DIRECTORY_SYNC_ACCESS));
    const int queried[] = {-1, 0, 2};
    for (size_t i = 0; i < sizeof(queried)/sizeof(queried[0]); ++i)
        assert(!pwp_directory_sync_access(queried[i], PWP_DIRECTORY_SYNC_ACCESS));
    for (unsigned bit = 0; bit < 32; ++bit)
        assert(!pwp_directory_sync_access(1, PWP_DIRECTORY_SYNC_ACCESS ^ (UINT32_C(1) << bit)));
    assert(!pwp_directory_sync_access(1, 0));
    assert(!pwp_directory_sync_access(1, UINT32_MAX));
    assert(!pwp_directory_sync_access(1, UINT32_C(0x001200a1))); /* Existing read-only directory mask. */
}
static void null_inputs_do_not_start(void) {
    fixture f = {0};
    assert(pwp_directory_sync_apply(NULL, verify_directory, flush_directory, &f) == PWP_ARGUMENT);
    assert(pwp_directory_sync_apply(&f.sync, NULL, flush_directory, &f) == PWP_ARGUMENT);
    assert(pwp_directory_sync_apply(&f.sync, verify_directory, NULL, &f) == PWP_ARGUMENT);
    assert(pwp_directory_sync_apply(&f.sync, NULL, NULL, NULL) == PWP_ARGUMENT);
    assert(!f.calls && f.sync.phase == PWP_SYNC_READY);
    assert(apply(&f) == PWP_OK);
}
static void nonready_states_do_not_start(void) {
    const pwp_directory_sync_phase phases[] = {PWP_SYNC_RUNNING, PWP_SYNC_UNCERTAIN,
        (pwp_directory_sync_phase)-1, (pwp_directory_sync_phase)99};
    for (size_t i = 0; i < sizeof(phases)/sizeof(phases[0]); ++i) {
        fixture f = {0}; f.sync.phase = phases[i];
        assert(apply(&f) == PWP_CLOSED && !f.calls && f.sync.phase == phases[i]);
        assert(pwp_directory_sync_apply(&f.sync, NULL, NULL, NULL) == PWP_CLOSED);
    }
}
static void success_verifies_around_one_flush(void) {
    fixture f = {0}; const unsigned order[] = {VERIFY, FLUSH, VERIFY};
    assert(apply(&f) == PWP_OK && f.sync.phase == PWP_SYNC_READY);
    assert(f.verifies == 2 && f.flushes == 1 && f.calls == 3 && !memcmp(f.trace, order, sizeof(order)));
    assert(pwp_directory_sync_close_ok(&f.sync, 1));
}
static void independent_later_sync_is_allowed(void) {
    fixture f = {0};
    assert(apply(&f) == PWP_OK && apply(&f) == PWP_OK);
    const unsigned order[] = {VERIFY, FLUSH, VERIFY, VERIFY, FLUSH, VERIFY};
    assert(f.verifies == 4 && f.flushes == 2 && f.calls == 6 && !memcmp(f.trace, order, sizeof(order)));
    assert(f.sync.phase == PWP_SYNC_READY);
}
static void preverification_never_flushes(void) {
    fixture f = {0}; f.fail_verify = 1;
    assert(apply(&f) == PWP_POLICY && f.calls == 1 && f.verifies == 1 && !f.flushes);
    assert(f.sync.phase == PWP_SYNC_READY && pwp_directory_sync_close_ok(&f.sync, 1));
    f.fail_verify = 0;
    assert(apply(&f) == PWP_OK && f.flushes == 1); /* New verified attempt, not a retry of any OS flush. */
}
static void flush_failure_is_terminal_uncertainty(void) {
    fixture f = {0}; f.fail_flush = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.calls == 2 && f.verifies == 1 && f.flushes == 1);
    no_retry(&f);
}
static void postverification_failure_is_terminal_uncertainty(void) {
    fixture f = {0}; f.fail_verify = 2;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.calls == 3 && f.verifies == 2 && f.flushes == 1);
    no_retry(&f);
}
static void reentry_keeps_original_operation(void) {
    for (unsigned mask = 1; mask <= 7; ++mask) {
        fixture f = {0}; f.reenter = mask;
        assert(apply(&f) == PWP_OK && f.calls == 3 && f.flushes == 1 && f.sync.phase == PWP_SYNC_READY);
    }
}
static void changed_identity_is_not_certified(void) {
    fixture before = {0}; before.alter_identity_at_verify = 1;
    assert(apply(&before) == PWP_POLICY && !before.flushes && before.sync.phase == PWP_SYNC_READY);
    fixture after = {0}; after.alter_identity_at_verify = 2;
    assert(apply(&after) == PWP_CLEANUP_UNKNOWN && after.flushes == 1);
    no_retry(&after);
}
static uint64_t add(pwp_owner *owner) {
    uint64_t token = 0;
    assert(pwp_reserve(owner, &token) == PWP_OK && pwp_attach(owner, token, (uintptr_t)token) == PWP_OK);
    assert(pwp_publish(owner, token) == PWP_OK);
    return token;
}
typedef struct {
    pwp_owner owner;
    pwp_roles roles;
    fixture f;
    uint64_t root, profile, identity, vault;
    uintptr_t closes[PWP_HANDLE_LIMIT];
    unsigned close_count;
    uint64_t close_fail;
} scope;
static void scope_init(scope *s, int identity) {
    memset(s, 0, sizeof(*s)); pwp_owner_init(&s->owner); pwp_roles_init(&s->roles);
    assert(pwp_roles_begin_root(&s->roles, &s->owner) == PWP_OK);
    s->root = add(&s->owner);
    assert(pwp_roles_bind_root(&s->roles, &s->owner, s->root) == PWP_OK);
    s->profile = add(&s->owner);
    assert(pwp_roles_bind_lease(&s->roles, &s->owner, s->root, PWP_LEASE_PROFILE, s->profile) == PWP_OK);
    if (identity) {
        s->identity = add(&s->owner);
        assert(pwp_roles_bind_identity(&s->roles, &s->owner, s->root, s->identity) == PWP_OK);
        s->vault = add(&s->owner);
        assert(pwp_roles_bind_lease(&s->roles, &s->owner, s->identity, PWP_LEASE_VAULT, s->vault) == PWP_OK);
    }
    s->f.owner = &s->owner; s->f.roles = &s->roles;
    assert(pwp_roles_capture(&s->roles, &s->owner, identity ? s->identity : s->root, &s->f.grant) == PWP_OK);
}
static int close_original(uintptr_t original, void *opaque) {
    scope *s = opaque;
    pwp_owned_handle *held = pwp_lookup(&s->owner, (uint64_t)original);
    assert(held && held->state == 4 && held->resource == original);
    assert(s->close_count < PWP_HANDLE_LIMIT);
    for (unsigned i = 0; i < s->close_count; ++i) assert(s->closes[i] != original);
    s->closes[s->close_count++] = original; /* Physical-close observation occurs BEFORE result classification. */
    return original == s->f.grant.directory ? pwp_directory_sync_close_ok(&s->f.sync, original != s->close_fail) :
        original != s->close_fail;
}
static void exact_root_and_identity_grants(void) {
    for (int identity = 0; identity <= 1; ++identity) {
        scope s; scope_init(&s, identity);
        assert(apply(&s.f) == PWP_OK && s.f.flushes == 1);
        assert(pwp_roles_retire_all(&s.roles, &s.owner, close_original, &s) == PWP_OK);
        assert(s.close_count == (unsigned)(identity ? 4 : 2));
    }
}
static void stale_grants_cannot_certify_a_flush(void) {
    for (int identity = 0; identity <= 1; ++identity) for (unsigned when = 1; when <= 2; ++when) {
        scope s; scope_init(&s, identity); s.f.alter_grant_at_verify = when;
        assert(apply(&s.f) == (when == 1 ? PWP_POLICY : PWP_CLEANUP_UNKNOWN));
        assert(s.f.flushes == (when == 1 ? 0u : 1u));
        --s.f.grant.profile; /* Restore the captured tuple only for inspecting ownership, never retry the flush. */
        if (when == 2) { no_retry(&s.f); s.owner.poisoned = 1; }
        assert(pwp_roles_retire_all(&s.roles, &s.owner, close_original, &s) ==
            (when == 1 ? PWP_OK : PWP_CLEANUP_UNKNOWN));
        assert(s.close_count == (unsigned)(identity ? 4 : 2));
    }
}
static void uncertainty_keeps_live_owner_until_real_close(void) {
    for (int identity = 0; identity <= 1; ++identity) {
        scope s; scope_init(&s, identity); s.f.fail_flush = 1;
        uint64_t directory = s.f.grant.directory;
        assert(apply(&s.f) == PWP_CLEANUP_UNKNOWN);
        pwp_owned_handle *held = pwp_lookup(&s.owner, directory);
        assert(held && held->state == 2 && held->published && held->resource == directory && !s.close_count);
        s.owner.poisoned = 1; /* Exact native boundary seals admission but does not pre-retire this owner. */
        pwp_role_grant rejected;
        assert(pwp_roles_capture(&s.roles, &s.owner, directory, &rejected) == PWP_CLEANUP_UNKNOWN);
        assert(pwp_roles_retire_all(&s.roles, &s.owner, close_original, &s) == PWP_CLEANUP_UNKNOWN);
        assert(s.close_count == (unsigned)(identity ? 4 : 2));
        assert(held->state == 4 && held->resource == directory && s.roles.root == s.root);
        unsigned count = s.close_count;
        assert(pwp_roles_retire_all(&s.roles, &s.owner, close_original, &s) == PWP_CLEANUP_UNKNOWN);
        assert(s.close_count == count && pwp_directory_sync_close_ok(&s.f.sync, 1) == 0);
        for (unsigned i = 0; i < count; ++i) assert(s.closes[i] == count-i);
    }
}
static void close_failure_never_retries_physical_handle(void) {
    scope s; scope_init(&s, 1); s.close_fail = s.identity;
    assert(apply(&s.f) == PWP_OK);
    assert(pwp_roles_retire_all(&s.roles, &s.owner, close_original, &s) == PWP_CLEANUP_UNKNOWN);
    assert(s.close_count == 4 && pwp_lookup(&s.owner, s.identity)->state == 4);
    assert(pwp_roles_retire_all(&s.roles, &s.owner, close_original, &s) == PWP_CLEANUP_UNKNOWN);
    assert(s.close_count == 4);
}
static void close_classifier_is_strict_and_nonmutating(void) {
    const pwp_directory_sync_phase phases[] = {PWP_SYNC_READY, PWP_SYNC_RUNNING, PWP_SYNC_UNCERTAIN,
        (pwp_directory_sync_phase)-1, (pwp_directory_sync_phase)99};
    const int results[] = {-1, 0, 1, 2};
    for (size_t i = 0; i < sizeof(phases)/sizeof(phases[0]); ++i) for (size_t j = 0; j < 4; ++j) {
        pwp_directory_sync sync = {phases[i]};
        assert(pwp_directory_sync_close_ok(&sync, results[j]) == (phases[i] == PWP_SYNC_READY && results[j] == 1));
        assert(sync.phase == phases[i] && !pwp_directory_sync_close_ok(NULL, results[j]));
    }
}
int main(void) {
    exact_access_readback(); null_inputs_do_not_start(); nonready_states_do_not_start();
    success_verifies_around_one_flush(); independent_later_sync_is_allowed(); preverification_never_flushes();
    flush_failure_is_terminal_uncertainty(); postverification_failure_is_terminal_uncertainty();
    reentry_keeps_original_operation(); changed_identity_is_not_certified(); exact_root_and_identity_grants();
    stale_grants_cannot_certify_a_flush(); uncertainty_keeps_live_owner_until_real_close();
    close_failure_never_retries_physical_handle(); close_classifier_is_strict_and_nonmutating();
    puts("15 portable directory-sync controller/ownership groups PASS; NOT Windows OS/crash qualification");
    return 0;
}
