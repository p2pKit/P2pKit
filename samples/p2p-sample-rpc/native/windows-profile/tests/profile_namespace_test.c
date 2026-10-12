/* Real namespace/directory-sync/owner/role controllers with synthetic syscall/readback callbacks.
 * No Win32 emulation, NTFS/DACL/sharing execution, crash durability or complete-provider qualification. */
#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define NAME_MISSING UINT32_C(0xc0000034)
#define NAME_COLLISION UINT32_C(0xc0000035)
#define PATH_MISSING UINT32_C(0xc000003a)
enum { BOOTSTRAP, CHILD, PROFILE_LOCK, VAULT_LOCK };
typedef struct {
    uint64_t token, identity, parent;
    uintptr_t resource;
    int published, directory;
} original;
typedef struct {
    pwp_owner owner;
    pwp_roles roles;
    pwp_role_grant grant;
    pwp_namespace_commit commit;
    pwp_directory_sync directory_sync[16];
    original originals[6];
    uint64_t observed_id[16], observed_parent[16];
    uintptr_t observed_handle[16];
    uint32_t access[16];
    unsigned physical_closes[16], close_order[16], close_count;
    unsigned original_count, calls, seals, sync_count, file_flushes, directory_flushes, publications, bindings;
    unsigned fail_at, mutate_at, mutation, reenter;
    unsigned active_sync, acknowledged[3], acknowledged_count;
    uint64_t root, profile, identity, target, returned, sync_order[3], floor, close_failure;
    int mode, created, failure_result, fail_publish, fail_bind, public_observation;
    char trace[96];
    int namespace_bad[16];
} fixture;
static pwp_result apply(fixture *f);
static uint64_t add(fixture *f, int published, int directory, uint64_t parent) {
    uint64_t token = 0;
    assert(pwp_reserve(&f->owner, &token) == PWP_OK && token < 16);
    uintptr_t resource = (uintptr_t)(0x10000u+token);
    assert(pwp_attach(&f->owner, token, resource) == PWP_OK);
    if (published) assert(pwp_publish(&f->owner, token) == PWP_OK);
    original *o = &f->originals[f->original_count++];
    *o = (original){token, 0x100000u+token, parent, resource, published, directory};
    f->observed_id[token] = o->identity; f->observed_parent[token] = parent;
    f->observed_handle[token] = resource; f->access[token] = PWP_DIRECTORY_SYNC_ACCESS;
    return token;
}
static void init(fixture *f, int mode, int created) {
    memset(f, 0, sizeof(*f)); pwp_owner_init(&f->owner); pwp_roles_init(&f->roles);
    f->mode = mode; f->created = created; f->failure_result = PWP_POLICY;
    assert(pwp_roles_begin_root(&f->roles, &f->owner) == PWP_OK); f->floor = f->roles.root_floor;
    if (mode == BOOTSTRAP) {
        uint64_t local = add(f, 0, 1, 0), vendor = add(f, 0, 1, local);
        f->root = f->target = add(f, 0, 1, vendor);
        f->sync_order[0] = f->root; f->sync_order[1] = vendor; f->sync_order[2] = local;
        f->sync_count = 3; return;
    }
    f->root = add(f, 1, 1, 0);
    assert(pwp_roles_bind_root(&f->roles, &f->owner, f->root) == PWP_OK);
    if (mode != PROFILE_LOCK) {
        f->profile = add(f, 1, 0, f->root);
        assert(pwp_roles_bind_lease(&f->roles, &f->owner, f->root, PWP_LEASE_PROFILE, f->profile) == PWP_OK);
        assert(pwp_roles_capture(&f->roles, &f->owner, f->root, &f->grant) == PWP_OK);
    }
    if (mode == VAULT_LOCK) {
        f->identity = add(f, 1, 1, f->root);
        assert(pwp_roles_bind_identity(&f->roles, &f->owner, f->root, f->identity) == PWP_OK);
    }
    f->target = add(f, 0, mode == CHILD, mode == VAULT_LOCK ? f->identity : f->root);
    f->sync_order[0] = f->target; f->sync_order[1] = mode == VAULT_LOCK ? f->identity : f->root;
    f->sync_count = 2;
}
static int observe(fixture *f, char event) {
    assert(f->calls < sizeof(f->trace) && f->commit.phase >= PWP_NAMESPACE_VERIFYING &&
        f->commit.phase <= PWP_NAMESPACE_PUBLISHING);
    f->trace[f->calls++] = event;
    assert(!f->returned);
    if (event != 'B') {
        pwp_owned_handle *target = pwp_lookup(&f->owner, f->target);
        assert(target && target->state == 2 && !target->published);
    }
    if (f->reenter) {
        unsigned calls = f->calls;
        assert(apply(f) == PWP_CLOSED && f->calls == calls && !f->seals);
    }
    if (f->mutate_at == f->calls) {
        if (f->mutation == 0) ++f->observed_id[f->target];
        if (f->mutation == 1) ++f->observed_handle[f->root];
        if (f->mutation == 2) ++f->observed_parent[f->target];
        if (f->mutation == 3) f->access[f->root] ^= 2;
        if (f->mutation == 4) {
            if (f->mode == BOOTSTRAP) ++f->floor;
            else if (f->mode == PROFILE_LOCK) f->public_observation = 1;
            else ++f->grant.profile;
        }
    }
    return f->calls != f->fail_at;
}
static int scope(fixture *f, int published_target) {
    if (f->owner.poisoned || f->public_observation) return 0;
    for (unsigned i = 0; i < f->original_count; ++i) {
        original *o = &f->originals[i]; pwp_owned_handle *h = pwp_lookup(&f->owner, o->token);
        if (!h || h->state != 2 || h->resource != o->resource ||
            h->published != (o->published || (published_target && o->token == f->target)) ||
            f->observed_id[o->token] != o->identity || f->observed_handle[o->token] != o->resource ||
            f->observed_parent[o->token] != o->parent || f->namespace_bad[o->token] ||
            (o->directory && !pwp_directory_sync_access(1, f->access[o->token]))) return 0;
    }
    if (f->mode == BOOTSTRAP)
        return f->roles.opening && !f->roles.root && !f->roles.profile && !f->roles.identity && !f->roles.vault &&
            f->roles.root_floor == f->floor && pwp_public_count(&f->owner) == (size_t)published_target;
    if (f->roles.root != f->root) return 0;
    if (f->mode == CHILD)
        return pwp_roles_identity_admit(&f->roles, &f->owner, f->root) == PWP_OK &&
            pwp_roles_check_grant(&f->roles, &f->owner, &f->grant) == PWP_OK;
    if (f->mode == PROFILE_LOCK)
        return pwp_roles_lease_admit(&f->roles, &f->owner, f->root, PWP_LEASE_PROFILE) == PWP_OK;
    return f->roles.identity == f->identity && !f->grant.vault && f->grant.directory == f->root &&
        pwp_roles_check_grant(&f->roles, &f->owner, &f->grant) == PWP_OK &&
        pwp_roles_lease_admit(&f->roles, &f->owner, f->identity, PWP_LEASE_VAULT) == PWP_OK;
}
static pwp_result verify_namespace(void *opaque) {
    fixture *f = opaque;
    assert(f->commit.phase == PWP_NAMESPACE_VERIFYING);
    return observe(f, 'V') && scope(f, 0) ? PWP_OK : (pwp_result)f->failure_result;
}
static int verify_directory(void *opaque) {
    fixture *f = opaque;
    assert(f->commit.phase == PWP_NAMESPACE_SYNCING && f->directory_sync[f->active_sync].phase == PWP_SYNC_RUNNING);
    return observe(f, 'D') && scope(f, 0);
}
static int flush_directory(void *opaque) {
    fixture *f = opaque; ++f->directory_flushes;
    return observe(f, 'F');
}
static pwp_result sync_namespace(size_t index, void *opaque) {
    fixture *f = opaque;
    assert(f->commit.phase == PWP_NAMESPACE_SYNCING && index < f->sync_count && index == f->acknowledged_count);
    if (!observe(f, 'S') || !scope(f, 0)) return (pwp_result)f->failure_result;
    uint64_t target = f->sync_order[index];
    pwp_result r;
    if ((f->mode == PROFILE_LOCK || f->mode == VAULT_LOCK) && index == 0) {
        ++f->file_flushes; r = observe(f, 'F') ? PWP_OK : PWP_OS;
    } else {
        f->active_sync = (unsigned)target;
        r = pwp_directory_sync_apply(&f->directory_sync[target], verify_directory, flush_directory, f);
    }
    if (r == PWP_OK) f->acknowledged[f->acknowledged_count++] = (unsigned)target;
    return r;
}
static pwp_result publish_namespace(void *opaque) {
    fixture *f = opaque; assert(f->commit.phase == PWP_NAMESPACE_PUBLISHING);
    assert(f->acknowledged_count == f->sync_count);
    if (!observe(f, 'P') || !scope(f, 0)) return (pwp_result)f->failure_result;
    ++f->publications;
    if (f->fail_publish) return PWP_LIMIT;
    pwp_result r = pwp_publish(&f->owner, f->target);
    if (r != PWP_OK) return r;
    if (!observe(f, 'B') || !scope(f, 1) || f->fail_bind) return PWP_POLICY;
    ++f->bindings;
    if (f->mode == BOOTSTRAP) r = pwp_roles_bind_root(&f->roles, &f->owner, f->target);
    else if (f->mode == CHILD) r = pwp_roles_bind_identity(&f->roles, &f->owner, f->root, f->target);
    else r = pwp_roles_bind_lease(&f->roles, &f->owner, f->mode == PROFILE_LOCK ? f->root : f->identity,
                                   f->mode == PROFILE_LOCK ? PWP_LEASE_PROFILE : PWP_LEASE_VAULT, f->target);
    if (r == PWP_OK) f->returned = f->target;
    return r;
}
static void seal_namespace(void *opaque) {
    fixture *f = opaque;
    assert(f->commit.phase == PWP_NAMESPACE_UNCERTAIN && ++f->seals == 1 && !f->close_count && !f->returned);
    for (unsigned i = 0; i < f->original_count; ++i) {
        original *o = &f->originals[i]; pwp_owned_handle *h = pwp_lookup(&f->owner, o->token);
        assert(h && h->state == 2 && h->resource == o->resource); /* Marking never pretends to close. */
        f->namespace_bad[o->token] = 1;
    }
    f->owner.poisoned = 1;
}
static pwp_result apply(fixture *f) {
    return pwp_namespace_commit_apply(&f->commit, f->created, f->sync_count, verify_namespace, sync_namespace,
                                       publish_namespace, seal_namespace, f);
}
static int close_original(uintptr_t resource, void *opaque) {
    fixture *f = opaque;
    assert(resource > 0x10000u && resource < 0x10010u); unsigned token = (unsigned)(resource-0x10000u);
    pwp_owned_handle *h = pwp_lookup(&f->owner, token);
    assert(h && h->state == 4 && h->resource == resource && ++f->physical_closes[token] == 1);
    f->close_order[f->close_count++] = token;
    /* Observe physical close before classifying uncertainty; failed values are never retried. */
    int closed = token != f->close_failure;
    return closed && !f->namespace_bad[token] && pwp_directory_sync_close_ok(&f->directory_sync[token], 1);
}
static void drain(fixture *f, pwp_result expected) {
    assert(pwp_roles_retire_all(&f->roles, &f->owner, close_original, f) == expected);
    assert(f->close_count == f->original_count);
    for (unsigned i = 0; i < f->close_count; ++i)
        assert(f->close_order[i] == f->originals[f->original_count-i-1].token);
    unsigned count = f->close_count;
    assert(pwp_roles_retire_all(&f->roles, &f->owner, close_original, f) == expected && f->close_count == count);
}
static void raw_collision_requires_exact_final_status_and_null(void) {
    const uint32_t statuses[] = {0, 0x103, NAME_COLLISION, NAME_MISSING, PATH_MISSING,
        0xc0000022, 0xc0000043, 0xc0000056, 0xffffffff};
    const int nulls[] = {-1, 0, 1, 2};
    for (size_t i = 0; i < sizeof(statuses)/sizeof(statuses[0]); ++i)
        for (size_t j = 0; j < sizeof(nulls)/sizeof(nulls[0]); ++j)
            assert(pwp_create_collision_without_effect(statuses[i], nulls[j]) ==
                (statuses[i] == NAME_COLLISION && nulls[j] == 1));
}
static void invalid_arguments_never_take_ownership(void) {
    fixture f; init(&f, BOOTSTRAP, 0);
    assert(pwp_namespace_commit_apply(NULL, 0, 3, verify_namespace, sync_namespace,
                                       publish_namespace, seal_namespace, &f) == PWP_ARGUMENT);
    const int created[] = {-1, 2};
    for (unsigned i = 0; i < 2; ++i) {
        f.created = created[i]; assert(apply(&f) == PWP_ARGUMENT && f.commit.phase == PWP_NAMESPACE_NEW);
    }
    f.created = 0;
    const size_t counts[] = {0, 4, SIZE_MAX};
    for (unsigned i = 0; i < 3; ++i) { f.sync_count = (unsigned)counts[i]; assert(apply(&f) == PWP_ARGUMENT); }
    assert(pwp_namespace_commit_apply(&f.commit, 0, SIZE_MAX, verify_namespace, sync_namespace,
                                       publish_namespace, seal_namespace, &f) == PWP_ARGUMENT);
    assert(pwp_namespace_commit_apply(&f.commit, 0, 3, NULL, sync_namespace,
                                       publish_namespace, seal_namespace, &f) == PWP_ARGUMENT);
    assert(pwp_namespace_commit_apply(&f.commit, 0, 3, verify_namespace, NULL,
                                       publish_namespace, seal_namespace, &f) == PWP_ARGUMENT);
    assert(pwp_namespace_commit_apply(&f.commit, 0, 3, verify_namespace, sync_namespace,
                                       NULL, seal_namespace, &f) == PWP_ARGUMENT);
    assert(pwp_namespace_commit_apply(&f.commit, 0, 3, verify_namespace, sync_namespace,
                                       publish_namespace, NULL, &f) == PWP_ARGUMENT);
    assert(!f.calls && !f.seals && !f.close_count && !f.owner.poisoned); drain(&f, PWP_OK);
}
static void every_nonnew_phase_refuses_reentry(void) {
    const pwp_namespace_phase phases[] = {PWP_NAMESPACE_VERIFYING, PWP_NAMESPACE_SYNCING,
        PWP_NAMESPACE_PUBLISHING, PWP_NAMESPACE_COMPLETE, PWP_NAMESPACE_FAILED, PWP_NAMESPACE_UNCERTAIN,
        (pwp_namespace_phase)-1, (pwp_namespace_phase)99};
    for (unsigned i = 0; i < sizeof(phases)/sizeof(phases[0]); ++i) {
        fixture f; init(&f, CHILD, 1); f.commit.phase = phases[i];
        assert(apply(&f) == PWP_CLOSED && !f.calls && !f.seals && f.commit.phase == phases[i]); drain(&f, PWP_OK);
    }
}
static void bootstrap_always_acknowledges_all_three_original_directories(void) {
    for (int created = 0; created <= 1; ++created) {
        fixture f; init(&f, BOOTSTRAP, created);
        assert(apply(&f) == PWP_OK && f.commit.phase == PWP_NAMESPACE_COMPLETE && f.returned == f.target);
        assert(f.directory_flushes == 3 && !f.file_flushes && f.acknowledged_count == 3);
        const char order[] = "VSDFDVSDFDVSDFDVPB";
        assert(f.calls == sizeof(order)-1 && !memcmp(f.trace, order, sizeof(order)-1));
        assert(f.acknowledged[0] == 3 && f.acknowledged[1] == 2 && f.acknowledged[2] == 1);
        assert(f.roles.root == f.target && !f.roles.opening && f.publications == 1 && f.bindings == 1);
        drain(&f, PWP_OK);
    }
}
static void child_acknowledges_self_then_original_root(void) {
    fixture f; init(&f, CHILD, 1); assert(apply(&f) == PWP_OK);
    const char order[] = "VSDFDVSDFDVPB";
    assert(f.calls == sizeof(order)-1 && !memcmp(f.trace, order, sizeof(order)-1));
    assert(f.directory_flushes == 2 && !f.file_flushes && f.acknowledged_count == 2);
    assert(f.acknowledged[0] == f.target && f.acknowledged[1] == f.root && f.roles.identity == f.target);
    assert(f.roles.profile == f.profile && f.returned == f.target); drain(&f, PWP_OK);
}
static void locks_acknowledge_file_then_original_containing_directory(void) {
    for (int mode = PROFILE_LOCK; mode <= VAULT_LOCK; ++mode) {
        fixture f; init(&f, mode, 1); assert(apply(&f) == PWP_OK);
        const char order[] = "VSFVSDFDVPB";
        assert(f.calls == sizeof(order)-1 && !memcmp(f.trace, order, sizeof(order)-1));
        assert(f.file_flushes == 1 && f.directory_flushes == 1 && f.returned == f.target);
        assert(f.acknowledged[0] == f.target && f.acknowledged[1] == (mode == PROFILE_LOCK ? f.root : f.identity));
        assert((mode == PROFILE_LOCK ? f.roles.profile : f.roles.vault) == f.target);
        if (mode == VAULT_LOCK) assert(f.roles.vault_profile == f.profile && f.roles.profile == f.profile);
        drain(&f, PWP_OK);
    }
}
static void callback_reentry_cannot_publish_or_repeat_an_acknowledgment(void) {
    for (int mode = BOOTSTRAP; mode <= VAULT_LOCK; ++mode) {
        fixture f; init(&f, mode, 1); f.reenter = 1;
        assert(apply(&f) == PWP_OK && !f.seals && f.returned == f.target);
        unsigned calls = f.calls; assert(apply(&f) == PWP_CLOSED && f.calls == calls); drain(&f, PWP_OK);
    }
}
static void every_postcreation_callback_failure_is_sticky_unknown(void) {
    for (int mode = BOOTSTRAP; mode <= VAULT_LOCK; ++mode) {
        fixture base; init(&base, mode, 1); assert(apply(&base) == PWP_OK); unsigned count = base.calls;
        drain(&base, PWP_OK);
        for (unsigned step = 1; step <= count; ++step) {
            fixture f; init(&f, mode, 1); f.fail_at = step;
            assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.seals == 1 && !f.returned);
            assert(f.commit.phase == PWP_NAMESPACE_UNCERTAIN && f.calls == step && !f.close_count);
            assert(apply(&f) == PWP_CLOSED && f.calls == step); drain(&f, PWP_CLEANUP_UNKNOWN);
        }
    }
}
static void existing_bootstrap_precheck_can_fail_cleanly_but_any_sync_entry_cannot(void) {
    fixture baseline; init(&baseline, BOOTSTRAP, 0); assert(apply(&baseline) == PWP_OK);
    unsigned count = baseline.calls; drain(&baseline, PWP_OK);
    for (unsigned step = 1; step <= count; ++step) {
        fixture f; init(&f, BOOTSTRAP, 0); f.fail_at = step;
        assert(apply(&f) == (step == 1 ? PWP_POLICY : PWP_CLEANUP_UNKNOWN));
        assert(f.seals == (unsigned)(step != 1) && !f.returned);
        drain(&f, step == 1 ? PWP_OK : PWP_CLEANUP_UNKNOWN);
    }
}
static void changed_original_identity_handle_parent_access_or_grant_never_publishes(void) {
    for (int mode = BOOTSTRAP; mode <= VAULT_LOCK; ++mode) {
        fixture baseline; init(&baseline, mode, 1); assert(apply(&baseline) == PWP_OK);
        unsigned count = baseline.calls; drain(&baseline, PWP_OK);
        for (unsigned kind = 0; kind <= 4; ++kind) for (unsigned step = 1; step <= count; ++step) {
            fixture f; init(&f, mode, 1); f.mutate_at = step; f.mutation = kind;
            assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.seals == 1 && !f.returned);
            assert(f.calls >= step && f.commit.phase == PWP_NAMESPACE_UNCERTAIN); drain(&f, PWP_CLEANUP_UNKNOWN);
        }
    }
}
static void publication_and_role_binding_failures_preserve_unreturned_owner(void) {
    for (int mode = BOOTSTRAP; mode <= VAULT_LOCK; ++mode) for (int when = 0; when < 2; ++when) {
        fixture f; init(&f, mode, 1); f.fail_publish = when == 0; f.fail_bind = when == 1;
        assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.seals == 1 && !f.returned && !f.bindings);
        assert(f.acknowledged_count == f.sync_count && !f.close_count);
        assert(pwp_lookup(&f.owner, f.target)->published == (when == 1)); drain(&f, PWP_CLEANUP_UNKNOWN);
    }
}
static void invalid_callback_results_never_become_success(void) {
    const int results[] = {-1, 99, PWP_NOT_FOUND, PWP_UNIMPLEMENTED, PWP_CLEANUP_UNKNOWN};
    for (unsigned i = 0; i < sizeof(results)/sizeof(results[0]); ++i) for (int created = 0; created < 2; ++created) {
        fixture f; init(&f, BOOTSTRAP, created); f.fail_at = 1; f.failure_result = results[i];
        pwp_result expected = results[i] < 0 || results[i] > PWP_UNIMPLEMENTED ?
            PWP_CLEANUP_UNKNOWN : (pwp_result)results[i];
        if (created) expected = PWP_CLEANUP_UNKNOWN;
        assert(apply(&f) == expected && !f.returned && !f.directory_flushes);
        drain(&f, expected == PWP_CLEANUP_UNKNOWN ? PWP_CLEANUP_UNKNOWN : PWP_OK);
    }
}
static void physical_close_failure_is_not_retried_or_allowed_to_skip_other_owners(void) {
    for (int mode = BOOTSTRAP; mode <= VAULT_LOCK; ++mode) {
        fixture f; init(&f, mode, 1); assert(apply(&f) == PWP_OK); f.close_failure = f.target;
        drain(&f, PWP_CLEANUP_UNKNOWN);
        assert(pwp_lookup(&f.owner, f.target)->state == 4 && f.physical_closes[f.target] == 1);
    }
}
static void provisional_admission_is_not_public_mutation_authority(void) {
    for (int mode = BOOTSTRAP; mode <= VAULT_LOCK; ++mode) {
        fixture f; init(&f, mode, 1); pwp_role_grant not_granted;
        uint64_t directory = mode == BOOTSTRAP || mode == PROFILE_LOCK ? f.root :
            mode == VAULT_LOCK ? f.identity : f.target;
        assert(pwp_roles_capture(&f.roles, &f.owner, directory, &not_granted) == PWP_POLICY);
        assert(!pwp_lookup(&f.owner, f.target)->published && !f.returned); drain(&f, PWP_OK);
    }
}

/* Raw opening/creation failure controls exercise the SAME strict predicates and original owner drain
 * used by the Win32 wrapper; syscall/access/token behavior itself remains a Windows runtime gate. */
typedef struct { pwp_owner owner; uint64_t token; unsigned closes, verified, creates; int fail_close; } probe;
static int probe_close(uintptr_t raw, void *opaque) {
    probe *p = opaque; assert(raw == 99 && ++p->closes == 1);
    assert(pwp_lookup(&p->owner, p->token)->state == 4); return !p->fail_close;
}
static int verify_after_retirement(void *opaque) {
    probe *p = opaque; ++p->verified;
    assert(pwp_lookup(&p->owner, p->token)->state == 3 && !p->closes); return 1;
}
static void probe_init(probe *p, int returned) {
    memset(p, 0, sizeof(*p)); pwp_owner_init(&p->owner); assert(pwp_reserve(&p->owner, &p->token) == PWP_OK);
    if (returned) assert(pwp_attach(&p->owner, p->token, 99) == PWP_OK);
}
static void strict_missing_does_not_accept_path_missing_access_pending_or_a_late_handle(void) {
    const uint32_t statuses[] = {0, 0x103, NAME_MISSING, PATH_MISSING, NAME_COLLISION, 0xc0000022, 0xc0000043};
    for (unsigned i = 0; i < sizeof(statuses)/sizeof(statuses[0]); ++i) for (int handle = 0; handle < 3; ++handle) {
        probe p; probe_init(&p, handle == 1);
        pwp_result r = pwp_name_absence_finish(&p.owner, p.token, statuses[i], handle == 0,
                                               verify_after_retirement, probe_close, &p);
        int absent = statuses[i] == NAME_MISSING && handle == 0;
        assert(r == (absent ? PWP_NOT_FOUND : PWP_CLEANUP_UNKNOWN));
        assert(p.verified == (unsigned)absent && p.closes == (unsigned)(handle == 1));
        if (r == PWP_NOT_FOUND) ++p.creates;
        assert(p.creates == (unsigned)absent); /* Same strict predicate; invalid non-NULL sentinel never creates. */
    }
}
static void failed_probe_retirement_never_reaches_a_create(void) {
    probe p; probe_init(&p, 1); p.fail_close = 1;
    assert(pwp_name_absence_finish(&p.owner, p.token, NAME_MISSING, 0,
                                    verify_after_retirement, probe_close, &p) == PWP_CLEANUP_UNKNOWN);
    assert(p.closes == 1 && !p.verified && !p.creates && p.owner.poisoned);
    assert(pwp_retire_all(&p.owner, probe_close, &p) == PWP_CLEANUP_UNKNOWN && p.closes == 1);
}
static void failed_create_without_a_handle_still_carries_uncertainty(void) {
    const uint32_t statuses[] = {0, 0x103, NAME_COLLISION, NAME_MISSING, PATH_MISSING, 0xc0000022, 0xc0000043};
    for (unsigned i = 0; i < sizeof(statuses)/sizeof(statuses[0]); ++i) {
        probe p; probe_init(&p, 0);
        int effect = !pwp_create_collision_without_effect(statuses[i], 1);
        if (effect) p.owner.poisoned = 1;
        assert(pwp_retire(&p.owner, p.token, probe_close, &p) == PWP_OK && !p.closes);
        assert(pwp_cleanup_result(PWP_OS, effect, p.owner.poisoned) ==
            (statuses[i] == NAME_COLLISION ? PWP_OS : PWP_CLEANUP_UNKNOWN));
    }
}
static void late_failed_create_owner_is_actually_closed_once_with_no_collision_escape(void) {
    const uint32_t statuses[] = {0, 0x103, NAME_COLLISION, NAME_MISSING, PATH_MISSING, 0xc0000022};
    for (unsigned i = 0; i < sizeof(statuses)/sizeof(statuses[0]); ++i) for (int fails = 0; fails < 2; ++fails) {
        probe p; probe_init(&p, 1); p.fail_close = fails;
        assert(!pwp_create_collision_without_effect(statuses[i], 0)); p.owner.poisoned = 1;
        pwp_result r = pwp_retire(&p.owner, p.token, probe_close, &p);
        assert(pwp_cleanup_result(r, 1, p.owner.poisoned) == PWP_CLEANUP_UNKNOWN && p.closes == 1);
        (void)pwp_retire_all(&p.owner, probe_close, &p); assert(p.closes == 1);
    }
}
static void precreate_refusal_has_no_effect_or_physical_owner(void) {
    probe p; probe_init(&p, 0);
    assert(pwp_retire(&p.owner, p.token, probe_close, &p) == PWP_OK && !p.closes && !p.owner.poisoned);
    assert(pwp_cleanup_result(PWP_POLICY, 0, 0) == PWP_POLICY);
}
static void earlier_vendor_creation_survives_later_bootstrap_failure(void) {
    fixture f; init(&f, BOOTSTRAP, 1); f.fail_at = 1;
    /* created remains set from P2pKit even if the later RpcProfile acquisition cannot be finalized. */
    assert(apply(&f) == PWP_CLEANUP_UNKNOWN && f.seals == 1 && !f.directory_flushes && !f.returned);
    drain(&f, PWP_CLEANUP_UNKNOWN);
}
/* The generic controller's count1 contract is not a production one-directory bootstrap path. */
typedef struct {
    pwp_namespace_commit commit;
    unsigned verifies, syncs, publications, seals;
    int fail, result;
} bounded;
static pwp_result bounded_verify(void *opaque) {
    bounded *b = opaque; ++b->verifies;
    return b->fail == 1 ? (pwp_result)b->result : PWP_OK;
}
static pwp_result bounded_sync(size_t index, void *opaque) {
    bounded *b = opaque; assert(index == b->syncs); ++b->syncs;
    return b->fail == 2 ? (pwp_result)b->result : PWP_OK;
}
static pwp_result bounded_publish(void *opaque) {
    bounded *b = opaque; ++b->publications;
    return b->fail == 3 ? (pwp_result)b->result : PWP_OK;
}
static void bounded_seal(void *opaque) {
    bounded *b = opaque; assert(b->commit.phase == PWP_NAMESPACE_UNCERTAIN && ++b->seals == 1);
}
static void generic_controller_accepts_only_the_requested_one_to_three_acknowledgments(void) {
    for (size_t count = 1; count <= 3; ++count) {
        bounded b = {0};
        assert(pwp_namespace_commit_apply(&b.commit, 0, count, bounded_verify, bounded_sync,
                                           bounded_publish, bounded_seal, &b) == PWP_OK);
        assert(b.syncs == count && b.verifies == count+1 && b.publications == 1 && !b.seals);
    }
}
static void every_callback_result_is_normalized_and_post_sync_failure_is_unknown(void) {
    const int results[] = {PWP_ARGUMENT, PWP_POLICY, PWP_OS, PWP_BUSY, PWP_CLOSED, PWP_LIMIT,
        PWP_NOT_FOUND, PWP_CLEANUP_UNKNOWN, PWP_UNIMPLEMENTED, -1, 99};
    for (unsigned i = 0; i < sizeof(results)/sizeof(results[0]); ++i) for (int where = 1; where <= 3; ++where) {
        bounded b = {0}; b.fail = where; b.result = results[i];
        pwp_result expected = where != 1 || results[i] < 0 || results[i] > PWP_UNIMPLEMENTED ?
            PWP_CLEANUP_UNKNOWN : (pwp_result)results[i];
        assert(pwp_namespace_commit_apply(&b.commit, 0, 3, bounded_verify, bounded_sync,
                                           bounded_publish, bounded_seal, &b) == expected);
        assert(b.seals == (unsigned)(expected == PWP_CLEANUP_UNKNOWN));
        assert(b.syncs == (where == 1 ? 0u : where == 2 ? 1u : 3u));
    }
}
int main(void) {
    raw_collision_requires_exact_final_status_and_null(); invalid_arguments_never_take_ownership();
    every_nonnew_phase_refuses_reentry(); bootstrap_always_acknowledges_all_three_original_directories();
    child_acknowledges_self_then_original_root(); locks_acknowledge_file_then_original_containing_directory();
    callback_reentry_cannot_publish_or_repeat_an_acknowledgment(); every_postcreation_callback_failure_is_sticky_unknown();
    existing_bootstrap_precheck_can_fail_cleanly_but_any_sync_entry_cannot();
    changed_original_identity_handle_parent_access_or_grant_never_publishes();
    publication_and_role_binding_failures_preserve_unreturned_owner(); invalid_callback_results_never_become_success();
    physical_close_failure_is_not_retried_or_allowed_to_skip_other_owners();
    provisional_admission_is_not_public_mutation_authority();
    strict_missing_does_not_accept_path_missing_access_pending_or_a_late_handle();
    failed_probe_retirement_never_reaches_a_create(); failed_create_without_a_handle_still_carries_uncertainty();
    late_failed_create_owner_is_actually_closed_once_with_no_collision_escape();
    precreate_refusal_has_no_effect_or_physical_owner(); earlier_vendor_creation_survives_later_bootstrap_failure();
    generic_controller_accepts_only_the_requested_one_to_three_acknowledgments();
    every_callback_result_is_normalized_and_post_sync_failure_is_unknown();
    puts("22 portable namespace/owner/role/sync groups PASS; NOT Windows runtime or crash qualification");
    return 0;
}
