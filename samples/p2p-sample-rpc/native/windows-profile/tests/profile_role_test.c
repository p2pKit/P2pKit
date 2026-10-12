#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Actual shared role/owner controllers with synthetic resources, not Windows file/ACL/share emulation.
 * Native original-handle fixed-scope and empty-file verification remains a separate Windows obligation. */
typedef struct {
    pwp_owner owner;
    pwp_roles roles;
    uintptr_t closed[PWP_HANDLE_LIMIT*4];
    size_t closes;
    uintptr_t fail_resource;
    int reject_verify, probe_terminal;
} fixture;
static int close_handle(uintptr_t resource, void *context) {
    fixture *f = context;
    assert(resource && f->closes < sizeof(f->closed)/sizeof(f->closed[0]));
    int retiring = 0;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i)
        if (f->owner.slots[i].resource == resource && f->owner.slots[i].state == 4) ++retiring;
    assert(retiring == 1);
    f->closed[f->closes++] = resource;
    if (f->probe_terminal) {
        pwp_result denied = f->owner.poisoned ? PWP_CLEANUP_UNKNOWN : PWP_BUSY;
        pwp_role_grant grant;
        assert(pwp_roles_capture(&f->roles, &f->owner, f->roles.root, &grant) == denied);
        assert(pwp_roles_begin_root(&f->roles, &f->owner) == denied);
        assert(pwp_roles_bind_root(&f->roles, &f->owner, f->roles.root) == denied);
        assert(pwp_roles_retire_all(&f->roles, &f->owner, close_handle, f) == PWP_BUSY);
    }
    return resource != f->fail_resource;
}
static int verify(void *context) { return !((fixture *)context)->reject_verify; }
static int flush(void *context) { (void)context; return 1; }
static uint64_t add(fixture *f, int published) {
    uint64_t token = 0;
    assert(pwp_reserve(&f->owner, &token) == PWP_OK);
    assert(pwp_attach(&f->owner, token, (uintptr_t)token) == PWP_OK);
    if (published) assert(pwp_publish(&f->owner, token) == PWP_OK);
    return token;
}
static void init(fixture *f) {
    memset(f, 0, sizeof(*f)); pwp_owner_init(&f->owner); pwp_roles_init(&f->roles);
}
static uint64_t root(fixture *f) {
    assert(pwp_roles_begin_root(&f->roles, &f->owner) == PWP_OK);
    uint64_t token = add(f, 1);
    assert(pwp_roles_bind_root(&f->roles, &f->owner, token) == PWP_OK);
    return token;
}
static uint64_t identity(fixture *f) {
    assert(pwp_roles_identity_admit(&f->roles, &f->owner, f->roles.root) == PWP_OK);
    uint64_t token = add(f, 1);
    assert(pwp_roles_bind_identity(&f->roles, &f->owner, f->roles.root, token) == PWP_OK);
    return token;
}
static uint64_t lease(fixture *f, pwp_lease_role role) {
    uint64_t directory = role == PWP_LEASE_PROFILE ? f->roles.root : f->roles.identity;
    assert(pwp_roles_lease_admit(&f->roles, &f->owner, directory, role) == PWP_OK);
    uint64_t token = add(f, 0);
    assert(pwp_roles_bind_lease(&f->roles, &f->owner, directory, role, token) == PWP_POLICY);
    assert(pwp_lock_finish(&f->owner, token, verify, flush, close_handle, f) == PWP_OK);
    assert(pwp_roles_bind_lease(&f->roles, &f->owner, directory, role, token) == PWP_OK);
    return token;
}
static uint64_t stage(fixture *f, uint64_t directory) {
    pwp_role_grant grant;
    assert(pwp_roles_capture(&f->roles, &f->owner, directory, &grant) == PWP_OK);
    uint64_t token = add(f, 1);
    assert(pwp_roles_bind_stage(&f->roles, &f->owner, token, &grant) == PWP_OK);
    return token;
}
static pwp_result retire(fixture *f, uint64_t token) {
    return pwp_roles_retire(&f->roles, &f->owner, token, close_handle, f);
}
static void complete(fixture *f) {
    uint64_t next = f->owner.next;
    assert(pwp_roles_retire_all(&f->roles, &f->owner, close_handle, f) == PWP_OK);
    size_t count = f->closes;
    assert(pwp_roles_retire_all(&f->roles, &f->owner, close_handle, f) == PWP_OK && f->closes == count);
    assert(!f->roles.root && !f->roles.profile && !f->roles.vault && !f->roles.identity && !f->owner.poisoned);
    assert(f->owner.next == next);
}
static size_t wide(uint16_t output[96], const char *name) {
    size_t count = strlen(name); assert(count < 96);
    for (size_t i = 0; i <= count; ++i) output[i] = (uint16_t)(unsigned char)name[i];
    return count;
}
static void fixed_names_are_selectors_not_authority(void) {
    uint16_t name[96]; size_t count = wide(name, "profile.lock");
    assert(pwp_lease_name(name, count) == PWP_LEASE_PROFILE);
    count = wide(name, "vault.lock"); assert(pwp_lease_name(name, count) == PWP_LEASE_VAULT);
    const char *bad[] = {"", "other.lock", "PROFILE.LOCK", "Vault.lock", "profile.lock.",
        "profile.lock:stream", "profile.lock/child", "vault.lock.bak", "identity", "profile.header"};
    for (size_t i = 0; i < sizeof(bad)/sizeof(bad[0]); ++i) {
        count = wide(name, bad[i]); assert(pwp_lease_name(name, count) == PWP_LEASE_NONE);
    }
    count = wide(name, "profile.lock"); name[3] = 0;
    assert(pwp_lease_name(name, count) == PWP_LEASE_NONE);
    assert(pwp_lease_name(NULL, 12) == PWP_LEASE_NONE && pwp_lease_name(name, SIZE_MAX) == PWP_LEASE_NONE);
    fixture f; init(&f); uint64_t r = root(&f); pwp_role_grant grant;
    assert(pwp_roles_capture(&f.roles, &f.owner, r, &grant) == PWP_POLICY); complete(&f);
}
static void root_admission_requires_retired_owners_and_publication(void) {
    fixture f; init(&f); uint64_t leftover = add(&f, 0);
    assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_BUSY);
    assert(retire(&f, leftover) == PWP_OK);
    assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_OK);
    uint64_t r = add(&f, 0);
    assert(pwp_roles_bind_root(&f.roles, &f.owner, r) == PWP_POLICY);
    assert(pwp_publish(&f.owner, r) == PWP_OK);
    assert(pwp_roles_bind_root(&f.roles, &f.owner, r) == PWP_OK);
    assert(pwp_roles_bind_root(&f.roles, &f.owner, r) == PWP_BUSY);
    assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_BUSY);
    assert(retire(&f, r) == PWP_BUSY && pwp_lookup(&f.owner, r)->state == 2);
    complete(&f);
}
static void partial_root_admission_owns_every_reservation(void) {
    fixture f; init(&f);
    assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_OK);
    uint64_t reserved = 0; assert(pwp_reserve(&f.owner, &reserved) == PWP_OK);
    uint64_t ancestor = add(&f, 0);
    assert(pwp_roles_bind_root(&f.roles, &f.owner, reserved) == PWP_POLICY);
    assert(pwp_roles_bind_root(&f.roles, &f.owner, ancestor) == PWP_POLICY);
    assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_BUSY);
    complete(&f);
    assert(f.closes == 1 && f.closed[0] == ancestor && !f.roles.opening);
    assert(root(&f) > ancestor); complete(&f);
}
static void root_quarantine_cannot_be_reset_or_rebound(void) {
    fixture f; init(&f); uint64_t r = root(&f); f.fail_resource = r;
    assert(pwp_roles_retire_all(&f.roles, &f.owner, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
    assert(f.owner.poisoned && f.roles.root == r && pwp_lookup(&f.owner, r)->state == 4);
    assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_CLEANUP_UNKNOWN);
    assert(pwp_roles_bind_root(&f.roles, &f.owner, r) == PWP_CLEANUP_UNKNOWN);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, close_handle, &f) == PWP_CLEANUP_UNKNOWN && f.closes == 1);
    uint64_t next = 0; assert(pwp_reserve(&f.owner, &next) == PWP_CLEANUP_UNKNOWN);
}
static void metadata_identity_can_precede_profile_but_cannot_mutate(void) {
    fixture f; init(&f); uint64_t r = root(&f), id = identity(&f), other = add(&f, 1);
    pwp_role_grant grant = {9, 9, 9, 9};
    assert(pwp_roles_capture(&f.roles, &f.owner, r, &grant) == PWP_POLICY);
    assert(!grant.root && !grant.directory && !grant.profile && !grant.vault);
    assert(pwp_roles_capture(&f.roles, &f.owner, id, &grant) == PWP_POLICY);
    assert(pwp_roles_capture(&f.roles, &f.owner, other, &grant) == PWP_POLICY);
    assert(pwp_roles_lease_admit(&f.roles, &f.owner, id, PWP_LEASE_VAULT) == PWP_POLICY);
    assert(retire(&f, id) == PWP_OK && !f.roles.identity);
    uint64_t replacement = identity(&f); assert(replacement > id);
    assert(pwp_roles_capture(&f.roles, &f.owner, replacement, &grant) == PWP_POLICY); complete(&f);
}
static void arbitrary_public_handles_and_wrong_roles_do_not_grant_mutation(void) {
    fixture f; init(&f); uint64_t r = root(&f), id = identity(&f), other = add(&f, 1);
    pwp_role_grant grant;
    assert(pwp_roles_lease_admit(&f.roles, &f.owner, other, PWP_LEASE_PROFILE) == PWP_POLICY);
    assert(pwp_roles_lease_admit(&f.roles, &f.owner, id, PWP_LEASE_PROFILE) == PWP_POLICY);
    assert(pwp_roles_bind_lease(&f.roles, &f.owner, r, PWP_LEASE_PROFILE, r) == PWP_POLICY);
    assert(pwp_roles_bind_lease(&f.roles, &f.owner, r, PWP_LEASE_PROFILE, id) == PWP_POLICY);
    assert(pwp_roles_capture(&f.roles, &f.owner, r, &grant) == PWP_POLICY);
    uint64_t p = lease(&f, PWP_LEASE_PROFILE);
    assert(pwp_roles_lease_admit(&f.roles, &f.owner, r, PWP_LEASE_PROFILE) == PWP_BUSY);
    assert(pwp_roles_bind_lease(&f.roles, &f.owner, id, PWP_LEASE_VAULT, p) == PWP_POLICY);
    assert(pwp_roles_bind_lease(&f.roles, &f.owner, id, PWP_LEASE_VAULT, id) == PWP_POLICY);
    assert(pwp_roles_capture(&f.roles, &f.owner, other, &grant) == PWP_POLICY); complete(&f);
}
static void vault_pins_canonical_identity_and_profile_generation(void) {
    fixture f; init(&f); uint64_t r = root(&f), p = lease(&f, PWP_LEASE_PROFILE), other = add(&f, 1);
    assert(pwp_roles_lease_admit(&f.roles, &f.owner, other, PWP_LEASE_VAULT) == PWP_POLICY);
    uint64_t id = identity(&f), duplicate = add(&f, 1);
    assert(pwp_roles_bind_identity(&f.roles, &f.owner, r, duplicate) == PWP_BUSY);
    assert(pwp_roles_lease_admit(&f.roles, &f.owner, duplicate, PWP_LEASE_VAULT) == PWP_POLICY);
    uint64_t v = lease(&f, PWP_LEASE_VAULT);
    assert(f.roles.vault == v && f.roles.vault_profile == p && f.roles.vault_directory == id);
    assert(pwp_roles_lease_admit(&f.roles, &f.owner, id, PWP_LEASE_VAULT) == PWP_BUSY);
    assert(retire(&f, p) == PWP_BUSY && retire(&f, id) == PWP_BUSY && f.closes == 0); complete(&f);
}
static void every_role_requires_an_actually_live_published_owner(void) {
    fixture f; init(&f); uint64_t r = root(&f), p = lease(&f, PWP_LEASE_PROFILE);
    uint64_t id = identity(&f), v = lease(&f, PWP_LEASE_VAULT), s = stage(&f, id);
    const uint64_t required[] = {r, p, id, v, s};
    for (size_t i = 0; i < sizeof(required)/sizeof(required[0]); ++i) for (int mode = 0; mode < 5; ++mode) {
        pwp_owned_handle *handle = pwp_lookup(&f.owner, required[i]), original = *handle;
        /* Fault injection only. Production never restores corrupted or quarantined owner state. */
        if (mode == 0) handle->published = 0;
        if (mode == 1) handle->state = 1;
        if (mode == 2) handle->state = 3;
        if (mode == 3) handle->state = 4;
        if (mode == 4) handle->resource = 0;
        assert(pwp_roles_check_stage(&f.roles, &f.owner, s) == PWP_POLICY);
        *handle = original;
    }
    f.owner.poisoned = 1;
    assert(pwp_roles_check_stage(&f.roles, &f.owner, s) == PWP_CLEANUP_UNKNOWN);
    /* No reset: terminal cleanup must retain this injected uncertainty even if all closes succeed. */
    assert(pwp_roles_retire_all(&f.roles, &f.owner, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
    assert(f.closes == 5 && f.roles.vault == v && f.roles.profile == p);
}
static void grants_are_exact_and_scoped(void) {
    fixture f; init(&f); uint64_t r = root(&f), p = lease(&f, PWP_LEASE_PROFILE), id = identity(&f);
    pwp_role_grant root_grant, grant;
    assert(pwp_roles_capture(&f.roles, &f.owner, r, &root_grant) == PWP_OK);
    assert(root_grant.root == r && root_grant.directory == r && root_grant.profile == p && !root_grant.vault);
    assert(pwp_roles_capture(&f.roles, &f.owner, id, &grant) == PWP_POLICY);
    uint64_t v = lease(&f, PWP_LEASE_VAULT), other = add(&f, 1);
    assert(pwp_roles_capture(&f.roles, &f.owner, other, &grant) == PWP_POLICY);
    assert(pwp_roles_capture(&f.roles, &f.owner, id, &grant) == PWP_OK);
    assert(grant.root == r && grant.directory == id && grant.profile == p && grant.vault == v);
    assert(pwp_roles_check_grant(&f.roles, &f.owner, &root_grant) == PWP_OK);
    for (int mode = 0; mode < 5; ++mode) {
        pwp_role_grant changed = grant;
        if (mode == 0) changed.root = other;
        if (mode == 1) changed.directory = r;
        if (mode == 2) changed.profile = other;
        if (mode == 3) changed.vault = 0;
        if (mode == 4) changed.directory = other;
        assert(pwp_roles_check_grant(&f.roles, &f.owner, &changed) == PWP_POLICY);
    }
    complete(&f);
}
static void reacquired_profile_cannot_authorize_an_old_grant(void) {
    fixture f; init(&f); uint64_t r = root(&f), old = lease(&f, PWP_LEASE_PROFILE);
    pwp_role_grant grant;
    assert(pwp_roles_capture(&f.roles, &f.owner, r, &grant) == PWP_OK);
    assert(retire(&f, old) == PWP_OK);
    assert(pwp_roles_check_grant(&f.roles, &f.owner, &grant) == PWP_POLICY);
    assert(pwp_roles_bind_lease(&f.roles, &f.owner, r, PWP_LEASE_PROFILE, old) == PWP_POLICY);
    uint64_t fresh = lease(&f, PWP_LEASE_PROFILE); assert(fresh > old);
    /* The OS may reuse a retired numeric resource; it must not reuse the native authority token. */
    pwp_lookup(&f.owner, fresh)->resource = (uintptr_t)old;
    assert(pwp_roles_check_grant(&f.roles, &f.owner, &grant) == PWP_POLICY);
    uint64_t candidate = add(&f, 1);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, candidate, &grant) == PWP_POLICY);
    assert(retire(&f, candidate) == PWP_OK); complete(&f);
}
static void reacquired_vault_cannot_authorize_an_old_grant(void) {
    fixture f; init(&f); root(&f); lease(&f, PWP_LEASE_PROFILE);
    uint64_t id = identity(&f), old = lease(&f, PWP_LEASE_VAULT); pwp_role_grant grant;
    assert(pwp_roles_capture(&f.roles, &f.owner, id, &grant) == PWP_OK);
    assert(retire(&f, old) == PWP_OK && !f.roles.vault_profile && !f.roles.vault_directory);
    assert(pwp_roles_bind_lease(&f.roles, &f.owner, id, PWP_LEASE_VAULT, old) == PWP_POLICY);
    uint64_t fresh = lease(&f, PWP_LEASE_VAULT); assert(fresh > old);
    assert(pwp_roles_check_grant(&f.roles, &f.owner, &grant) == PWP_POLICY);
    uint64_t candidate = add(&f, 1);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, candidate, &grant) == PWP_POLICY);
    assert(retire(&f, candidate) == PWP_OK); complete(&f);
}
static void root_stage_prevents_profile_close_not_unrelated_directory_close(void) {
    fixture f; init(&f); uint64_t r = root(&f), p = lease(&f, PWP_LEASE_PROFILE);
    uint64_t id = identity(&f), s = stage(&f, r);
    assert(retire(&f, p) == PWP_BUSY && f.closes == 0 && pwp_lookup(&f.owner, p)->state == 2);
    assert(retire(&f, id) == PWP_OK && !f.roles.identity);
    assert(pwp_roles_check_stage(&f.roles, &f.owner, s) == PWP_OK);
    assert(retire(&f, s) == PWP_OK && retire(&f, p) == PWP_OK); complete(&f);
}
static void mixed_stage_dependencies_release_only_in_order(void) {
    fixture f; init(&f); uint64_t r = root(&f), p = lease(&f, PWP_LEASE_PROFILE);
    uint64_t id = identity(&f), v = lease(&f, PWP_LEASE_VAULT);
    uint64_t outer = stage(&f, r), inner = stage(&f, id);
    assert(retire(&f, v) == PWP_BUSY && retire(&f, p) == PWP_BUSY && retire(&f, id) == PWP_BUSY);
    assert(f.closes == 0 && retire(&f, inner) == PWP_OK);
    assert(retire(&f, p) == PWP_BUSY && retire(&f, id) == PWP_BUSY);
    assert(retire(&f, v) == PWP_OK && retire(&f, id) == PWP_OK);
    assert(pwp_roles_check_stage(&f.roles, &f.owner, outer) == PWP_OK);
    assert(retire(&f, p) == PWP_BUSY && retire(&f, outer) == PWP_OK && retire(&f, p) == PWP_OK);
    complete(&f);
}
static void stage_binding_rejects_unpublished_duplicate_and_stale_tokens(void) {
    fixture f; init(&f); uint64_t r = root(&f), p = lease(&f, PWP_LEASE_PROFILE); pwp_role_grant grant;
    assert(pwp_roles_capture(&f.roles, &f.owner, r, &grant) == PWP_OK);
    uint64_t s = add(&f, 0);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, s, &grant) == PWP_POLICY);
    assert(pwp_publish(&f.owner, s) == PWP_OK);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, s, &grant) == PWP_OK);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, s, &grant) == PWP_BUSY);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, p, &grant) == PWP_BUSY);
    assert(retire(&f, s) == PWP_OK && retire(&f, s) == PWP_OK && f.closes == 1);
    assert(pwp_roles_check_stage(&f.roles, &f.owner, s) == PWP_POLICY);
    uint64_t replacement = add(&f, 1); assert(replacement > s);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, s, &grant) == PWP_POLICY);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, replacement, &grant) == PWP_OK); complete(&f);
}
static void failed_stage_retirement_retains_all_dependencies(void) {
    fixture f; init(&f); uint64_t r = root(&f), p = lease(&f, PWP_LEASE_PROFILE);
    uint64_t id = identity(&f), v = lease(&f, PWP_LEASE_VAULT), s = stage(&f, id);
    f.fail_resource = s;
    assert(retire(&f, s) == PWP_CLEANUP_UNKNOWN && f.closes == 1);
    assert(f.roles.stages[0].token == s && f.roles.stages[0].grant.profile == p);
    assert(f.roles.stages[0].grant.vault == v && pwp_lookup(&f.owner, s)->state == 4);
    assert(retire(&f, v) == PWP_CLEANUP_UNKNOWN && retire(&f, p) == PWP_CLEANUP_UNKNOWN);
    assert(retire(&f, id) == PWP_CLEANUP_UNKNOWN && f.closes == 1);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
    assert(f.closes == 5 && f.closed[1] == v && f.closed[2] == id && f.closed[3] == p && f.closed[4] == r);
    assert(f.roles.stages[0].token == s && f.roles.profile == p && f.roles.vault == v);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, close_handle, &f) == PWP_CLEANUP_UNKNOWN && f.closes == 5);
    assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_CLEANUP_UNKNOWN);
}
static void unpublished_failure_still_retains_granting_parents(void) {
    for (int vault_failure = 0; vault_failure < 2; ++vault_failure) {
        fixture f; init(&f); root(&f); uint64_t p = lease(&f, PWP_LEASE_PROFILE), id = identity(&f);
        uint64_t v = vault_failure ? 0 : lease(&f, PWP_LEASE_VAULT), partial = add(&f, 0);
        f.fail_resource = partial;
        if (vault_failure) {
            f.reject_verify = 1;
            assert(pwp_lock_finish(&f.owner, partial, verify, flush, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        } else assert(retire(&f, partial) == PWP_CLEANUP_UNKNOWN);
        assert(!pwp_lookup(&f.owner, partial)->published && !f.roles.stages[0].token);
        assert(retire(&f, p) == PWP_CLEANUP_UNKNOWN && retire(&f, id) == PWP_CLEANUP_UNKNOWN);
        if (v) assert(retire(&f, v) == PWP_CLEANUP_UNKNOWN);
        assert(f.closes == 1 && pwp_lookup(&f.owner, p)->state == 2);
        assert(pwp_roles_retire_all(&f.roles, &f.owner, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(f.closes == (vault_failure ? 4u : 5u));
        assert(pwp_lookup(&f.owner, p)->state == 3 && pwp_lookup(&f.owner, partial)->state == 4);
        assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_CLEANUP_UNKNOWN);
    }
}
static void whole_root_cleanup_ignores_dependency_guards_but_seals_admission(void) {
    for (int failure = 0; failure < 3; ++failure) {
        fixture f; init(&f); uint64_t r = root(&f), p = lease(&f, PWP_LEASE_PROFILE);
        uint64_t id = identity(&f), v = lease(&f, PWP_LEASE_VAULT);
        uint64_t outer = stage(&f, r), inner = stage(&f, id), unpublished = add(&f, 0);
        const uint64_t order[] = {unpublished, inner, outer, v, id, p, r};
        f.probe_terminal = 1; f.fail_resource = failure == 1 ? inner : failure == 2 ? v : 0;
        pwp_result expected = failure ? PWP_CLEANUP_UNKNOWN : PWP_OK;
        assert(pwp_roles_retire_all(&f.roles, &f.owner, close_handle, &f) == expected);
        assert(f.closes == sizeof(order)/sizeof(order[0]));
        for (size_t i = 0; i < f.closes; ++i) assert(f.closed[i] == order[i]);
        assert(pwp_roles_retire_all(&f.roles, &f.owner, close_handle, &f) == expected && f.closes == 7);
        if (failure) {
            assert(f.roles.root == r && f.roles.vault == v && f.roles.profile == p);
            assert(pwp_lookup(&f.owner, p)->state == 3 && pwp_lookup(&f.owner, r)->state == 3);
            assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_CLEANUP_UNKNOWN);
        } else assert(!f.roles.root && !f.roles.stages[0].token);
    }
}
static void stage_capacity_is_bounded_and_retired_slots_do_not_reuse_tokens(void) {
    fixture f; init(&f); uint64_t r = root(&f); lease(&f, PWP_LEASE_PROFILE);
    uint64_t tokens[PWP_PUBLIC_HANDLE_LIMIT-2];
    for (size_t i = 0; i < sizeof(tokens)/sizeof(tokens[0]); ++i) tokens[i] = stage(&f, r);
    assert(pwp_public_count(&f.owner) == PWP_PUBLIC_HANDLE_LIMIT);
    uint64_t excess = add(&f, 0); pwp_role_grant grant;
    assert(pwp_publish(&f.owner, excess) == PWP_LIMIT);
    assert(pwp_roles_capture(&f.roles, &f.owner, r, &grant) == PWP_OK);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, excess, &grant) == PWP_POLICY);
    assert(retire(&f, excess) == PWP_OK && retire(&f, tokens[0]) == PWP_OK);
    uint64_t replacement = stage(&f, r); assert(replacement > excess);
    assert(pwp_roles_check_stage(&f.roles, &f.owner, tokens[0]) == PWP_POLICY); complete(&f);
}
static void invalid_controller_arguments_never_admit_or_retire(void) {
    fixture f; init(&f); uint64_t r = root(&f); pwp_role_grant grant;
    assert(pwp_roles_begin_root(NULL, &f.owner) == PWP_ARGUMENT);
    assert(pwp_roles_begin_root(&f.roles, NULL) == PWP_ARGUMENT);
    assert(pwp_roles_bind_root(&f.roles, &f.owner, 0) == PWP_ARGUMENT);
    assert(pwp_roles_identity_admit(NULL, &f.owner, r) == PWP_ARGUMENT);
    assert(pwp_roles_bind_identity(&f.roles, NULL, r, r+1) == PWP_ARGUMENT);
    assert(pwp_roles_lease_admit(&f.roles, &f.owner, r, PWP_LEASE_NONE) == PWP_ARGUMENT);
    assert(pwp_roles_capture(&f.roles, &f.owner, r, NULL) == PWP_ARGUMENT);
    assert(pwp_roles_capture(NULL, &f.owner, r, &grant) == PWP_ARGUMENT);
    assert(pwp_roles_check_grant(&f.roles, &f.owner, NULL) == PWP_ARGUMENT);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, r, NULL) == PWP_ARGUMENT);
    assert(pwp_roles_check_stage(NULL, &f.owner, r) == PWP_ARGUMENT);
    assert(pwp_roles_retire(NULL, &f.owner, r, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_roles_retire(&f.roles, &f.owner, r, NULL, &f) == PWP_ARGUMENT);
    assert(pwp_roles_retire_all(&f.roles, NULL, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_roles_retire_all(&f.roles, &f.owner, NULL, &f) == PWP_ARGUMENT);
    assert(f.closes == 0 && pwp_lookup(&f.owner, r)->state == 2); complete(&f);
}
static void new_root_session_never_inherits_an_old_grant(void) {
    fixture f; init(&f); uint64_t old = root(&f); lease(&f, PWP_LEASE_PROFILE); pwp_role_grant grant;
    assert(pwp_roles_capture(&f.roles, &f.owner, old, &grant) == PWP_OK);
    complete(&f);
    assert(pwp_roles_begin_root(&f.roles, &f.owner) == PWP_OK);
    assert(pwp_roles_bind_root(&f.roles, &f.owner, old) == PWP_POLICY);
    uint64_t fresh = add(&f, 1); assert(fresh > old);
    pwp_lookup(&f.owner, fresh)->resource = (uintptr_t)old;
    assert(pwp_roles_bind_root(&f.roles, &f.owner, fresh) == PWP_OK);
    lease(&f, PWP_LEASE_PROFILE);
    assert(pwp_roles_check_grant(&f.roles, &f.owner, &grant) == PWP_POLICY);
    uint64_t candidate = add(&f, 1);
    assert(pwp_roles_bind_stage(&f.roles, &f.owner, candidate, &grant) == PWP_POLICY);
    complete(&f);
}
int main(void) {
    fixed_names_are_selectors_not_authority(); root_admission_requires_retired_owners_and_publication();
    partial_root_admission_owns_every_reservation(); root_quarantine_cannot_be_reset_or_rebound();
    metadata_identity_can_precede_profile_but_cannot_mutate();
    arbitrary_public_handles_and_wrong_roles_do_not_grant_mutation();
    vault_pins_canonical_identity_and_profile_generation(); every_role_requires_an_actually_live_published_owner();
    grants_are_exact_and_scoped(); reacquired_profile_cannot_authorize_an_old_grant();
    reacquired_vault_cannot_authorize_an_old_grant();
    root_stage_prevents_profile_close_not_unrelated_directory_close(); mixed_stage_dependencies_release_only_in_order();
    stage_binding_rejects_unpublished_duplicate_and_stale_tokens(); failed_stage_retirement_retains_all_dependencies();
    unpublished_failure_still_retains_granting_parents();
    whole_root_cleanup_ignores_dependency_guards_but_seals_admission();
    stage_capacity_is_bounded_and_retired_slots_do_not_reuse_tokens();
    invalid_controller_arguments_never_admit_or_retire(); new_root_session_never_inherits_an_old_grant();
    puts("20 portable role/ownership groups PASS; NOT Windows SDK/NTFS/ACL/share or installed-runtime qualification");
    return 0;
}
