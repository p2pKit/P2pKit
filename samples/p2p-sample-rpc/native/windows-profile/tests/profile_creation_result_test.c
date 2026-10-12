/* Actual create-result classifier and ownership/stage/candidate/namespace/write controllers.
 * Syscall observations and resources are inert inputs, not Win32 emulation or NTFS execution evidence. */
#include "../profile_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define COLLISION UINT32_C(0xc0000035)
typedef enum { BOOTSTRAP = 0, STAGE, CANDIDATE } create_kind;
typedef struct {
    pwp_owner owner;
    pwp_roles roles;
    pwp_role_grant grant;
    pwp_stage stage;
    pwp_candidate candidate;
    pwp_namespace_commit bootstrap;
    pwp_record_write record;
    uint64_t root, profile, identity, vault, created;
    unsigned closes[16], physical_closes[16], verifies, writes, flushes, reads, publishes, dispositions;
    unsigned record_seals, forbidden_record_calls;
    unsigned char stored[3];
    size_t size, position;
    create_kind kind;
    uint32_t status, io_status;
    uint64_t information;
    int handle_kind, known_created, namespace_uncertain, fail_close, fail_write, other_custody_failure;
} fixture;
static uintptr_t resource(uint64_t token) { return (uintptr_t)(100u + token); }
static uint64_t own(fixture *f) {
    uint64_t token = 0;
    assert(pwp_reserve(&f->owner, &token) == PWP_OK && token < 16);
    assert(pwp_attach(&f->owner, token, resource(token)) == PWP_OK);
    assert(pwp_publish(&f->owner, token) == PWP_OK);
    return token;
}
static void initialize(fixture *f, create_kind kind) {
    memset(f, 0, sizeof(*f)); pwp_owner_init(&f->owner); pwp_roles_init(&f->roles);
    f->kind = kind; f->information = 2; f->handle_kind = 1;
    assert(pwp_roles_begin_root(&f->roles, &f->owner) == PWP_OK);
    f->root = own(f); assert(pwp_roles_bind_root(&f->roles, &f->owner, f->root) == PWP_OK);
    f->profile = own(f);
    assert(pwp_roles_bind_lease(&f->roles, &f->owner, f->root, PWP_LEASE_PROFILE, f->profile) == PWP_OK);
    f->identity = own(f);
    assert(pwp_roles_bind_identity(&f->roles, &f->owner, f->root, f->identity) == PWP_OK);
    f->vault = own(f);
    assert(pwp_roles_bind_lease(&f->roles, &f->owner, f->identity, PWP_LEASE_VAULT, f->vault) == PWP_OK);
    assert(pwp_roles_capture(&f->roles, &f->owner, f->identity, &f->grant) == PWP_OK);
}
static int original_grants(fixture *f) {
    const uint64_t owners[] = {f->root, f->profile, f->identity, f->vault};
    for (size_t i = 0; i < sizeof(owners)/sizeof(owners[0]); ++i) {
        pwp_owned_handle *held = pwp_lookup(&f->owner, owners[i]);
        if (!held || held->state != 2 || held->resource != resource(owners[i]) || f->closes[owners[i]]) return 0;
    }
    return pwp_roles_check_grant(&f->roles, &f->owner, &f->grant) == PWP_OK;
}
static int stage_disposition(void *opaque) {
    fixture *f = opaque;
    assert(f->kind == STAGE && f->known_created && !f->namespace_uncertain && ++f->dispositions == 1);
    return 1;
}
static int stage_physical_close(void *opaque) {
    fixture *f = opaque; assert(++f->physical_closes[f->created] == 1); return !f->fail_close;
}
static int close_original(uintptr_t value, void *opaque) {
    fixture *f = opaque;
    for (size_t i = 0; i < PWP_HANDLE_LIMIT; ++i) {
        pwp_owned_handle *held = &f->owner.slots[i];
        if (held->state != 4 || held->resource != value) continue;
        assert(held->token < 16 && value == resource(held->token) && ++f->closes[held->token] == 1);
        if (held->token == f->created && f->kind == STAGE && f->stage.phase != PWP_STAGE_EMPTY) {
            return pwp_stage_discard(&f->stage, stage_disposition, stage_physical_close, f) == PWP_OK;
        }
        assert(++f->physical_closes[held->token] == 1);
        if (held->token != f->created) return 1;
        if (f->candidate.phase != PWP_CANDIDATE_EMPTY)
            return pwp_candidate_close_ok(&f->candidate, !f->fail_close);
        /* The actual native close ordering also checks stage/candidate first. Failed creation must keep
         * both EMPTY so neither can discard a presumed stage or mask the namespace-uncertain seal. */
        assert(f->stage.phase == PWP_STAGE_EMPTY && f->candidate.phase == PWP_CANDIDATE_EMPTY);
        return !f->namespace_uncertain && !f->fail_close;
    }
    assert(0); return 0;
}
static int record_verify(size_t count, void *opaque) {
    fixture *f = opaque; ++f->verifies;
    assert(f->known_created && original_grants(f));
    assert((f->kind == STAGE && f->stage.phase == PWP_STAGE_FILLING) ||
           (f->kind == CANDIDATE && f->candidate.phase == PWP_CANDIDATE_FILLING));
    return count == f->size;
}
static int record_write(const unsigned char *bytes, size_t count, size_t *written, void *opaque) {
    fixture *f = opaque; ++f->writes;
    assert(f->known_created && original_grants(f) && f->size == 0 && count == sizeof(f->stored));
    if (f->fail_write) { *written = 0; return 0; }
    memcpy(f->stored, bytes, count); f->size = *written = count; return 1;
}
static int record_flush(void *opaque) {
    fixture *f = opaque; ++f->flushes; assert(f->known_created && original_grants(f)); return 1;
}
static int record_rewind(void *opaque) {
    fixture *f = opaque; assert(f->known_created && original_grants(f)); f->position = 0; return 1;
}
static int record_read(unsigned char *bytes, size_t count, size_t *actual, void *opaque) {
    fixture *f = opaque; ++f->reads;
    assert(f->known_created && original_grants(f) && f->position <= f->size);
    *actual = f->size - f->position;
    if (*actual > count) *actual = count;
    memcpy(bytes, f->stored + f->position, *actual); f->position += *actual; return 1;
}
static pwp_result bootstrap_verify(void *opaque) {
    fixture *f = opaque; ++f->verifies; assert(f->known_created && original_grants(f)); return PWP_OK;
}
static pwp_result bootstrap_sync(size_t index, void *opaque) {
    fixture *f = opaque; assert(index == 0 && ++f->flushes == 1);
    return bootstrap_verify(f);
}
static pwp_result bootstrap_publish(void *opaque) {
    fixture *f = opaque; ++f->publishes; assert(f->known_created && original_grants(f));
    return pwp_publish(&f->owner, f->created);
}
static void namespace_seal(void *opaque) {
    fixture *f = opaque; f->namespace_uncertain = 1; f->owner.poisoned = 1;
}
static pwp_result create_observation(fixture *f) {
    assert(!f->created && original_grants(f));
    assert(pwp_reserve(&f->owner, &f->created) == PWP_OK && f->created < 16);
    /* 0=NULL; 1=valid original; 2=invalid non-NULL sentinel, never attached or closed. */
    if (f->handle_kind == 1)
        assert(pwp_attach(&f->owner, f->created, resource(f->created)) == PWP_OK);
    pwp_result result = pwp_create_observation(f->status, f->io_status, f->information,
        f->handle_kind == 0, f->handle_kind == 1);
    if (f->other_custody_failure) f->owner.poisoned = 1;
    if (result != PWP_OK) {
        if (result == PWP_CLEANUP_UNKNOWN) namespace_seal(f);
        pwp_result cleanup = pwp_roles_retire(&f->roles, &f->owner, f->created, close_original, f);
        return pwp_cleanup_result(cleanup == PWP_OK ? result : PWP_CLEANUP_UNKNOWN,
            f->namespace_uncertain, f->owner.poisoned);
    }
    f->known_created = 1;
    /* These real controllers are entered only after the same shared gate used at all3 native create sites. */
    if (f->kind == BOOTSTRAP) {
        result = pwp_namespace_commit_apply(&f->bootstrap, 1, 1, bootstrap_verify, bootstrap_sync,
            bootstrap_publish, namespace_seal, f);
    } else {
        static const unsigned char bytes[] = {17, 23, 42};
        if (f->kind == STAGE) {
            assert(pwp_stage_init(&f->stage) == PWP_OK);
            result = pwp_stage_fill(&f->stage, bytes, sizeof(bytes), record_write, record_flush, record_verify, f);
        } else {
            assert(pwp_candidate_init(&f->candidate) == PWP_OK);
            result = pwp_candidate_fill(&f->candidate, bytes, sizeof(bytes), record_write, record_flush,
                record_rewind, record_read, record_verify, f);
        }
        if (result == PWP_OK) result = pwp_publish(&f->owner, f->created);
        if (result == PWP_OK) result = pwp_roles_bind_stage(&f->roles, &f->owner, f->created, &f->grant);
    }
    if (result == PWP_OK) return result;
    pwp_result cleanup = pwp_roles_retire(&f->roles, &f->owner, f->created, close_original, f);
    return pwp_cleanup_result(cleanup == PWP_OK ? result : PWP_CLEANUP_UNKNOWN,
        f->namespace_uncertain, f->owner.poisoned);
}
static void drain(fixture *f, int uncertain) {
    assert(pwp_roles_retire_all(&f->roles, &f->owner, close_original, f) ==
        (uncertain ? PWP_CLEANUP_UNKNOWN : PWP_OK));
    for (uint64_t token = f->root; token <= f->vault; ++token)
        assert(f->closes[token] == 1 && f->physical_closes[token] == 1);
    assert(f->closes[f->created] == (unsigned)(f->handle_kind == 1));
    assert(f->physical_closes[f->created] == f->closes[f->created]);
    unsigned saved[16]; memcpy(saved, f->closes, sizeof(saved));
    assert(pwp_roles_retire_all(&f->roles, &f->owner, close_original, f) ==
        (uncertain ? PWP_CLEANUP_UNKNOWN : PWP_OK));
    assert(!memcmp(saved, f->closes, sizeof(saved)));
}
static void classifier_requires_exact_creation_or_exact_collision(void) {
    const uint32_t statuses[] = {0, 0x103, COLLISION, 0xc0000034, 0xc000003a, 0xc0000022, 0xc0000043, 0xffffffff};
    const uint32_t io[] = {0, 0x103, 0xc0000022};
    const uint64_t information[] = {0, 1, 2, 3, UINT64_MAX};
    const int flags[] = {-1, 0, 1, 2};
    for (size_t s = 0; s < sizeof(statuses)/sizeof(statuses[0]); ++s)
        for (size_t i = 0; i < sizeof(io)/sizeof(io[0]); ++i)
            for (size_t k = 0; k < sizeof(information)/sizeof(information[0]); ++k)
                for (size_t n = 0; n < sizeof(flags)/sizeof(flags[0]); ++n)
                    for (size_t v = 0; v < sizeof(flags)/sizeof(flags[0]); ++v) {
                        pwp_result expected = PWP_CLEANUP_UNKNOWN;
                        if (flags[n] == 0 && flags[v] == 1 && !statuses[s] && !io[i] && information[k] == 2)
                            expected = PWP_OK;
                        if (flags[n] == 1 && flags[v] == 0 && statuses[s] == COLLISION) expected = PWP_OS;
                        assert(pwp_create_observation(statuses[s], io[i], information[k], flags[n], flags[v]) == expected);
                    }
}
static void exact_creation_enters_each_existing_controller_with_original_grants(void) {
    for (create_kind kind = BOOTSTRAP; kind <= CANDIDATE; ++kind) {
        fixture f; initialize(&f, kind);
        assert(create_observation(&f) == PWP_OK && f.known_created && original_grants(&f));
        assert(f.flushes == 1 && f.verifies && !f.closes[f.created] && !f.namespace_uncertain);
        assert(kind != STAGE || f.stage.phase == PWP_STAGE_FLUSHED);
        assert(kind != CANDIDATE || f.candidate.phase == PWP_CANDIDATE_VERIFIED);
        assert(kind != BOOTSTRAP || f.bootstrap.phase == PWP_NAMESPACE_COMPLETE);
        drain(&f, 0);
        assert(f.dispositions == (unsigned)(kind == STAGE));
    }
}
static void noncanonical_creation_never_initializes_phases_or_runs_payload_actions(void) {
    const uint32_t statuses[] = {0, 0x103, COLLISION, 0xc0000034, 0xc000003a, 0xc0000022, 0xc0000043};
    const uint32_t io[] = {0, 0x103, 0xc0000022};
    const uint64_t information[] = {0, 1, 2, UINT64_MAX};
    for (create_kind kind = BOOTSTRAP; kind <= CANDIDATE; ++kind)
        for (size_t s = 0; s < sizeof(statuses)/sizeof(statuses[0]); ++s)
            for (size_t i = 0; i < sizeof(io)/sizeof(io[0]); ++i)
                for (size_t k = 0; k < sizeof(information)/sizeof(information[0]); ++k)
                    for (int handle = 0; handle <= 2; ++handle) {
                        if (!statuses[s] && !io[i] && information[k] == 2 && handle == 1) continue;
                        fixture f; initialize(&f, kind);
                        f.status = statuses[s]; f.io_status = io[i]; f.information = information[k]; f.handle_kind = handle;
                        int no_effect = statuses[s] == COLLISION && handle == 0;
                        assert(create_observation(&f) == (no_effect ? PWP_OS : PWP_CLEANUP_UNKNOWN));
                        assert(!f.known_created && !f.writes && !f.flushes && !f.reads && !f.verifies && !f.publishes);
                        assert(f.stage.phase == PWP_STAGE_EMPTY && f.candidate.phase == PWP_CANDIDATE_EMPTY);
                        assert(f.bootstrap.phase == PWP_NAMESPACE_NEW && !f.dispositions);
                        assert(f.namespace_uncertain == !no_effect && f.owner.poisoned == !no_effect);
                        assert(f.closes[f.created] == (unsigned)(handle == 1));
                        if (no_effect) assert(original_grants(&f));
                        else {
                            uint64_t token = 0;
                            assert(pwp_reserve(&f.owner, &token) == PWP_CLEANUP_UNKNOWN && token == 0);
                        }
                        drain(&f, !no_effect);
                    }
}
static void cleanup_failure_never_clears_ambiguous_or_other_custody_failure(void) {
    for (create_kind kind = BOOTSTRAP; kind <= CANDIDATE; ++kind) {
        fixture late; initialize(&late, kind); late.status = COLLISION; late.fail_close = 1;
        assert(create_observation(&late) == PWP_CLEANUP_UNKNOWN && late.namespace_uncertain);
        assert(late.closes[late.created] == 1 && !late.dispositions);
        drain(&late, 1);
        fixture null_collision; initialize(&null_collision, kind);
        null_collision.status = COLLISION; null_collision.handle_kind = 0; null_collision.other_custody_failure = 1;
        assert(create_observation(&null_collision) == PWP_CLEANUP_UNKNOWN);
        assert(!null_collision.known_created && !null_collision.namespace_uncertain && null_collision.owner.poisoned);
        assert(!null_collision.closes[null_collision.created]); drain(&null_collision, 1);
    }
}
static void known_created_payload_failure_keeps_existing_pending_or_stage_cleanup_semantics(void) {
    for (create_kind kind = STAGE; kind <= CANDIDATE; ++kind) {
        fixture f; initialize(&f, kind); f.fail_write = 1;
        assert(create_observation(&f) == PWP_OS && f.known_created && !f.namespace_uncertain && !f.owner.poisoned);
        assert(f.writes == 1 && !f.flushes && !f.reads && !f.publishes && f.closes[f.created] == 1);
        assert(kind != CANDIDATE || f.candidate.phase == PWP_CANDIDATE_FAILED);
        assert(kind != STAGE || f.stage.phase == PWP_STAGE_RETIRED);
        assert(f.dispositions == (unsigned)(kind == STAGE));
        drain(&f, 0); /* Candidate is merely physically closed; this does not promise pending-name cleanup/durability. */
    }
}
static pwp_result prepare_for_record(uint64_t *token, void *opaque) {
    fixture *f = opaque;
    pwp_result result = create_observation(f);
    *token = result == PWP_OK ? f->created : 0;
    return result;
}
static pwp_result forbidden_record_step(uint64_t token, void *opaque) {
    fixture *f = opaque; (void)token; ++f->forbidden_record_calls; assert(0); return PWP_CLEANUP_UNKNOWN;
}
static void record_seal(uint64_t token, void *opaque) {
    fixture *f = opaque; assert(token == 0 && ++f->record_seals == 1); namespace_seal(f);
}
static void composed_record_preserves_unknown_preparation_without_reconstructing_or_reclosing_an_owner(void) {
    const uint32_t statuses[] = {0, 0x103, COLLISION, 0xc0000034, 0xc000003a, 0xc0000022};
    for (size_t i = 0; i < sizeof(statuses)/sizeof(statuses[0]); ++i) {
        fixture f; initialize(&f, CANDIDATE); f.status = statuses[i]; f.handle_kind = 0;
        int no_effect = f.status == COLLISION;
        assert(pwp_record_write_apply(&f.record, prepare_for_record, forbidden_record_step, forbidden_record_step,
            forbidden_record_step, record_seal, &f) == (no_effect ? PWP_OS : PWP_CLEANUP_UNKNOWN));
        assert(f.record.phase == (no_effect ? PWP_WRITE_FAILED : PWP_WRITE_UNCERTAIN));
        assert(!f.record.candidate && !f.forbidden_record_calls && f.record_seals == (unsigned)!no_effect);
        assert(!f.closes[f.created] && !f.writes && !f.dispositions);
        assert(pwp_record_write_apply(&f.record, prepare_for_record, forbidden_record_step, forbidden_record_step,
            forbidden_record_step, record_seal, &f) == PWP_CLOSED);
        drain(&f, !no_effect);
    }
}
int main(void) {
    classifier_requires_exact_creation_or_exact_collision();
    exact_creation_enters_each_existing_controller_with_original_grants();
    noncanonical_creation_never_initializes_phases_or_runs_payload_actions();
    cleanup_failure_never_clears_ambiguous_or_other_custody_failure();
    known_created_payload_failure_keeps_existing_pending_or_stage_cleanup_semantics();
    composed_record_preserves_unknown_preparation_without_reconstructing_or_reclosing_an_owner();
    puts("PASS 6 portable exact-creation-result groups (not Windows runtime)");
    return 0;
}
