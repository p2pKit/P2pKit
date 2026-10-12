#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Shared orchestration contracts, not Windows open/share/ACL/durability emulation. */
typedef struct {
    unsigned verifies, flushes, closes;
    unsigned reject_verify, exhaust_on_verify;
    int fail_flush, fail_close, poison_on_verify;
    char order[8]; size_t ordered;
    pwp_owner *owner;
} fake;
static void record(fake *f, char action) { assert(f->ordered < sizeof(f->order)); f->order[f->ordered++] = action; }
static int verify(void *context) {
    fake *f = context; ++f->verifies; record(f, 'V');
    if (f->poison_on_verify) f->owner->poisoned = 1;
    if (f->exhaust_on_verify == f->verifies) for (unsigned i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i) {
        uint64_t token = 0;
        assert(pwp_reserve(f->owner, &token) == PWP_OK && pwp_attach(f->owner, token, 7) == PWP_OK);
        assert(pwp_publish(f->owner, token) == PWP_OK);
    }
    return f->verifies != f->reject_verify;
}
static int flush(void *context) { fake *f = context; ++f->flushes; record(f, 'F'); return !f->fail_flush; }
static int close_handle(uintptr_t resource, void *context) {
    fake *f = context; assert(resource == 7); ++f->closes; record(f, 'C'); return !f->fail_close;
}
static uint64_t allocated(pwp_owner *owner) {
    uint64_t token = 0; pwp_owner_init(owner);
    assert(pwp_reserve(owner, &token) == PWP_OK && pwp_attach(owner, token, 7) == PWP_OK); return token;
}
static void exact_order_and_owned_lease(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_OK);
    assert(f.ordered == 3 && memcmp(f.order, "VFV", 3) == 0 && f.closes == 0);
    assert(pwp_public_count(&owner) == 1 && pwp_lookup(&owner, token)->state == 2);
    assert(pwp_lookup(&owner, token)->resource == 7 && pwp_lookup(&owner, token)->published);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK && f.closes == 1);
}
static void bad_arguments_do_not_assume_ownership(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    assert(pwp_lock_finish(NULL, token, verify, flush, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_lock_finish(&owner, 0, verify, flush, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_lock_finish(&owner, token+1, verify, flush, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_lock_finish(&owner, token, NULL, flush, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_lock_finish(&owner, token, verify, NULL, close_handle, &f) == PWP_ARGUMENT);
    assert(pwp_lock_finish(&owner, token, verify, flush, NULL, &f) == PWP_ARGUMENT);
    assert(f.ordered == 0 && pwp_lookup(&owner, token)->state == 2);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK && f.closes == 1);
}
static void verification_failure_never_publishes(void) {
    for (unsigned fail = 1; fail <= 2; ++fail) {
        pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner; f.reject_verify = fail;
        assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_POLICY);
        assert(f.verifies == fail && f.flushes == fail-1 && f.closes == 1 && pwp_public_count(&owner) == 0);
        assert(pwp_lookup(&owner, token)->state == 3 && !pwp_lookup(&owner, token)->published);
        assert(pwp_retire_all(&owner, close_handle, &f) == PWP_OK && f.closes == 1);
    }
}
static void flush_failure_closes_without_retry(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner; f.fail_flush = 1;
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_OS);
    assert(f.ordered == 3 && memcmp(f.order, "VFC", 3) == 0 && pwp_public_count(&owner) == 0);
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_ARGUMENT && f.ordered == 3);
}
static void uncertain_close_is_quarantined(void) {
    for (int mode = 0; mode < 3; ++mode) {
        pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
        f.fail_close = 1; f.reject_verify = mode == 0 ? 1u : mode == 2 ? 2u : 0u; f.fail_flush = mode == 1;
        assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(f.closes == 1 && owner.poisoned && pwp_lookup(&owner, token)->state == 4);
        assert(pwp_lookup(&owner, token)->resource == 7 && !pwp_lookup(&owner, token)->published);
        assert(pwp_retire_all(&owner, close_handle, &f) == PWP_CLEANUP_UNKNOWN && f.closes == 1);
        uint64_t another = 0; assert(pwp_reserve(&owner, &another) == PWP_CLEANUP_UNKNOWN);
    }
}
static void no_republication_or_stale_token(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_OK);
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_ARGUMENT && f.ordered == 3);
    assert(pwp_retire(&owner, token, close_handle, &f) == PWP_OK); uint64_t next = 0;
    assert(pwp_reserve(&owner, &next) == PWP_OK && next != token && pwp_attach(&owner, next, 7) == PWP_OK);
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_ARGUMENT && f.ordered == 4);
    assert(pwp_retire(&owner, next, close_handle, &f) == PWP_OK);
}
static void capacity_preflight_prevents_observation(void) {
    pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
    for (unsigned i = 0; i < PWP_PUBLIC_HANDLE_LIMIT; ++i) {
        uint64_t other = 0; assert(pwp_reserve(&owner, &other) == PWP_OK && pwp_attach(&owner, other, 7) == PWP_OK);
        assert(pwp_publish(&owner, other) == PWP_OK);
    }
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_LIMIT);
    assert(f.verifies == 0 && f.flushes == 0 && f.closes == 1 && pwp_public_count(&owner) == PWP_PUBLIC_HANDLE_LIMIT);
}
static void poisoned_owner_never_publishes(void) {
    for (int mode = 0; mode < 2; ++mode) {
        pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
        owner.poisoned = mode == 0; f.poison_on_verify = mode == 1;
        assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_CLEANUP_UNKNOWN);
        assert(f.closes == 1 && !pwp_lookup(&owner, token)->published && pwp_lookup(&owner, token)->state == 3);
        assert(f.flushes == 0 && f.verifies == (mode == 1 ? 1u : 0u));
    }
}
typedef struct {
    uint64_t root[6], directory[6], file[6];
    uint16_t root_path[96], directory_path[96];
    size_t root_length, directory_length;
} scope_fixture;
static size_t wide(uint16_t output[96], const char *value) {
    size_t length = strlen(value); assert(length < 96);
    for (size_t i = 0; i <= length; ++i) output[i] = (uint16_t)(unsigned char)value[i];
    return length;
}
static scope_fixture vault_fixture(void) {
    scope_fixture fixture = {
        {1, UINT64_MAX, UINT64_C(0x8000000000000000), 0, 0x1ff, 1},
        {1, UINT64_MAX, 0, UINT64_MAX, 0x1ff, 1},
        {1, UINT64_MAX, 9, 3, 0x2ff, 1},
        {0}, {0}, 0, 0
    };
    fixture.root_length = wide(fixture.root_path, "C:\\LocalProfile\\RpcProfile");
    fixture.directory_length = wide(fixture.directory_path, "C:\\LocalProfile\\RpcProfile\\identity");
    return fixture;
}
static int vault_scope(const scope_fixture *f) {
    return pwp_vault_directory_scope(f->root, f->directory, 6,
        f->root_path, f->root_length, f->directory_path, f->directory_length);
}
static void vault_scope_is_the_exact_fixed_identity_child(void) {
    scope_fixture f = vault_fixture(); assert(vault_scope(&f));
    f.directory_length = wide(f.directory_path, "c:\\localprofile\\rpcprofile\\IDENTITY");
    assert(vault_scope(&f)); /* Only the existing admitted insensitive namespace policy is used. */
    const char *rejected[] = {
        "C:\\LocalProfile\\RpcProfile", "C:\\LocalProfile\\RpcProfile\\trusted",
        "C:\\LocalProfile\\RpcProfile\\identity\\identity", "C:\\LocalProfile\\RpcProfile\\identity2",
        "C:\\LocalProfile\\RpcProfile\\identity.", "C:\\LocalProfile\\RpcProfile\\identity ",
        "C:\\LocalProfile\\RpcProfile\\identity:ads", "C:\\LocalProfile\\RpcProfile/identity",
        "D:\\LocalProfile\\RpcProfile\\identity", "C:\\OtherProfile\\RpcProfile\\identity",
        "C:\\LocalProfile\\RpcProfile\\..\\identity"
    };
    for (size_t i = 0; i < sizeof(rejected)/sizeof(rejected[0]); ++i) {
        f.directory_length = wide(f.directory_path, rejected[i]);
        assert(!vault_scope(&f));
    }
}
static void vault_scope_bounds_fail_before_path_access(void) {
    scope_fixture f = vault_fixture();
    assert(!pwp_vault_directory_scope(f.root, f.directory, 6, NULL, f.root_length,
        f.directory_path, f.directory_length));
    assert(!pwp_vault_directory_scope(f.root, f.directory, 6, f.root_path, f.root_length,
        NULL, f.directory_length));
    const size_t bad_root[] = {0, PWP_PATH_LIMIT, SIZE_MAX};
    for (size_t i = 0; i < sizeof(bad_root)/sizeof(bad_root[0]); ++i)
        assert(!pwp_vault_directory_scope(f.root, f.directory, 6, f.root_path, bad_root[i],
            f.directory_path, f.directory_length));
    const size_t bad_child[] = {0, f.root_length-1, f.directory_length-1, PWP_PATH_LIMIT, SIZE_MAX};
    for (size_t i = 0; i < sizeof(bad_child)/sizeof(bad_child[0]); ++i)
        assert(!pwp_vault_directory_scope(f.root, f.directory, 6, f.root_path, f.root_length,
            f.directory_path, bad_child[i]));
    assert(!pwp_vault_directory_scope(f.root, f.directory, 6, f.root_path, SIZE_MAX-9,
        f.directory_path, SIZE_MAX));
    assert(vault_scope(&f)); /* Failure never repairs or mutates an input path. */
}
static void vault_scope_requires_fresh_normal_directory_tuples(void) {
    scope_fixture f = vault_fixture();
    assert(!pwp_vault_directory_scope(NULL, f.directory, 6,
        f.root_path, f.root_length, f.directory_path, f.directory_length));
    assert(!pwp_vault_directory_scope(f.root, NULL, 6,
        f.root_path, f.root_length, f.directory_path, f.directory_length));
    const size_t counts[] = {0, 5, 7, SIZE_MAX};
    for (size_t i = 0; i < sizeof(counts)/sizeof(counts[0]); ++i)
        assert(!pwp_vault_directory_scope(f.root, f.directory, counts[i],
            f.root_path, f.root_length, f.directory_path, f.directory_length));
    for (int side = 0; side < 2; ++side) for (unsigned change = 0; change < 8; ++change) {
        f = vault_fixture(); uint64_t *tuple = side ? f.directory : f.root;
        if (change == 0) tuple[0] = 2;
        if (change == 1) tuple[1] = 0;
        if (change == 2) tuple[1] = 3;
        if (change == 3) tuple[2] = tuple[3] = 0;
        if (change == 4) tuple[4] = 0x2ff;
        if (change == 5) tuple[4] = 0;
        if (change == 6) tuple[5] = 0;
        if (change == 7) tuple[5] = 2;
        assert(!vault_scope(&f));
    }
    f = vault_fixture(); memcpy(f.directory, f.root, sizeof(f.root));
    assert(!vault_scope(&f)); /* A different path cannot make the root its own identity child. */
}
static void new_lock_file_tuples_require_exact_type_volume_and_distinct_ids(void) {
    scope_fixture f = vault_fixture();
    assert(pwp_expected_lock_file(f.directory, f.file, 6));
    assert(pwp_expected_lock_file(f.root, f.file, 6));
    assert(!pwp_expected_lock_file(NULL, f.file, 6) && !pwp_expected_lock_file(f.directory, NULL, 6));
    const size_t counts[] = {0, 5, 7, SIZE_MAX};
    for (size_t i = 0; i < sizeof(counts)/sizeof(counts[0]); ++i)
        assert(!pwp_expected_lock_file(f.directory, f.file, counts[i]));
    for (int side = 0; side < 2; ++side) for (unsigned change = 0; change < 8; ++change) {
        f = vault_fixture(); uint64_t *tuple = side ? f.file : f.directory;
        if (change == 0) tuple[0] = 2;
        if (change == 1) tuple[1] = 0;
        if (change == 2) tuple[1] = 3;
        if (change == 3) tuple[2] = tuple[3] = 0;
        if (change == 4) tuple[4] = side ? 0x1ff : 0x2ff;
        if (change == 5) tuple[4] = 0;
        if (change == 6) tuple[5] = 0;
        if (change == 7) tuple[5] = 2;
        assert(!pwp_expected_lock_file(f.directory, f.file, 6));
    }
    f = vault_fixture(); f.file[2] = f.directory[2]; f.file[3] = f.directory[3];
    assert(!pwp_expected_lock_file(f.directory, f.file, 6));
    f = vault_fixture(); f.file[2] = UINT64_MAX; f.file[3] = UINT64_C(0x8000000000000000);
    assert(pwp_expected_lock_file(f.directory, f.file, 6)); /* Preserve unsigned raw IDs. */
}
typedef struct { fake owner; scope_fixture scope; unsigned change_on_flush; } scoped_lock;
static int scoped_verify(void *context) {
    scoped_lock *c = context;
    return verify(&c->owner) && vault_scope(&c->scope) &&
        pwp_expected_lock_file(c->scope.directory, c->scope.file, 6);
}
static int scoped_flush(void *context) {
    scoped_lock *c = context;
    if (c->change_on_flush == 1) c->scope.directory_path[c->scope.directory_length-1] = 'x';
    if (c->change_on_flush == 2) c->scope.directory[1] = 3;
    if (c->change_on_flush == 3) c->scope.file[4] = 0;
    if (c->change_on_flush == 4) {
        c->scope.file[2] = c->scope.directory[2]; c->scope.file[3] = c->scope.directory[3];
    }
    return flush(&c->owner);
}
static int scoped_close(uintptr_t resource, void *context) {
    return close_handle(resource, &((scoped_lock *)context)->owner);
}
static void shared_lock_controller_rechecks_scope_and_file_after_flush(void) {
    for (unsigned change = 0; change <= 4; ++change) for (int close_fails = 0; close_fails <= 1; ++close_fails) {
        pwp_owner owner; uint64_t token = allocated(&owner);
        scoped_lock c = {0}; c.owner.owner = &owner; c.scope = vault_fixture();
        c.change_on_flush = change; c.owner.fail_close = close_fails;
        pwp_result expected = !change ? PWP_OK : close_fails ? PWP_CLEANUP_UNKNOWN : PWP_POLICY;
        assert(pwp_lock_finish(&owner, token, scoped_verify, scoped_flush, scoped_close, &c) == expected);
        assert(c.owner.verifies == 2 && c.owner.flushes == 1 && c.owner.closes == (change ? 1u : 0u));
        assert(pwp_public_count(&owner) == (change ? 0u : 1u));
        if (change) {
            assert(c.owner.ordered == 4 && memcmp(c.owner.order, "VFVC", 4) == 0);
            assert(pwp_lookup(&owner, token)->state == (close_fails ? 4u : 3u));
            assert(!pwp_lookup(&owner, token)->published);
        } else {
            assert(c.owner.ordered == 3 && memcmp(c.owner.order, "VFV", 3) == 0);
            assert(pwp_retire(&owner, token, scoped_close, &c) == (close_fails ? PWP_CLEANUP_UNKNOWN : PWP_OK));
        }
        assert(pwp_retire_all(&owner, scoped_close, &c) == (close_fails ? PWP_CLEANUP_UNKNOWN : PWP_OK));
        assert(c.owner.closes == 1);
    }
}
static void failed_publication_retires_the_unpublished_lock_once(void) {
    for (int close_fails = 0; close_fails <= 1; ++close_fails) {
        pwp_owner owner; uint64_t token = allocated(&owner); fake f = {0}; f.owner = &owner;
        f.exhaust_on_verify = 2; f.fail_close = close_fails;
        assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) ==
            (close_fails ? PWP_CLEANUP_UNKNOWN : PWP_LIMIT));
        assert(f.ordered == 4 && memcmp(f.order, "VFVC", 4) == 0 && f.closes == 1);
        assert(!pwp_lookup(&owner, token)->published && pwp_lookup(&owner, token)->state == (close_fails ? 4u : 3u));
        assert(pwp_retire(&owner, token, close_handle, &f) == (close_fails ? PWP_CLEANUP_UNKNOWN : PWP_OK));
        assert(f.closes == 1);
    }
}
typedef struct { uintptr_t resources[4]; size_t count; } retired_profile;
static int ordered_close(uintptr_t resource, void *context) {
    retired_profile *profile = context; assert(profile->count < 4);
    profile->resources[profile->count++] = resource; return 1;
}
static void session_retires_vault_lease_before_identity_and_profile(void) {
    pwp_owner owner; pwp_owner_init(&owner); uint64_t token = 0;
    for (uintptr_t resource = 9; resource <= 11; ++resource) {
        assert(pwp_reserve(&owner, &token) == PWP_OK && pwp_attach(&owner, token, resource) == PWP_OK);
        assert(pwp_publish(&owner, token) == PWP_OK);
    }
    assert(pwp_reserve(&owner, &token) == PWP_OK && pwp_attach(&owner, token, 7) == PWP_OK);
    fake f = {0}; f.owner = &owner;
    assert(pwp_lock_finish(&owner, token, verify, flush, close_handle, &f) == PWP_OK);
    retired_profile profile = {{0}, 0};
    assert(pwp_retire_all(&owner, ordered_close, &profile) == PWP_OK);
    assert(profile.count == 4 && profile.resources[0] == 7 && profile.resources[1] == 11 &&
        profile.resources[2] == 10 && profile.resources[3] == 9);
    assert(pwp_retire_all(&owner, ordered_close, &profile) == PWP_OK && profile.count == 4);
}
int main(void) {
    exact_order_and_owned_lease(); bad_arguments_do_not_assume_ownership(); verification_failure_never_publishes();
    flush_failure_closes_without_retry(); uncertain_close_is_quarantined(); no_republication_or_stale_token();
    capacity_preflight_prevents_observation(); poisoned_owner_never_publishes();
    vault_scope_is_the_exact_fixed_identity_child(); vault_scope_bounds_fail_before_path_access();
    vault_scope_requires_fresh_normal_directory_tuples();
    new_lock_file_tuples_require_exact_type_volume_and_distinct_ids();
    shared_lock_controller_rechecks_scope_and_file_after_flush();
    failed_publication_retires_the_unpublished_lock_once(); session_retires_vault_lease_before_identity_and_profile();
    puts("15 portable new-lock custody groups PASS; NOT Windows sharing/ACL/namespace durability qualification"); return 0;
}
