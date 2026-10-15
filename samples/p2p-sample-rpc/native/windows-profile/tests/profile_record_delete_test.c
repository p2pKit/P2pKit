/* Actual shared deletion, absence, directory-sync and owner/role controllers; synthetic syscall callbacks.
 * No fake Windows headers, OS filesystem simulation, crash durability or complete-provider qualification. */
#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define NAME_MISSING UINT32_C(0xc0000034)
#define PATH_MISSING UINT32_C(0xc000003a)
typedef struct {
    pwp_owner owner;
    uint64_t probe, reused, independent;
    uint32_t status;
    int null_handle, fail_close, fail_verify, poison_verify, reuse, reenter;
    unsigned closes, checks, close_reentries, verify_reentries, independent_closes;
} absence_fixture;
static pwp_result observe_absence(absence_fixture *f);
static int probe_close(uintptr_t resource, void *opaque) {
    absence_fixture *f = opaque;
    if (resource == 77) { ++f->independent_closes; assert(f->independent_closes == 1); return 1; }
    assert(resource == 99 && ++f->closes == 1);
    assert(pwp_lookup(&f->owner, f->probe)->state == 4);
    if (f->reenter) { assert(observe_absence(f) == PWP_ARGUMENT); ++f->close_reentries; }
    return !f->fail_close;
}
static int probe_verify(void *opaque) {
    absence_fixture *f = opaque; ++f->checks;
    assert(f->checks == 1 && !f->closes);
    pwp_owned_handle *retired = pwp_lookup(&f->owner, f->probe);
    assert(retired && retired->state == 3 && !retired->resource);
    if (f->reenter) { assert(observe_absence(f) == PWP_ARGUMENT); ++f->verify_reentries; }
    if (f->reuse) {
        assert(pwp_reserve(&f->owner, &f->reused) == PWP_OK && f->reused != f->probe);
        assert(pwp_lookup(&f->owner, f->reused) == retired && !pwp_lookup(&f->owner, f->probe));
        assert(pwp_attach(&f->owner, f->reused, 77) == PWP_OK);
    }
    if (f->poison_verify) f->owner.poisoned = 1;
    return !f->fail_verify;
}
static void absence_init(absence_fixture *f, int resource) {
    memset(f, 0, sizeof(*f)); pwp_owner_init(&f->owner);
    f->status = NAME_MISSING; f->null_handle = !resource;
    assert(pwp_reserve(&f->owner, &f->probe) == PWP_OK);
    if (resource) assert(pwp_attach(&f->owner, f->probe, 99) == PWP_OK);
}
static pwp_result observe_absence(absence_fixture *f) {
    return pwp_name_absence_finish(&f->owner, f->probe, f->status, f->null_handle,
                                    probe_verify, probe_close, f);
}
static void only_exact_final_missing_and_null_handle_prove_absence(void) {
    const uint32_t statuses[] = {0, 0x103, NAME_MISSING, PATH_MISSING, 0xc0000022, 0xc0000043,
        0xc0000056, 0xc0000103, 0xc0000033, 0xffffffff};
    const int nulls[] = {-1, 0, 1, 2};
    for (size_t i = 0; i < sizeof(statuses)/sizeof(statuses[0]); ++i)
        for (size_t j = 0; j < sizeof(nulls)/sizeof(nulls[0]); ++j)
            assert(pwp_exact_name_absence(statuses[i], nulls[j]) == (statuses[i] == NAME_MISSING && nulls[j] == 1));
}
static void exact_absence_retires_empty_probe_before_parent_check(void) {
    absence_fixture f; absence_init(&f, 0);
    assert(observe_absence(&f) == PWP_NOT_FOUND && f.checks == 1 && !f.closes && !f.owner.poisoned);
    assert(pwp_lookup(&f.owner, f.probe)->state == 3);
    assert(pwp_retire_all(&f.owner, probe_close, &f) == PWP_OK && !f.closes);
}
static void all_nonmissing_statuses_and_invalid_sentinel_fail_closed(void) {
    const uint32_t statuses[] = {0, 0x103, PATH_MISSING, 0xc0000022, 0xc0000043, 0xc0000056, 0xffffffff};
    for (size_t i = 0; i < sizeof(statuses)/sizeof(statuses[0]); ++i) {
        absence_fixture f; absence_init(&f, 0); f.status = statuses[i];
        assert(observe_absence(&f) == PWP_CLEANUP_UNKNOWN && !f.closes && !f.checks);
        assert(pwp_lookup(&f.owner, f.probe)->state == 3);
    }
    absence_fixture sentinel; absence_init(&sentinel, 0); sentinel.null_handle = 0;
    /* INVALID_HANDLE_VALUE is non-NULL but never attached or physically closed. */
    assert(observe_absence(&sentinel) == PWP_CLEANUP_UNKNOWN && !sentinel.closes && !sentinel.checks);
}
static void unexpected_valid_handle_is_always_closed_not_deleted(void) {
    const uint32_t statuses[] = {0, 0x103, NAME_MISSING, PATH_MISSING, 0xc0000022, 0xc0000043};
    for (size_t i = 0; i < sizeof(statuses)/sizeof(statuses[0]); ++i) for (int nulls = 0; nulls <= 1; ++nulls) {
        absence_fixture f; absence_init(&f, 1); f.status = statuses[i]; f.null_handle = nulls;
        assert(observe_absence(&f) == PWP_CLEANUP_UNKNOWN && f.closes == 1 && !f.checks);
        assert(pwp_lookup(&f.owner, f.probe)->state == 3 && !f.owner.poisoned);
        assert(pwp_retire_all(&f.owner, probe_close, &f) == PWP_OK && f.closes == 1);
    }
}
static void failed_probe_close_quarantines_and_drains_independent_owners(void) {
    absence_fixture f; absence_init(&f, 1); f.fail_close = 1;
    assert(pwp_reserve(&f.owner, &f.independent) == PWP_OK);
    assert(pwp_attach(&f.owner, f.independent, 77) == PWP_OK);
    assert(observe_absence(&f) == PWP_CLEANUP_UNKNOWN && f.closes == 1 && !f.checks && f.owner.poisoned);
    assert(pwp_retire_all(&f.owner, probe_close, &f) == PWP_CLEANUP_UNKNOWN);
    assert(f.independent_closes == 1 && f.closes == 1);
    assert(observe_absence(&f) == PWP_ARGUMENT && f.closes == 1);
}
static void original_parent_must_verify_after_empty_probe_retirement(void) {
    for (int mode = 0; mode < 3; ++mode) {
        absence_fixture f; absence_init(&f, 0);
        f.fail_verify = mode == 0; f.poison_verify = mode == 1; f.owner.poisoned = mode == 2;
        assert(observe_absence(&f) == PWP_CLEANUP_UNKNOWN && !f.closes);
        assert(f.checks == (mode == 2 ? 0u : 1u) && pwp_lookup(&f.owner, f.probe)->state == 3);
    }
}
static void verifier_can_reuse_retired_probe_slot_without_changing_observation(void) {
    absence_fixture f; absence_init(&f, 0); f.reuse = 1;
    assert(observe_absence(&f) == PWP_NOT_FOUND && f.checks == 1 && f.reused && !f.closes);
    assert(!pwp_lookup(&f.owner, f.probe) && pwp_lookup(&f.owner, f.reused)->state == 2);
    assert(pwp_retire_all(&f.owner, probe_close, &f) == PWP_OK && f.independent_closes == 1);
}
static void probe_invalid_arguments_never_adopt_caller_ownership(void) {
    absence_fixture f; absence_init(&f, 1);
    assert(pwp_name_absence_finish(NULL, f.probe, NAME_MISSING, 0, probe_verify, probe_close, &f) == PWP_ARGUMENT);
    assert(pwp_name_absence_finish(&f.owner, 0, NAME_MISSING, 0, probe_verify, probe_close, &f) == PWP_ARGUMENT);
    assert(pwp_name_absence_finish(&f.owner, f.probe, NAME_MISSING, 0, NULL, probe_close, &f) == PWP_ARGUMENT);
    assert(pwp_name_absence_finish(&f.owner, f.probe, NAME_MISSING, 0, probe_verify, NULL, &f) == PWP_ARGUMENT);
    f.null_handle = -1; assert(observe_absence(&f) == PWP_ARGUMENT);
    f.null_handle = 2; assert(observe_absence(&f) == PWP_ARGUMENT);
    assert(!f.closes && !f.checks && pwp_lookup(&f.owner, f.probe)->state == 2);
    assert(pwp_retire_all(&f.owner, probe_close, &f) == PWP_OK && f.closes == 1);
}
static void published_stale_and_malformed_probe_owners_are_not_borrowed(void) {
    absence_fixture f; absence_init(&f, 1); assert(pwp_publish(&f.owner, f.probe) == PWP_OK);
    assert(observe_absence(&f) == PWP_ARGUMENT && !f.closes && !f.checks);
    assert(pwp_retire_all(&f.owner, probe_close, &f) == PWP_OK && f.closes == 1);
    assert(observe_absence(&f) == PWP_ARGUMENT);
    for (int mode = 0; mode < 4; ++mode) {
        absence_init(&f, 0); pwp_owned_handle *owned = pwp_lookup(&f.owner, f.probe);
        if (mode == 0) owned->state = 0;
        if (mode == 1) owned->state = 4;
        if (mode == 2) owned->resource = 99;
        if (mode == 3) owned->state = 2;
        assert(observe_absence(&f) == PWP_ARGUMENT && !f.closes && !f.checks);
    }
}
static void probe_callback_reentry_never_repeats_cleanup(void) {
    for (int resource = 0; resource <= 1; ++resource) {
        absence_fixture f; absence_init(&f, resource); f.reenter = 1;
        assert(observe_absence(&f) == (resource ? PWP_CLEANUP_UNKNOWN : PWP_NOT_FOUND));
        assert(f.close_reentries == (unsigned)resource && f.verify_reentries == (unsigned)!resource);
        assert(f.closes == (unsigned)resource && f.checks == (unsigned)!resource);
    }
}

typedef struct {
    pwp_owner owner;
    pwp_roles roles;
    pwp_role_grant grant;
    pwp_record_delete deletion;
    pwp_directory_sync directory_sync;
    uint64_t root, profile, identity, vault, independent, source, probe;
    uint64_t parent_id, expected_parent_id, actual_file_id, expected_file_id;
    unsigned closes[32], close_order[32], close_count, removes, absences, syncs, seals;
    unsigned verifies, marks, pending_checks, probe_checks, sync_checks, directory_flushes;
    unsigned events, reentries, invalidation_occurrence, invalidation_count;
    char trace[32], invalidate_at;
    int invalidate_kind, reenter, draining, fail_mark, fail_pending, fail_source_close, fail_probe_close;
    int fail_sync_check, fail_flush, probe_resource, probe_null, namespace_changed, namespace_synced, session_failed;
    int absence_override, sync_override;
    uint32_t probe_status;
    pwp_result remove_result, absence_result, sync_result;
} fixture;
static pwp_result remove_record(void *opaque);
static pwp_result absence_record(void *opaque);
static pwp_result sync_record(void *opaque);
static void seal_record(void *opaque);
static pwp_result apply(fixture *f) {
    return pwp_record_delete_apply(&f->deletion, remove_record, absence_record, sync_record, seal_record, f);
}
static uintptr_t resource(uint64_t token) { return (uintptr_t)(0x10000u+token); }
static uint64_t own(fixture *f, int published) {
    uint64_t token = 0; assert(pwp_reserve(&f->owner, &token) == PWP_OK && token < 32);
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
    f->independent = own(f, 1);
    pwp_role_grant root_grant;
    assert(pwp_roles_capture(&f->roles, &f->owner, f->root, &root_grant) == PWP_OK);
    assert(pwp_roles_bind_stage(&f->roles, &f->owner, f->independent, &root_grant) == PWP_OK);
    assert(pwp_roles_capture(&f->roles, &f->owner, f->identity, &f->grant) == PWP_OK);
    f->parent_id = f->expected_parent_id = 0x1234;
    f->actual_file_id = f->expected_file_id = 0x9876;
    f->probe_status = NAME_MISSING; f->probe_null = 1; f->invalidation_occurrence = 1;
}
static void event(fixture *f, char action) {
    assert(f->events < sizeof(f->trace)); f->trace[f->events++] = action;
    if (f->reenter) {
        unsigned count = f->events;
        assert(apply(f) == PWP_CLOSED && f->events == count); ++f->reentries;
    }
    if (action == f->invalidate_at && ++f->invalidation_count == f->invalidation_occurrence) {
        if (f->invalidate_kind == 0) ++f->roles.root;
        if (f->invalidate_kind == 1) ++f->roles.profile;
        if (f->invalidate_kind == 2) ++f->roles.identity;
        if (f->invalidate_kind == 3) ++f->roles.vault;
        if (f->invalidate_kind == 4) ++f->parent_id;
    }
}
static int parents_held(fixture *f) {
    const uint64_t parents[] = {f->root, f->profile, f->identity, f->vault};
    for (size_t i = 0; i < sizeof(parents)/sizeof(parents[0]); ++i) {
        pwp_owned_handle *held = pwp_lookup(&f->owner, parents[i]);
        if (!held || held->state != 2 || !held->published || held->resource != resource(parents[i]) ||
            f->closes[parents[i]]) return 0;
    }
    return 1;
}
static int parent_valid(fixture *f) {
    return parents_held(f) && f->parent_id == f->expected_parent_id &&
        pwp_roles_check_grant(&f->roles, &f->owner, &f->grant) == PWP_OK;
}
static int source_verify(void *opaque) {
    fixture *f = opaque; event(f, 'V'); ++f->verifies;
    assert(f->deletion.phase == PWP_DELETE_INTENT && pwp_lookup(&f->owner, f->source)->state == 4);
    return parent_valid(f) && f->actual_file_id == f->expected_file_id;
}
static int source_mark(void *opaque) {
    fixture *f = opaque; event(f, 'M'); ++f->marks;
    assert(f->marks == 1 && parents_held(f));
    f->namespace_changed = 1; /* A failed attempted disposition cannot imply no mutation. */
    return parent_valid(f) && !f->fail_mark;
}
static int source_pending(void *opaque) {
    fixture *f = opaque; event(f, 'P'); ++f->pending_checks;
    assert(f->marks == 1 && parents_held(f));
    return parent_valid(f) && !f->fail_pending && f->actual_file_id == f->expected_file_id;
}
static int physical_close(uintptr_t raw, void *opaque) {
    fixture *f = opaque;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        pwp_owned_handle *held = &f->owner.slots[i];
        if (held->state != 4 || held->resource != raw) continue;
        uint64_t token = held->token;
        assert(token < 32 && raw == resource(token) && ++f->closes[token] == 1);
        assert(f->close_count < 32); f->close_order[f->close_count++] = (unsigned)token;
        if (!f->draining) assert(parents_held(f));
        if (token == f->source) { event(f, 'C'); return !f->fail_source_close; }
        if (token == f->probe) { event(f, 'Q'); return !f->fail_probe_close; }
        if (token == f->identity) return pwp_directory_sync_close_ok(&f->directory_sync, 1);
        return 1;
    }
    assert(0); return 0;
}
static pwp_result remove_record(void *opaque) {
    fixture *f = opaque; assert(f->deletion.phase == PWP_DELETE_INTENT); event(f, 'R'); ++f->removes;
    if (!parent_valid(f)) return PWP_POLICY;
    if (f->remove_result != PWP_OK) return f->remove_result;
    assert(f->removes == 1 && !f->source); f->source = own(f, 0);
    return pwp_delete_intent_finish(&f->owner, f->source, source_verify, source_mark, source_pending, physical_close, f);
}
static int after_probe(void *opaque) {
    fixture *f = opaque; event(f, 'G'); ++f->probe_checks;
    assert(f->closes[f->source] == 1 && !pwp_lookup(&f->owner, f->source));
    assert(pwp_lookup(&f->owner, f->probe)->state == 3);
    return parent_valid(f);
}
static pwp_result absence_record(void *opaque) {
    fixture *f = opaque; assert(f->deletion.phase == PWP_DELETE_OBSERVING); event(f, 'A'); ++f->absences;
    assert(f->closes[f->source] == 1 && f->marks == 1 && f->pending_checks == 1);
    if (!parent_valid(f)) return PWP_POLICY;
    if (f->absence_override) return f->absence_result;
    pwp_owned_handle *retired_source = pwp_lookup(&f->owner, f->source);
    assert(retired_source && retired_source->state == 3);
    pwp_result result = pwp_reserve(&f->owner, &f->probe); if (result != PWP_OK) return result;
    /* The real registry reuses the retired source slot. No later phase may inspect the old file entry. */
    assert(pwp_lookup(&f->owner, f->probe) == retired_source && !pwp_lookup(&f->owner, f->source));
    if (f->probe_resource) assert(pwp_attach(&f->owner, f->probe, resource(f->probe)) == PWP_OK);
    return pwp_name_absence_finish(&f->owner, f->probe, f->probe_status, f->probe_null,
                                    after_probe, physical_close, f);
}
static int sync_verify(void *opaque) {
    fixture *f = opaque; event(f, 'D'); ++f->sync_checks;
    assert(f->directory_sync.phase == PWP_SYNC_RUNNING && f->deletion.phase == PWP_DELETE_SYNCING);
    return f->sync_checks != (unsigned)f->fail_sync_check && parent_valid(f);
}
static int sync_flush(void *opaque) {
    fixture *f = opaque; event(f, 'F'); ++f->directory_flushes;
    assert(f->directory_flushes == 1 && f->closes[f->source] == 1 && parents_held(f));
    f->namespace_synced = !f->fail_flush;
    return !f->fail_flush;
}
static pwp_result sync_record(void *opaque) {
    fixture *f = opaque; assert(f->deletion.phase == PWP_DELETE_SYNCING); event(f, 'S'); ++f->syncs;
    assert(f->closes[f->source] == 1 && f->namespace_changed && parents_held(f));
    if (!parent_valid(f)) return PWP_POLICY;
    if (f->sync_override) return f->sync_result;
    pwp_result result = pwp_directory_sync_apply(&f->directory_sync, sync_verify, sync_flush, f);
    if (result == PWP_OK) { event(f, 'E'); if (!parent_valid(f)) result = PWP_POLICY; }
    return result;
}
static void seal_record(void *opaque) {
    fixture *f = opaque; assert(f->deletion.phase == PWP_DELETE_UNCERTAIN); event(f, 'U'); ++f->seals;
    assert(f->seals == 1 && (!f->source || f->closes[f->source] == 1));
    /* Only memory authority is sealed, including when the old source slot now belongs to the probe. */
    f->session_failed = 1; f->owner.poisoned = 1;
}
static void no_retry(fixture *f, pwp_record_delete_phase phase) {
    unsigned calls = f->events;
    assert(f->deletion.phase == phase && apply(f) == PWP_CLOSED && f->events == calls);
}
static void drain(fixture *f, int unknown) {
    f->draining = 1;
    unsigned source_closes = f->source ? f->closes[f->source] : 0;
    unsigned probe_closes = f->probe ? f->closes[f->probe] : 0;
    assert(pwp_roles_retire_all(&f->roles, &f->owner, physical_close, f) ==
        (unknown ? PWP_CLEANUP_UNKNOWN : PWP_OK));
    if (f->source) assert(f->closes[f->source] == source_closes && source_closes == 1);
    if (f->probe) assert(f->closes[f->probe] == probe_closes);
    assert(f->close_count >= 5);
    for (unsigned i = 0; i < 5; ++i) {
        assert(f->closes[i+1] == 1);
        assert(f->close_order[f->close_count-5+i] == 5-i);
    }
    unsigned count = f->close_count;
    assert(pwp_roles_retire_all(&f->roles, &f->owner, physical_close, f) ==
        (unknown ? PWP_CLEANUP_UNKNOWN : PWP_OK));
    assert(f->close_count == count && !!f->owner.poisoned == !!unknown);
}
static void expect_unknown(fixture *f) {
    assert(f->session_failed && f->owner.poisoned && f->seals == 1);
    no_retry(f, PWP_DELETE_UNCERTAIN); drain(f, 1);
}
static void successful_delete_closes_before_strict_absence_then_syncs_original_parent(void) {
    fixture f; initialize(&f); assert(apply(&f) == PWP_OK);
    assert(f.events == 12 && !memcmp(f.trace, "RVMPCAGSDFDE", 12));
    assert(f.removes == 1 && f.absences == 1 && f.syncs == 1 && f.probe_checks == 1);
    assert(f.directory_flushes == 1 && f.sync_checks == 2 && f.namespace_changed && f.namespace_synced);
    assert(!f.seals && parents_held(&f) && !pwp_lookup(&f.owner, f.source));
    no_retry(&f, PWP_DELETE_COMPLETE); drain(&f, 0);
}
static void missing_before_intent_is_still_an_error_without_absence_or_sync(void) {
    fixture f; initialize(&f); f.remove_result = PWP_NOT_FOUND;
    assert(apply(&f) == PWP_NOT_FOUND && f.events == 1 && f.trace[0] == 'R');
    assert(!f.source && !f.absences && !f.syncs && !f.seals && !f.namespace_changed);
    no_retry(&f, PWP_DELETE_FAILED); drain(&f, 0);
}
static void safe_preintent_errors_never_run_later_steps(void) {
    const pwp_result codes[] = {PWP_ARGUMENT, PWP_BUSY, PWP_CLOSED, PWP_POLICY, PWP_LIMIT, PWP_OS, PWP_UNIMPLEMENTED};
    for (size_t i = 0; i < sizeof(codes)/sizeof(codes[0]); ++i) {
        fixture f; initialize(&f); f.remove_result = codes[i];
        assert(apply(&f) == codes[i] && f.events == 1 && !f.source && !f.absences && !f.syncs && !f.seals);
        no_retry(&f, PWP_DELETE_FAILED); drain(&f, 0);
    }
}
static void wrong_expected_identity_closes_without_mark_and_preserves_policy(void) {
    fixture f; initialize(&f); ++f.expected_file_id;
    assert(apply(&f) == PWP_POLICY && f.events == 3 && !memcmp(f.trace, "RVC", 3));
    assert(f.closes[f.source] == 1 && !f.marks && !f.absences && !f.syncs && !f.seals);
    no_retry(&f, PWP_DELETE_FAILED); drain(&f, 0);
}
static void failed_mark_readback_or_close_never_observes_absence_or_flushes(void) {
    for (int failure = 0; failure < 3; ++failure) {
        fixture f; initialize(&f);
        f.fail_mark = failure == 0; f.fail_pending = failure == 1; f.fail_source_close = failure == 2;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.closes[f.source] == 1 && f.marks == 1);
        assert(!f.absences && !f.syncs && !f.directory_flushes);
        assert(pwp_lookup(&f.owner, f.source)->state == 4);
        expect_unknown(&f);
    }
}
static void safe_identity_refusal_with_failed_close_is_uncertain(void) {
    fixture f; initialize(&f); ++f.expected_file_id; f.fail_source_close = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.marks && !f.absences && !f.syncs);
    expect_unknown(&f);
}
static void every_nonabsence_result_after_intent_becomes_unknown(void) {
    const int codes[] = {0, 1, 2, 3, 4, 5, 6, 8, 9, 10, -1, INT32_MIN, INT32_MAX};
    for (size_t i = 0; i < sizeof(codes)/sizeof(codes[0]); ++i) {
        fixture f; initialize(&f); f.absence_override = 1; f.absence_result = (pwp_result)codes[i];
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.closes[f.source] == 1 && f.absences == 1);
        assert(!f.syncs && !f.directory_flushes); expect_unknown(&f);
    }
}
static void path_missing_access_sharing_pending_and_presence_never_become_success(void) {
    const uint32_t codes[] = {0, 0x103, PATH_MISSING, 0xc0000022, 0xc0000043, 0xc0000056};
    for (size_t i = 0; i < sizeof(codes)/sizeof(codes[0]); ++i) {
        fixture f; initialize(&f); f.probe_status = codes[i];
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.probe_checks && !f.syncs);
        expect_unknown(&f);
    }
}
static void unexpected_postdelete_handle_is_retired_once_before_seal(void) {
    for (int failed_close = 0; failed_close <= 1; ++failed_close) {
        fixture f; initialize(&f); f.probe_resource = 1; f.probe_null = 0; f.fail_probe_close = failed_close;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.closes[f.source] == 1 && f.closes[f.probe] == 1);
        assert(!f.probe_checks && !f.syncs && !pwp_lookup(&f.owner, f.source));
        expect_unknown(&f);
    }
}
static void invalid_nonnull_probe_sentinel_does_not_certify_absence(void) {
    fixture f; initialize(&f); f.probe_null = 0;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.closes[f.probe] && !f.probe_checks && !f.syncs);
    expect_unknown(&f);
}
static void every_sync_error_after_absence_is_unknown_including_preverification(void) {
    const int codes[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, -1, INT32_MIN, INT32_MAX};
    for (size_t i = 0; i < sizeof(codes)/sizeof(codes[0]); ++i) {
        fixture f; initialize(&f); f.sync_override = 1; f.sync_result = (pwp_result)codes[i];
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.syncs == 1 && f.probe_checks == 1 && !f.directory_flushes);
        expect_unknown(&f);
    }
}
static void directory_preverification_flush_and_postverification_failures_are_uncertain(void) {
    for (int failure = 0; failure < 3; ++failure) {
        fixture f; initialize(&f); f.fail_sync_check = failure == 0 ? 1 : failure == 2 ? 2 : 0;
        f.fail_flush = failure == 1;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.syncs == 1 && f.closes[f.source] == 1);
        assert(f.directory_flushes == (failure == 0 ? 0u : 1u)); expect_unknown(&f);
    }
}
static void stale_grants_and_parent_identity_are_checked_at_every_transition(void) {
    const char points[] = {'R', 'V', 'M', 'P', 'A', 'G', 'S', 'D', 'F', 'E'};
    for (size_t at = 0; at < sizeof(points); ++at) for (int kind = 0; kind < 5; ++kind) {
        fixture f; initialize(&f); f.invalidate_at = points[at]; f.invalidate_kind = kind;
        int uncertain = points[at] != 'R' && points[at] != 'V';
        assert(apply(&f) == (uncertain ? PWP_CLEANUP_UNKNOWN : PWP_POLICY));
        if (uncertain) expect_unknown(&f);
        else { assert(!f.marks && !f.absences && !f.syncs && !f.seals); no_retry(&f, PWP_DELETE_FAILED); drain(&f, 0); }
    }
    fixture post; initialize(&post); post.invalidate_at = 'D'; post.invalidation_occurrence = 2;
    assert(apply(&post) == PWP_CLEANUP_UNKNOWN && post.directory_flushes == 1); expect_unknown(&post);
}
static void invalid_remove_result_is_uncertainty_not_a_safe_error(void) {
    const int codes[] = {-1, 10, INT32_MIN, INT32_MAX, PWP_CLEANUP_UNKNOWN};
    for (size_t i = 0; i < sizeof(codes)/sizeof(codes[0]); ++i) {
        fixture f; initialize(&f); f.remove_result = (pwp_result)codes[i];
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.source && !f.absences && !f.syncs); expect_unknown(&f);
    }
}
static void missing_callbacks_and_null_controller_do_not_enter(void) {
    fixture f; initialize(&f);
    assert(pwp_record_delete_apply(NULL, remove_record, absence_record, sync_record, seal_record, &f) == PWP_ARGUMENT);
    assert(pwp_record_delete_apply(&f.deletion, NULL, absence_record, sync_record, seal_record, &f) == PWP_ARGUMENT);
    assert(pwp_record_delete_apply(&f.deletion, remove_record, NULL, sync_record, seal_record, &f) == PWP_ARGUMENT);
    assert(pwp_record_delete_apply(&f.deletion, remove_record, absence_record, NULL, seal_record, &f) == PWP_ARGUMENT);
    assert(pwp_record_delete_apply(&f.deletion, remove_record, absence_record, sync_record, NULL, &f) == PWP_ARGUMENT);
    assert(!f.events && f.deletion.phase == PWP_DELETE_NEW); drain(&f, 0);
}
static void nonnew_states_never_reenter_or_retry(void) {
    const pwp_record_delete_phase phases[] = {PWP_DELETE_INTENT, PWP_DELETE_OBSERVING, PWP_DELETE_SYNCING,
        PWP_DELETE_COMPLETE, PWP_DELETE_FAILED, PWP_DELETE_UNCERTAIN, (pwp_record_delete_phase)-1,
        (pwp_record_delete_phase)99};
    for (size_t i = 0; i < sizeof(phases)/sizeof(phases[0]); ++i) {
        fixture f; initialize(&f); f.deletion.phase = phases[i];
        assert(apply(&f) == PWP_CLOSED && !f.events && f.deletion.phase == phases[i]); drain(&f, 0);
    }
}
static void every_real_callback_reentry_preserves_the_original_operation(void) {
    for (int fail = 0; fail <= 1; ++fail) {
        fixture f; initialize(&f); f.reenter = 1; f.fail_flush = fail;
        assert(apply(&f) == (fail ? PWP_CLEANUP_UNKNOWN : PWP_OK));
        assert(f.events == f.reentries && f.closes[f.source] == 1 && f.directory_flushes == 1);
        if (fail) expect_unknown(&f); else { no_retry(&f, PWP_DELETE_COMPLETE); drain(&f, 0); }
    }
}
static void uncertain_seal_never_touches_the_reused_original_slot(void) {
    fixture f; initialize(&f); f.fail_flush = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !pwp_lookup(&f.owner, f.source));
    pwp_owned_handle *probe = pwp_lookup(&f.owner, f.probe);
    assert(probe && probe->state == 3 && !probe->resource && !probe->published && !f.closes[f.probe]);
    assert(f.closes[f.source] == 1 && f.events && f.trace[f.events-1] == 'U'); expect_unknown(&f);
}
int main(void) {
    unsigned groups = 0;
#define RUN(test) do { test(); ++groups; } while (0)
    RUN(only_exact_final_missing_and_null_handle_prove_absence);
    RUN(exact_absence_retires_empty_probe_before_parent_check);
    RUN(all_nonmissing_statuses_and_invalid_sentinel_fail_closed);
    RUN(unexpected_valid_handle_is_always_closed_not_deleted);
    RUN(failed_probe_close_quarantines_and_drains_independent_owners);
    RUN(original_parent_must_verify_after_empty_probe_retirement);
    RUN(verifier_can_reuse_retired_probe_slot_without_changing_observation);
    RUN(probe_invalid_arguments_never_adopt_caller_ownership);
    RUN(published_stale_and_malformed_probe_owners_are_not_borrowed);
    RUN(probe_callback_reentry_never_repeats_cleanup);
    RUN(successful_delete_closes_before_strict_absence_then_syncs_original_parent);
    RUN(missing_before_intent_is_still_an_error_without_absence_or_sync);
    RUN(safe_preintent_errors_never_run_later_steps);
    RUN(wrong_expected_identity_closes_without_mark_and_preserves_policy);
    RUN(failed_mark_readback_or_close_never_observes_absence_or_flushes);
    RUN(safe_identity_refusal_with_failed_close_is_uncertain);
    RUN(every_nonabsence_result_after_intent_becomes_unknown);
    RUN(path_missing_access_sharing_pending_and_presence_never_become_success);
    RUN(unexpected_postdelete_handle_is_retired_once_before_seal);
    RUN(invalid_nonnull_probe_sentinel_does_not_certify_absence);
    RUN(every_sync_error_after_absence_is_unknown_including_preverification);
    RUN(directory_preverification_flush_and_postverification_failures_are_uncertain);
    RUN(stale_grants_and_parent_identity_are_checked_at_every_transition);
    RUN(invalid_remove_result_is_uncertainty_not_a_safe_error);
    RUN(missing_callbacks_and_null_controller_do_not_enter);
    RUN(nonnew_states_never_reenter_or_retry);
    RUN(every_real_callback_reentry_preserves_the_original_operation);
    RUN(uncertain_seal_never_touches_the_reused_original_slot);
#undef RUN
    printf("%u portable durable-delete/absence/ownership groups PASS; NOT Windows OS/crash qualification\n", groups);
    return 0;
}
