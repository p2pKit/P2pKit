/* Real shared record/rename/sync/owner controllers, with synthetic resources and syscall callbacks.
 * This is not Windows filesystem emulation, an NTFS durability test or complete-provider evidence. */
#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

enum { PREPARE = 1, PUBLISH, SYNC, CLOSE, UNCERTAIN };
typedef struct {
    pwp_owner owner;
    pwp_roles roles;
    pwp_role_grant grant;
    pwp_candidate candidate;
    pwp_directory_sync directory_sync;
    pwp_record_write write;
    uint64_t root, profile, identity, vault, independent, source, returned_token;
    uint64_t source_identity, observed_identity;
    unsigned calls, trace[16], prepares, publishes, syncs, closes, seals;
    unsigned physical_closes[32], close_order[32], close_count;
    unsigned rename_attempts, rename_checks, file_flushes, sync_checks, directory_flushes;
    unsigned fail_rename_check, fail_sync_check, invalidate_grant_at;
    pwp_result prepare_result, publish_result, sync_result;
    int create_owner, published_owner, override_token, fail_rename, fail_file_flush, fail_directory_flush;
    int fail_candidate_close, fail_independent_close, fail_before_sync, fail_after_sync, reenter;
    int namespace_changed, namespace_synchronized, session_failed, close_succeeded, seal_before_close;
} fixture;
static pwp_result prepare(uint64_t *token, void *opaque);
static pwp_result publish(uint64_t token, void *opaque);
static pwp_result sync_record(uint64_t token, void *opaque);
static pwp_result close_record(uint64_t token, void *opaque);
static void uncertain(uint64_t token, void *opaque);
static pwp_result apply(fixture *f) {
    return pwp_record_write_apply(&f->write, prepare, publish, sync_record, close_record, uncertain, f);
}
static uintptr_t resource(uint64_t token) { return (uintptr_t)(0x10000u+token); }
static uint64_t own(fixture *f, int public_owner) {
    uint64_t token = 0;
    assert(pwp_reserve(&f->owner, &token) == PWP_OK && token < 32);
    assert(pwp_attach(&f->owner, token, resource(token)) == PWP_OK);
    if (public_owner) assert(pwp_publish(&f->owner, token) == PWP_OK);
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
    f->create_owner = f->published_owner = 1;
    f->source_identity = f->observed_identity = 0x123456u;
}
static void observe(fixture *f, unsigned event, pwp_record_write_phase phase) {
    assert(f->write.phase == phase && f->calls < 16);
    f->trace[f->calls++] = event;
    if (f->reenter) {
        unsigned calls = f->calls;
        assert(apply(f) == PWP_CLOSED && f->calls == calls);
    }
}
static int original_parents(fixture *f) {
    const uint64_t parents[] = {f->root, f->profile, f->identity, f->vault};
    for (size_t i = 0; i < sizeof(parents)/sizeof(parents[0]); ++i) {
        pwp_owned_handle *held = pwp_lookup(&f->owner, parents[i]);
        if (!held || held->state != 2 || !held->published || held->resource != resource(parents[i]) ||
            f->physical_closes[parents[i]]) return 0;
    }
    return 1;
}
static int authority(fixture *f) {
    return original_parents(f) && pwp_roles_check_grant(&f->roles, &f->owner, &f->grant) == PWP_OK;
}
static int original_source(fixture *f) {
    pwp_owned_handle *held = pwp_lookup(&f->owner, f->source);
    return authority(f) && held && held->state == 2 && held->resource == resource(f->source) &&
        f->source_identity == f->observed_identity &&
        pwp_roles_check_stage(&f->roles, &f->owner, f->source) == PWP_OK &&
        !f->physical_closes[f->source];
}
static pwp_result prepare(uint64_t *token, void *opaque) {
    fixture *f = opaque; observe(f, PREPARE, PWP_WRITE_PREPARING); ++f->prepares;
    assert(token && !*token && f->prepares == 1);
    if (f->invalidate_grant_at == PREPARE) ++f->grant.vault;
    if (!authority(f)) return PWP_POLICY;
    if (f->create_owner) {
        f->source = own(f, f->published_owner);
        f->candidate.phase = f->prepare_result == PWP_OK ? PWP_CANDIDATE_VERIFIED : PWP_CANDIDATE_FAILED;
        f->candidate.prepared_size = 17;
        if (f->published_owner)
            assert(pwp_roles_bind_stage(&f->roles, &f->owner, f->source, &f->grant) == PWP_OK);
    }
    *token = f->override_token ? f->returned_token : f->source;
    return f->prepare_result;
}
static int rename_verify(size_t count, void *opaque) {
    fixture *f = opaque; ++f->rename_checks;
    assert(f->candidate.phase == PWP_CANDIDATE_RENAMING && count == 17);
    return f->rename_checks != f->fail_rename_check && original_source(f);
}
static int rename_once(void *opaque) {
    fixture *f = opaque; ++f->rename_attempts;
    assert(original_source(f) && f->rename_attempts == 1);
    f->namespace_changed = 1; /* A syscall failure is permitted to have changed namespace. */
    return !f->fail_rename;
}
static int flush_file(void *opaque) {
    fixture *f = opaque; ++f->file_flushes;
    assert(original_source(f) && f->namespace_changed && f->file_flushes == 1);
    return !f->fail_file_flush;
}
static pwp_result publish(uint64_t token, void *opaque) {
    fixture *f = opaque; observe(f, PUBLISH, PWP_WRITE_PUBLISHING); ++f->publishes;
    assert(token == f->source && f->write.candidate == token && f->publishes == 1 && !f->closes);
    if (f->invalidate_grant_at == PUBLISH) ++f->grant.vault;
    if (!original_source(f)) return PWP_POLICY;
    if (f->publish_result != PWP_OK) return f->publish_result;
    return pwp_candidate_rename_new(&f->candidate, rename_verify, rename_once, rename_verify, flush_file, f);
}
static int sync_verify(void *opaque) {
    fixture *f = opaque; ++f->sync_checks;
    assert(f->directory_sync.phase == PWP_SYNC_RUNNING && f->candidate.phase == PWP_CANDIDATE_RENAMED);
    return f->sync_checks != f->fail_sync_check && original_source(f);
}
static int flush_directory(void *opaque) {
    fixture *f = opaque; ++f->directory_flushes;
    assert(original_source(f) && f->namespace_changed && f->directory_flushes == 1);
    f->namespace_synchronized = !f->fail_directory_flush;
    return !f->fail_directory_flush;
}
static pwp_result sync_record(uint64_t token, void *opaque) {
    fixture *f = opaque; observe(f, SYNC, PWP_WRITE_SYNCING); ++f->syncs;
    assert(token == f->source && f->syncs == 1 && f->namespace_changed && !f->closes);
    if (f->invalidate_grant_at == SYNC) ++f->grant.vault;
    if (f->fail_before_sync) ++f->observed_identity;
    if (!original_source(f)) return PWP_POLICY;
    if (f->sync_result != PWP_OK) return f->sync_result;
    pwp_result result = pwp_directory_sync_apply(&f->directory_sync, sync_verify, flush_directory, f);
    if (f->invalidate_grant_at == SYNC+10) ++f->grant.profile;
    if (f->fail_after_sync) ++f->observed_identity;
    if (result == PWP_OK && !original_source(f)) result = PWP_POLICY;
    return result;
}
static int physical_close(uintptr_t value, void *opaque) {
    fixture *f = opaque;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        pwp_owned_handle *held = &f->owner.slots[i];
        if (held->state != 4 || held->resource != value) continue;
        uint64_t token = held->token;
        assert(token < 32 && value == resource(token) && ++f->physical_closes[token] == 1);
        assert(f->close_count < 32); f->close_order[f->close_count++] = (unsigned)token;
        if (token == f->source) {
            assert(original_parents(f));
            f->close_succeeded = !f->fail_candidate_close;
            return pwp_candidate_close_ok(&f->candidate, f->close_succeeded);
        }
        if (token == f->identity) return pwp_directory_sync_close_ok(&f->directory_sync, 1);
        return !(token == f->independent && f->fail_independent_close);
    }
    assert(0); return 0;
}
static pwp_result close_record(uint64_t token, void *opaque) {
    fixture *f = opaque; observe(f, CLOSE, PWP_WRITE_CLOSING); ++f->closes;
    assert(token == f->source && f->closes == 1 && original_parents(f));
    assert(pwp_lookup(&f->owner, token)->state == 2 && !f->physical_closes[token]);
    f->seal_before_close = f->seals != 0;
    pwp_result result = pwp_roles_retire(&f->roles, &f->owner, token, physical_close, f);
    /* Never read a formerly live source entry after retirement, including an apparently successful close. */
    return pwp_cleanup_result(result, f->session_failed, f->owner.poisoned);
}
static void uncertain(uint64_t token, void *opaque) {
    fixture *f = opaque; observe(f, UNCERTAIN, PWP_WRITE_UNCERTAIN); ++f->seals;
    assert(f->seals == 1 && (!token || token == f->source));
    pwp_owned_handle *held = token ? pwp_lookup(&f->owner, token) : NULL;
    if (held && held->state == 2) f->candidate.phase = PWP_CANDIDATE_UNCERTAIN;
    f->session_failed = 1; f->owner.poisoned = 1;
}
static void no_retry(fixture *f, pwp_record_write_phase phase) {
    unsigned count = f->calls;
    assert(f->write.phase == phase && apply(f) == PWP_CLOSED && f->calls == count);
}
static void drain(fixture *f, int unknown) {
    unsigned source_closes = f->source ? f->physical_closes[f->source] : 0;
    assert(pwp_roles_retire_all(&f->roles, &f->owner, physical_close, f) ==
        (unknown ? PWP_CLEANUP_UNKNOWN : PWP_OK));
    assert(!!f->owner.poisoned == !!unknown);
    if (f->source) assert(f->physical_closes[f->source] == source_closes && source_closes == 1);
    for (uint64_t token = 1; token <= 5; ++token) assert(f->physical_closes[token] == 1);
    unsigned count = f->close_count;
    assert(pwp_roles_retire_all(&f->roles, &f->owner, physical_close, f) ==
        (unknown ? PWP_CLEANUP_UNKNOWN : PWP_OK));
    assert(f->close_count == count);
}
static void expect_unknown(fixture *f, int before_close) {
    assert(f->write.phase == PWP_WRITE_UNCERTAIN && f->session_failed && f->owner.poisoned && f->seals == 1);
    assert(f->closes == 1 && f->physical_closes[f->source] == 1 && f->seal_before_close == before_close);
    pwp_owned_handle *held = pwp_lookup(&f->owner, f->source);
    assert(held && held->state == 4); /* Unknown transaction never becomes a clean retired owner. */
    no_retry(f, PWP_WRITE_UNCERTAIN);
    drain(f, 1);
}
static size_t wide(const char *text, uint16_t *output) {
    size_t length = strlen(text);
    for (size_t i = 0; i < length; ++i) output[i] = (unsigned char)text[i];
    return length;
}
static void valid_scopes_and_bounds(void) {
    uint16_t pending[96], target[96];
    size_t p = wide("pwp-pending-0123456789abcdef0123456789abcdef", pending);
    const char *names[] = {"profile.header",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.aesgcm"};
    const size_t sizes[] = {0, 1, PWP_RECORD_LIMIT, (size_t)PWP_RECORD_LIMIT+1, SIZE_MAX};
    for (int scope = -1; scope <= 2; ++scope) for (int replace = -1; replace <= 2; ++replace)
        for (int which = 0; which <= 1; ++which) for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
            size_t t = wide(names[which], target);
            int expected = sizes[i] <= PWP_RECORD_LIMIT && scope == which &&
                (replace == 0 || (replace == 1 && scope == 1));
            assert(pwp_record_write_request(pending, p, target, t, sizes[i], scope, replace) == expected);
        }
}
static void invalid_names_rejected_before_work(void) {
    uint16_t pending[96], target[96];
    size_t p = wide("pwp-pending-0123456789abcdef0123456789abcdef", pending);
    size_t t = wide("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.aesgcm", target);
    assert(!pwp_record_write_request(NULL, p, target, t, 1, 1, 1));
    assert(!pwp_record_write_request(pending, p, NULL, t, 1, 1, 1));
    for (size_t i = 0; i < 96; ++i) {
        assert(pwp_record_write_request(pending, i, target, t, 1, 1, 1) == (i == p));
        assert(pwp_record_write_request(pending, p, target, i, 1, 1, 1) == (i == t));
    }
    assert(!pwp_record_write_request(pending, SIZE_MAX, target, t, 1, 1, 1));
    assert(!pwp_record_write_request(pending, p, target, SIZE_MAX, 1, 1, 1));
    for (size_t i = 0; i < p; ++i) {
        uint16_t saved = pending[i]; pending[i] = '/';
        assert(!pwp_record_write_request(pending, p, target, t, 1, 1, 1)); pending[i] = saved;
    }
    for (size_t i = 0; i < t; ++i) {
        uint16_t saved = target[i]; target[i] = ':';
        assert(!pwp_record_write_request(pending, p, target, t, 1, 1, 1)); target[i] = saved;
    }
    const char *invalid[] = {"profile.lock", "vault.lock", "identity", "PROFILE.HEADER",
        "pwp-pending-0123456789abcdef0123456789abcdef", "pwp-stage-0123456789abcdef0123456789abcdef"};
    for (size_t i = 0; i < sizeof(invalid)/sizeof(invalid[0]); ++i) {
        t = wide(invalid[i], target);
        assert(!pwp_record_write_request(pending, p, target, t, 1, 0, 0));
        assert(!pwp_record_write_request(pending, p, target, t, 1, 1, 0));
        assert(!pwp_record_write_request(pending, p, target, t, 1, 1, 1));
    }
}
static void argument_rejection_never_adopts(void) {
    fixture f; initialize(&f);
    assert(pwp_record_write_apply(NULL, prepare, publish, sync_record, close_record, uncertain, &f) == PWP_ARGUMENT);
    for (unsigned which = 0; which < 5; ++which) {
        assert(pwp_record_write_apply(&f.write, which == 0 ? NULL : prepare, which == 1 ? NULL : publish,
            which == 2 ? NULL : sync_record, which == 3 ? NULL : close_record, which == 4 ? NULL : uncertain,
            &f) == PWP_ARGUMENT);
        assert(!f.calls && f.write.phase == PWP_WRITE_NEW);
    }
    f.write.candidate = f.vault;
    assert(apply(&f) == PWP_ARGUMENT && !f.calls && !f.physical_closes[f.vault]);
    f.write.candidate = 0; drain(&f, 0);
}
static void nonnew_states_refuse_all_callbacks(void) {
    const pwp_record_write_phase phases[] = {PWP_WRITE_PREPARING, PWP_WRITE_PUBLISHING, PWP_WRITE_SYNCING,
        PWP_WRITE_CLOSING, PWP_WRITE_COMPLETE, PWP_WRITE_FAILED, PWP_WRITE_UNCERTAIN,
        (pwp_record_write_phase)-1, (pwp_record_write_phase)99};
    for (size_t i = 0; i < sizeof(phases)/sizeof(phases[0]); ++i) {
        fixture f; initialize(&f); f.write.phase = phases[i];
        assert(apply(&f) == PWP_CLOSED && !f.calls && f.write.phase == phases[i]); drain(&f, 0);
    }
}
static void success_preserves_originals_through_close(void) {
    fixture f; initialize(&f);
    assert(apply(&f) == PWP_OK);
    const unsigned trace[] = {PREPARE, PUBLISH, SYNC, CLOSE};
    assert(f.calls == 4 && memcmp(f.trace, trace, sizeof(trace)) == 0 && !f.seals && !f.owner.poisoned);
    assert(f.rename_attempts == 1 && f.rename_checks == 3 && f.file_flushes == 1);
    assert(f.sync_checks == 2 && f.directory_flushes == 1 && f.namespace_synchronized && f.close_succeeded);
    assert(f.closes == 1 && pwp_lookup(&f.owner, f.source)->state == 3);
    assert(f.candidate.phase == PWP_CANDIDATE_RENAMED && original_parents(&f));
    no_retry(&f, PWP_WRITE_COMPLETE); drain(&f, 0);
}
static void callback_reentry_rejected_every_phase(void) {
    fixture f; initialize(&f); f.reenter = 1;
    assert(apply(&f) == PWP_OK); no_retry(&f, PWP_WRITE_COMPLETE); drain(&f, 0);
    initialize(&f); f.reenter = 1; f.fail_directory_flush = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN); expect_unknown(&f, 1);
}
static void prepare_safe_failure_has_no_cleanup_obligation(void) {
    for (unsigned code = PWP_ARGUMENT; code <= PWP_UNIMPLEMENTED; ++code) {
        if (code == PWP_CLEANUP_UNKNOWN) continue;
        fixture f; initialize(&f); f.create_owner = 0; f.prepare_result = (pwp_result)code;
        assert(apply(&f) == (pwp_result)code && f.calls == 1 && !f.closes && !f.seals && !f.source);
        no_retry(&f, PWP_WRITE_FAILED); drain(&f, 0);
    }
}
static void late_prepared_owner_failure_is_still_closed(void) {
    for (int published = 0; published <= 1; ++published)
        for (unsigned code = PWP_ARGUMENT; code <= PWP_UNIMPLEMENTED; ++code) {
            if (code == PWP_CLEANUP_UNKNOWN) continue;
            fixture f; initialize(&f); f.published_owner = published; f.prepare_result = (pwp_result)code;
            assert(apply(&f) == (pwp_result)code && f.source && f.closes == 1 && !f.publishes && !f.syncs);
            assert(f.physical_closes[f.source] == 1 && !f.seals && pwp_lookup(&f.owner, f.source)->state == 3);
            no_retry(&f, PWP_WRITE_FAILED); drain(&f, 0);
        }
}
static void late_prepare_unknown_seals_before_exact_close(void) {
    fixture f; initialize(&f); f.prepare_result = PWP_CLEANUP_UNKNOWN;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.publishes && !f.syncs); expect_unknown(&f, 1);
}
static void late_prepare_close_fault_outranks_original_error(void) {
    for (int published = 0; published <= 1; ++published) {
        fixture f; initialize(&f); f.published_owner = published;
        f.prepare_result = PWP_POLICY; f.fail_candidate_close = 1;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.publishes && !f.syncs); expect_unknown(&f, 0);
    }
}
static void success_without_owner_is_contract_uncertainty(void) {
    fixture f; initialize(&f); f.create_owner = 0;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.source && !f.closes && f.seals == 1);
    no_retry(&f, PWP_WRITE_UNCERTAIN); drain(&f, 1);
}
static void invalid_owner_is_never_guessed_or_closed(void) {
    const uint64_t invalid[] = {UINT64_MAX, UINT64_C(0x8000000000000000)};
    for (size_t i = 0; i < sizeof(invalid)/sizeof(invalid[0]); ++i) for (int success = 0; success <= 1; ++success) {
        fixture f; initialize(&f); f.create_owner = 0; f.override_token = 1; f.returned_token = invalid[i];
        f.prepare_result = success ? PWP_OK : PWP_OS;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.closes && !f.publishes && f.seals == 1);
        no_retry(&f, PWP_WRITE_UNCERTAIN); drain(&f, 1);
    }
}
static void missing_owner_unknown_still_seals_session(void) {
    fixture f; initialize(&f); f.create_owner = 0; f.prepare_result = PWP_CLEANUP_UNKNOWN;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.closes && f.seals == 1);
    no_retry(&f, PWP_WRITE_UNCERTAIN); drain(&f, 1);
}
static void invalid_result_codes_fail_closed(void) {
    const pwp_result invalid[] = {(pwp_result)-1, (pwp_result)99};
    for (size_t i = 0; i < sizeof(invalid)/sizeof(invalid[0]); ++i) {
        fixture f; initialize(&f); f.prepare_result = invalid[i];
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.publishes); expect_unknown(&f, 1);
        initialize(&f); f.publish_result = invalid[i];
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.syncs); expect_unknown(&f, 1);
        initialize(&f); f.sync_result = invalid[i];
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.directory_flushes); expect_unknown(&f, 1);
    }
}
static void publish_safe_rejection_preserves_pending_owner_only(void) {
    for (unsigned code = PWP_ARGUMENT; code <= PWP_UNIMPLEMENTED; ++code) {
        if (code == PWP_CLEANUP_UNKNOWN) continue;
        fixture f; initialize(&f); f.publish_result = (pwp_result)code;
        assert(apply(&f) == (pwp_result)code && !f.syncs && !f.namespace_changed && f.closes == 1 && !f.seals);
        assert(f.candidate.phase == PWP_CANDIDATE_VERIFIED);
        no_retry(&f, PWP_WRITE_FAILED); drain(&f, 0);
    }
}
static void publish_preverification_failure_is_not_attempted(void) {
    fixture f; initialize(&f); f.fail_rename_check = 1;
    assert(apply(&f) == PWP_POLICY && !f.rename_attempts && !f.syncs && f.closes == 1 && !f.seals);
    assert(f.candidate.phase == PWP_CANDIDATE_FAILED);
    no_retry(&f, PWP_WRITE_FAILED); drain(&f, 0);
}
static void publish_attempt_failure_is_uncertain(void) {
    fixture f; initialize(&f); f.fail_rename = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.namespace_changed && !f.syncs && !f.file_flushes);
    expect_unknown(&f, 1);
}
static void publish_postverification_and_file_flush_failures(void) {
    for (unsigned which = 0; which < 3; ++which) {
        fixture f; initialize(&f);
        if (which < 2) f.fail_rename_check = which+2; else f.fail_file_flush = 1;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.namespace_changed && !f.syncs);
        expect_unknown(&f, 1);
    }
}
static void publish_cleanup_failure_outranks_safe_refusal(void) {
    fixture f; initialize(&f); f.publish_result = PWP_POLICY; f.fail_candidate_close = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.namespace_changed && !f.syncs);
    expect_unknown(&f, 0);
}
static void every_sync_refusal_is_postpublication_uncertainty(void) {
    for (unsigned code = PWP_ARGUMENT; code <= PWP_UNIMPLEMENTED; ++code) {
        fixture f; initialize(&f); f.sync_result = (pwp_result)code;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.namespace_changed && !f.directory_flushes);
        expect_unknown(&f, 1);
    }
}
static void sync_source_preverification_failure_still_seals(void) {
    fixture f; initialize(&f); f.fail_before_sync = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.directory_flushes && !f.sync_checks);
    expect_unknown(&f, 1);
}
static void sync_directory_preverification_failure_still_seals(void) {
    fixture f; initialize(&f); f.fail_sync_check = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && !f.directory_flushes && f.sync_checks == 1);
    assert(f.directory_sync.phase == PWP_SYNC_READY); expect_unknown(&f, 1);
}
static void directory_flush_and_postverification_failures_seal(void) {
    for (unsigned which = 0; which < 2; ++which) {
        fixture f; initialize(&f);
        if (which) f.fail_sync_check = 2; else f.fail_directory_flush = 1;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.directory_flushes == 1);
        assert(f.directory_sync.phase == PWP_SYNC_UNCERTAIN); expect_unknown(&f, 1);
    }
}
static void final_source_check_failure_cannot_be_success(void) {
    fixture f; initialize(&f); f.fail_after_sync = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.namespace_synchronized && f.directory_flushes == 1);
    assert(f.directory_sync.phase == PWP_SYNC_READY); expect_unknown(&f, 1);
}
static void exact_original_grants_required_at_every_boundary(void) {
    const unsigned boundaries[] = {PREPARE, PUBLISH, SYNC, SYNC+10};
    for (size_t i = 0; i < sizeof(boundaries)/sizeof(boundaries[0]); ++i) {
        fixture f; initialize(&f); f.invalidate_grant_at = boundaries[i];
        pwp_result expected = boundaries[i] >= SYNC ? PWP_CLEANUP_UNKNOWN : PWP_POLICY;
        assert(apply(&f) == expected);
        if (expected == PWP_CLEANUP_UNKNOWN) expect_unknown(&f, 1);
        else { assert(!f.namespace_changed && !f.seals); no_retry(&f, PWP_WRITE_FAILED); drain(&f, 0); }
    }
}
static void candidate_close_is_part_of_write_success(void) {
    fixture f; initialize(&f); f.fail_candidate_close = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.namespace_synchronized && !f.close_succeeded);
    expect_unknown(&f, 0);
}
static void existing_uncertainty_never_repeats_seal_or_close(void) {
    fixture f; initialize(&f); f.fail_rename = f.fail_candidate_close = f.reenter = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.seals == 1 && f.closes == 1);
    expect_unknown(&f, 1);
}
static void independent_reverse_cleanup_continues_after_uncertainty(void) {
    fixture f; initialize(&f); f.fail_directory_flush = 1; f.fail_independent_close = 1;
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.close_succeeded);
    expect_unknown(&f, 1);
    const unsigned order[] = {6, 5, 4, 3, 2, 1};
    assert(f.close_count == 6 && memcmp(f.close_order, order, sizeof(order)) == 0);
    assert(pwp_lookup(&f.owner, f.source)->state == 4 && pwp_lookup(&f.owner, f.independent)->state == 4);
    assert(f.roles.root == f.root); /* Neither role ledger nor poisoned original owners were reset. */
}

int main(void) {
    valid_scopes_and_bounds(); invalid_names_rejected_before_work(); argument_rejection_never_adopts();
    nonnew_states_refuse_all_callbacks(); success_preserves_originals_through_close();
    callback_reentry_rejected_every_phase(); prepare_safe_failure_has_no_cleanup_obligation();
    late_prepared_owner_failure_is_still_closed(); late_prepare_unknown_seals_before_exact_close();
    late_prepare_close_fault_outranks_original_error(); success_without_owner_is_contract_uncertainty();
    invalid_owner_is_never_guessed_or_closed(); missing_owner_unknown_still_seals_session();
    invalid_result_codes_fail_closed(); publish_safe_rejection_preserves_pending_owner_only();
    publish_preverification_failure_is_not_attempted(); publish_attempt_failure_is_uncertain();
    publish_postverification_and_file_flush_failures(); publish_cleanup_failure_outranks_safe_refusal();
    every_sync_refusal_is_postpublication_uncertainty(); sync_source_preverification_failure_still_seals();
    sync_directory_preverification_failure_still_seals(); directory_flush_and_postverification_failures_seal();
    final_source_check_failure_cannot_be_success(); exact_original_grants_required_at_every_boundary();
    candidate_close_is_part_of_write_success(); existing_uncertainty_never_repeats_seal_or_close();
    independent_reverse_cleanup_continues_after_uncertainty();
    puts("PASS 28 portable record-write orchestration/ownership groups (not Windows runtime)");
    return 0;
}
