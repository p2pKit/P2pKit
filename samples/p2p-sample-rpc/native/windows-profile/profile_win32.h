#ifndef P2PKIT_WINDOWS_PROFILE_WIN32_H
#define P2PKIT_WINDOWS_PROFILE_WIN32_H
#include "profile_policy.h"
/* Custody implementation, NOT complete profile persistence: transaction capability remains absent. */
pwp_result pwp_win_open_root(uint64_t *root);
pwp_result pwp_win_child(uint64_t parent, const uint16_t *name, size_t length, uint64_t *child);
/* Explicit collision-refusing FILE_CREATE. No open-existing fallback, rollback or durable namespace claim. */
pwp_result pwp_win_create_child(uint64_t parent, const uint16_t *name, size_t length, uint64_t *child);
pwp_result pwp_win_identity(uint64_t handle, uint64_t words[PWP_IDENTITY_WORDS]);
pwp_result pwp_win_file_identity(uint64_t directory, const uint16_t *name, size_t length,
                                 uint64_t words[PWP_IDENTITY_WORDS]);
pwp_result pwp_win_exists(uint64_t directory, const uint16_t *name, size_t length, int *exists);
/* Bulk callbacks execute synchronously under the native admission owner. Never retain their buffers,
 * re-enter the provider, or unwind across C; report JNI exceptions as errors, not successful callbacks. */
typedef pwp_result (*pwp_names_action)(const pwp_directory_names *names, void *context);
pwp_result pwp_win_names(uint64_t directory, pwp_names_action receive, void *context);
pwp_result pwp_win_read(uint64_t directory, const uint16_t *name, size_t length,
                        size_t maximum, pwp_buffer_action receive, void *context);
pwp_result pwp_win_lock(uint64_t directory, const uint16_t *name, size_t length, uint64_t *lease);
/* Exact root/profile.lock FILE_CREATE only; returned share-none lease is held, not a durable transaction. */
pwp_result pwp_win_create_profile_lock(uint64_t root, uint64_t *lease);
/* Disposable stage only; FILE_CREATE/delete-on-close, bounded file flush, no record publication/durability. */
pwp_result pwp_win_stage(uint64_t directory, const uint16_t *name, size_t length,
                         size_t count, pwp_buffer_action copy, void *context, uint64_t *stage);
pwp_result pwp_win_discard_stage(uint64_t stage);
pwp_result pwp_win_close(uint64_t handle);
pwp_result pwp_win_request_delete(uint64_t directory, const uint16_t *name, size_t length,
                                  const uint64_t *expected, size_t count);
#endif
