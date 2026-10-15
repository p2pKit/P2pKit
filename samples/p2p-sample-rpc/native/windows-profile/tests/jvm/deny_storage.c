/* Test-only deny-all backend. No OS storage implementation is linked to this executable.
 * Every backend entry terminates: even an accidental storage call cannot report success. */
#include "../../profile_win32.h"
#include <stdio.h>
#include <stdlib.h>

static _Noreturn void forbidden_storage(const char *name) {
    fprintf(stderr, "FORBIDDEN_STORAGE_ENTRY: %s\n", name);
    abort();
}

pwp_result pwp_win_open_root(uint64_t *root) {
    (void)root;
    forbidden_storage("pwp_win_open_root");
}

pwp_result pwp_win_child(uint64_t parent, const uint16_t *name, size_t length, uint64_t *child) {
    (void)parent; (void)name; (void)length; (void)child;
    forbidden_storage("pwp_win_child");
}

pwp_result pwp_win_create_child(uint64_t parent, const uint16_t *name, size_t length, uint64_t *child) {
    (void)parent; (void)name; (void)length; (void)child;
    forbidden_storage("pwp_win_create_child");
}

pwp_result pwp_win_identity(uint64_t handle, uint64_t words[PWP_IDENTITY_WORDS]) {
    (void)handle; (void)words;
    forbidden_storage("pwp_win_identity");
}

pwp_result pwp_win_file_identity(uint64_t directory, const uint16_t *name, size_t length,
                                 uint64_t words[PWP_IDENTITY_WORDS]) {
    (void)directory; (void)name; (void)length; (void)words;
    forbidden_storage("pwp_win_file_identity");
}

pwp_result pwp_win_exists(uint64_t directory, const uint16_t *name, size_t length, int *exists) {
    (void)directory; (void)name; (void)length; (void)exists;
    forbidden_storage("pwp_win_exists");
}

pwp_result pwp_win_names(uint64_t directory, pwp_names_action receive, void *context) {
    (void)directory; (void)receive; (void)context;
    forbidden_storage("pwp_win_names");
}

pwp_result pwp_win_read(uint64_t directory, const uint16_t *name, size_t length,
                        size_t maximum, pwp_buffer_action receive, void *context) {
    (void)directory; (void)name; (void)length; (void)maximum; (void)receive; (void)context;
    forbidden_storage("pwp_win_read");
}

pwp_result pwp_win_lock(uint64_t directory, const uint16_t *name, size_t length, uint64_t *lease) {
    (void)directory; (void)name; (void)length; (void)lease;
    forbidden_storage("pwp_win_lock");
}

pwp_result pwp_win_create_profile_lock(uint64_t root, uint64_t *lease) {
    (void)root; (void)lease;
    forbidden_storage("pwp_win_create_profile_lock");
}

pwp_result pwp_win_create_vault_lock(uint64_t identity_directory, uint64_t *lease) {
    (void)identity_directory; (void)lease;
    forbidden_storage("pwp_win_create_vault_lock");
}

pwp_result pwp_win_stage(uint64_t directory, const uint16_t *name, size_t length,
                         size_t count, pwp_buffer_action copy, void *context, uint64_t *stage) {
    (void)directory; (void)name; (void)length; (void)count; (void)copy; (void)context; (void)stage;
    forbidden_storage("pwp_win_stage");
}

pwp_result pwp_win_prepare_record(uint64_t directory, const uint16_t *name, size_t length,
                                  size_t count, pwp_buffer_action copy, void *context, uint64_t *candidate) {
    (void)directory; (void)name; (void)length; (void)count; (void)copy; (void)context; (void)candidate;
    forbidden_storage("pwp_win_prepare_record");
}

pwp_result pwp_win_rename_candidate(uint64_t candidate, const uint16_t *name, size_t length) {
    (void)candidate; (void)name; (void)length;
    forbidden_storage("pwp_win_rename_candidate");
}

pwp_result pwp_win_replace_candidate(uint64_t candidate, const uint16_t *name, size_t length) {
    (void)candidate; (void)name; (void)length;
    forbidden_storage("pwp_win_replace_candidate");
}

pwp_result pwp_win_sync_directory(uint64_t directory) {
    (void)directory;
    forbidden_storage("pwp_win_sync_directory");
}

pwp_result pwp_win_write_record(uint64_t directory, const uint16_t *pending, size_t pending_length,
                                const uint16_t *target, size_t target_length, size_t count,
                                pwp_buffer_action copy, void *context, int replace) {
    (void)directory; (void)pending; (void)pending_length; (void)target; (void)target_length; (void)count; (void)copy; (void)context; (void)replace;
    forbidden_storage("pwp_win_write_record");
}

pwp_result pwp_win_discard_stage(uint64_t stage) {
    (void)stage;
    forbidden_storage("pwp_win_discard_stage");
}

pwp_result pwp_win_close(uint64_t handle) {
    (void)handle;
    forbidden_storage("pwp_win_close");
}

pwp_result pwp_win_request_delete(uint64_t directory, const uint16_t *name, size_t length,
                                  const uint64_t *expected, size_t count) {
    (void)directory; (void)name; (void)length; (void)expected; (void)count;
    forbidden_storage("pwp_win_request_delete");
}

pwp_result pwp_win_delete_record(uint64_t directory, const uint16_t *name, size_t length,
                                 const uint64_t *expected, size_t count) {
    (void)directory; (void)name; (void)length; (void)expected; (void)count;
    forbidden_storage("pwp_win_delete_record");
}

