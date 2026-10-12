/* Actual strict-open classifier, original-owner ledger and candidate publication controllers.
 * Raw syscall observations/resources are inert inputs, not Windows execution or NTFS durability proof. */
#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define NAME_MISSING UINT32_C(0xc0000034)
#define PATH_MISSING UINT32_C(0xc000003a)
typedef struct {
    pwp_owner owner;
    pwp_roles roles;
    pwp_role_grant grant;
    pwp_candidate candidate;
    uint64_t root, profile, identity, vault, source, probe;
    unsigned closes[16], verifies, renames, flushes, forbidden_target_calls;
    int fail_probe_close, invalidate_grant;
} fixture;
static uintptr_t resource(uint64_t token) { return (uintptr_t)(100u + token); }
static uint64_t own(fixture *f, int published) {
    uint64_t token = 0;
    assert(pwp_reserve(&f->owner, &token) == PWP_OK && token < 16);
    assert(pwp_attach(&f->owner, token, resource(token)) == PWP_OK);
    if (published) assert(pwp_publish(&f->owner, token) == PWP_OK);
    return token;
}
static void initialize(fixture *f) {
    memset(f, 0, sizeof(*f)); pwp_owner_init(&f->owner); pwp_roles_init(&f->roles);
    assert(pwp_roles_begin_root(&f->roles, &f->owner) == PWP_OK);
    f->root = own(f, 1); assert(pwp_roles_bind_root(&f->roles, &f->owner, f->root) == PWP_OK);
    f->profile = own(f, 1);
    assert(pwp_roles_bind_lease(&f->roles, &f->owner, f->root, PWP_LEASE_PROFILE, f->profile) == PWP_OK);
    f->identity = own(f, 1);
    assert(pwp_roles_bind_identity(&f->roles, &f->owner, f->root, f->identity) == PWP_OK);
    f->vault = own(f, 1);
    assert(pwp_roles_bind_lease(&f->roles, &f->owner, f->identity, PWP_LEASE_VAULT, f->vault) == PWP_OK);
    assert(pwp_roles_capture(&f->roles, &f->owner, f->identity, &f->grant) == PWP_OK);
    f->source = own(f, 1);
    assert(pwp_roles_bind_stage(&f->roles, &f->owner, f->source, &f->grant) == PWP_OK);
    f->candidate.phase = PWP_CANDIDATE_VERIFIED; f->candidate.prepared_size = 17;
}
static int close_original(uintptr_t value, void *opaque) {
    fixture *f = opaque;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        pwp_owned_handle *held = &f->owner.slots[i];
        if (held->state != 4 || held->resource != value) continue;
        assert(held->token < 16 && value == resource(held->token));
        assert(++f->closes[held->token] == 1);
        return held->token != f->probe || !f->fail_probe_close;
    }
    assert(0); return 0;
}
static int original_grant(fixture *f) {
    const uint64_t owners[] = {f->root, f->profile, f->identity, f->vault, f->source};
    for (size_t i = 0; i < sizeof(owners)/sizeof(owners[0]); ++i) {
        pwp_owned_handle *held = pwp_lookup(&f->owner, owners[i]);
        if (!held || held->state != 2 || held->resource != resource(owners[i]) || f->closes[owners[i]]) return 0;
    }
    return pwp_roles_check_grant(&f->roles, &f->owner, &f->grant) == PWP_OK &&
        pwp_roles_check_stage(&f->roles, &f->owner, f->source) == PWP_OK;
}
static int verify_source(size_t count, void *opaque) {
    fixture *f = opaque; ++f->verifies;
    assert(count == 17 && f->candidate.phase == PWP_CANDIDATE_RENAMING);
    /* Probe retirement precedes every first publication check; the original grants remain held. */
    assert(pwp_lookup(&f->owner, f->probe)->state == 3);
    return original_grant(f);
}
static int rename_once(void *opaque) {
    fixture *f = opaque; assert(original_grant(f) && ++f->renames == 1); return 1;
}
static int replace_once(int replace, void *opaque) {
    assert(replace == 0); /* A missing target authorizes create-only, not replacement or a retry. */
    return rename_once(opaque);
}
static int flush_once(void *opaque) {
    fixture *f = opaque; assert(original_grant(f) && f->renames == 1 && ++f->flushes == 1); return 1;
}
static int target_must_not_be_borrowed(void *opaque) {
    fixture *f = opaque; ++f->forbidden_target_calls; assert(0); return 0;
}
static pwp_result publication(fixture *f, uint32_t status, int null_handle, int late_owner, int replace) {
    assert(pwp_reserve(&f->owner, &f->probe) == PWP_OK && f->probe < 16);
    if (late_owner) assert(pwp_attach(&f->owner, f->probe, resource(f->probe)) == PWP_OK);
    /* The Win32 strict-open failure path performs this same exact original retirement before classification. */
    pwp_result retired = pwp_retire(&f->owner, f->probe, close_original, f);
    pwp_result result = pwp_strict_open_failure(status, null_handle, retired);
    if (result != PWP_NOT_FOUND) return result;
    if (f->invalidate_grant) ++f->grant.profile;
    if (replace) return pwp_candidate_replace(&f->candidate, &f->owner, 0, verify_source,
        target_must_not_be_borrowed, close_original, replace_once, verify_source, flush_once, f);
    return pwp_candidate_rename_new(&f->candidate, verify_source, rename_once, verify_source, flush_once, f);
}
static void drain(fixture *f, int uncertain) {
    assert(pwp_roles_retire_all(&f->roles, &f->owner, close_original, f) ==
        (uncertain ? PWP_CLEANUP_UNKNOWN : PWP_OK));
    for (uint64_t token = f->root; token <= f->source; ++token) assert(f->closes[token] == 1);
    unsigned saved[16]; memcpy(saved, f->closes, sizeof(saved));
    assert(pwp_roles_retire_all(&f->roles, &f->owner, close_original, f) ==
        (uncertain ? PWP_CLEANUP_UNKNOWN : PWP_OK));
    assert(memcmp(saved, f->closes, sizeof(saved)) == 0 && !f->forbidden_target_calls);
}
static void classifier_never_turns_errors_or_cleanup_failure_into_absence(void) {
    const uint32_t statuses[] = {0, 0x103, NAME_MISSING, PATH_MISSING, 0xc0000022, 0xc0000043,
        0xc0000056, 0xffffffff};
    const int nulls[] = {-1, 0, 1, 2};
    const pwp_result results[] = {PWP_OK, PWP_ARGUMENT, PWP_NOT_FOUND, PWP_OS, PWP_CLEANUP_UNKNOWN,
        (pwp_result)-1, (pwp_result)99};
    for (size_t s = 0; s < sizeof(statuses)/sizeof(statuses[0]); ++s)
        for (size_t n = 0; n < sizeof(nulls)/sizeof(nulls[0]); ++n)
            for (size_t r = 0; r < sizeof(results)/sizeof(results[0]); ++r) {
                pwp_result expected = results[r] != PWP_OK ? PWP_CLEANUP_UNKNOWN :
                    statuses[s] == NAME_MISSING && nulls[n] == 1 ? PWP_NOT_FOUND : PWP_OS;
                assert(pwp_strict_open_failure(statuses[s], nulls[n], results[r]) == expected);
            }
}
static void exact_missing_enters_both_create_only_controllers_with_original_grants(void) {
    for (int replace = 0; replace <= 1; ++replace) {
        fixture f; initialize(&f);
        assert(publication(&f, NAME_MISSING, 1, 0, replace) == PWP_OK);
        assert(f.renames == 1 && f.flushes == 1 && !f.closes[f.probe] && !f.closes[f.source]);
        assert(f.candidate.phase == PWP_CANDIDATE_RENAMED && original_grant(&f));
        drain(&f, 0);
    }
}
static void failed_missing_probes_never_enter_either_publication_controller(void) {
    const uint32_t statuses[] = {0, 0x103, NAME_MISSING, PATH_MISSING, 0xc0000022, 0xc0000043, 0xc0000056};
    for (size_t s = 0; s < sizeof(statuses)/sizeof(statuses[0]); ++s)
        for (int handle = 0; handle <= 2; ++handle) for (int replace = 0; replace <= 1; ++replace) {
            /* handle=0: NULL; 1: valid late owner; 2: invalid non-NULL sentinel, never attach/close it. */
            if (statuses[s] == NAME_MISSING && handle == 0) continue;
            fixture f; initialize(&f);
            assert(publication(&f, statuses[s], handle == 0, handle == 1, replace) == PWP_OS);
            assert(!f.verifies && !f.renames && !f.flushes && original_grant(&f));
            assert(f.closes[f.probe] == (unsigned)(handle == 1));
            assert(f.candidate.phase == PWP_CANDIDATE_VERIFIED && !f.closes[f.source]);
            drain(&f, 0);
        }
}
static void failed_probe_retirement_retains_uncertainty_and_never_retries_close(void) {
    for (int replace = 0; replace <= 1; ++replace) {
        fixture f; initialize(&f); f.fail_probe_close = 1;
        assert(publication(&f, NAME_MISSING, 0, 1, replace) == PWP_CLEANUP_UNKNOWN);
        assert(!f.verifies && !f.renames && !f.flushes && f.closes[f.probe] == 1 && f.owner.poisoned);
        drain(&f, 1); assert(f.closes[f.probe] == 1);
    }
}
static void successful_absence_cannot_substitute_a_new_grant(void) {
    for (int replace = 0; replace <= 1; ++replace) {
        fixture f; initialize(&f); f.invalidate_grant = 1;
        assert(publication(&f, NAME_MISSING, 1, 0, replace) == PWP_POLICY);
        assert(f.verifies == 1 && !f.renames && !f.flushes && !f.closes[f.probe]);
        assert(f.candidate.phase == PWP_CANDIDATE_FAILED); drain(&f, 0);
    }
}
int main(void) {
    classifier_never_turns_errors_or_cleanup_failure_into_absence();
    exact_missing_enters_both_create_only_controllers_with_original_grants();
    failed_missing_probes_never_enter_either_publication_controller();
    failed_probe_retirement_retains_uncertainty_and_never_retries_close();
    successful_absence_cannot_substitute_a_new_grant();
    puts("PASS 5 portable strict-publication-probe groups (not Windows runtime)");
    return 0;
}
