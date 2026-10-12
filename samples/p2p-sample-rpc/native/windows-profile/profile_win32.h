#ifndef P2PKIT_WINDOWS_PROFILE_WIN32_H
#define P2PKIT_WINDOWS_PROFILE_WIN32_H
#include "profile_policy.h"
/* Custody implementation, NOT complete profile persistence: transaction capability remains absent. */
pwp_result pwp_win_open_root(uint64_t *root);
pwp_result pwp_win_child(uint64_t parent, const uint16_t *name, size_t length, uint64_t *child);
/* Fixed root/identity FILE_CREATE under a live native profile lease. No fallback or durable namespace claim. */
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
/* Only empty root/profile.lock or canonical root/identity/vault.lock; vault needs a live verified profile
 * lease. Exact fixed component spelling; existing-file admission never falls back to creation. */
pwp_result pwp_win_lock(uint64_t directory, const uint16_t *name, size_t length, uint64_t *lease);
/* Exact root/profile.lock FILE_CREATE only; returned share-none lease is held, not a durable transaction. */
pwp_result pwp_win_create_profile_lock(uint64_t root, uint64_t *lease);
/* Exact pinned root/identity/vault.lock FILE_CREATE under a native profile lease; no alternate directory. */
pwp_result pwp_win_create_vault_lock(uint64_t identity_directory, uint64_t *lease);
/* Disposable stage only; root requires profile, identity requires profile+vault, before payload copying.
 * FILE_CREATE/delete-on-close, bounded file flush, no record publication/durability. */
pwp_result pwp_win_stage(uint64_t directory, const uint16_t *name, size_t length,
                         size_t count, pwp_buffer_action copy, void *context, uint64_t *stage);
/* Persistent UNCOMMITTED candidate: role-bound FILE_CREATE, no DELETE_ON_CLOSE, bounded write,
 * file flush and exact original-handle byte/EOF readback. Names are pwp-pending- plus 32 lowercase hex.
 * Success retains an opaque candidate owner; close only closes, never deletes. On failure partial/new
 * files can remain. No rename, durable namespace, recovery, complete-adapter wiring or record-write success. */
pwp_result pwp_win_prepare_record(uint64_t directory, const uint16_t *name, size_t length,
                                  size_t count, pwp_buffer_action copy, void *context, uint64_t *candidate);
/* Same-directory CREATE-ONLY name publication, not a durable transaction. Only root/profile.header
 * or identity/<64-lowercase-hex>.aesgcm. Same original handle/grant retained; no stage promotion or replace.
 * Read-only early collision rejection leaves the prepared candidate unchanged. Any uncertainty after the
 * rename attempt seals the session; close still attempts that original handle once and retains quarantine.
 * Success means same-handle rename/file-flush readback ONLY; no namespace durability or complete-adapter wiring. */
pwp_result pwp_win_rename_candidate(uint64_t candidate, const uint16_t *name, size_t length);
/* Same-directory cooperative replacement of canonical identity/<64-lowercase-hex>.aesgcm only.
 * Keep the exact candidate/profile/vault originals live; validate a fresh exclusive read-only target,
 * then retire ONLY that unpublished probe before classic rename. An absent target selects create-only;
 * unsafe/owned targets and uncertain close never reach rename. No hostile same-user namespace CAS,
 * atomic expected-ID replacement, directory durability, complete write, or recovery is claimed. */
pwp_result pwp_win_replace_candidate(uint64_t candidate, const uint16_t *name, size_t length);
/* Original-handle NTFS directory-metadata flush, not a full durable record transaction. Only the exact
 * private root (profile lease) or canonical identity (profile+vault leases); no alternate directory or
 * pre-lease bootstrap claim. Query and verify actual granted write-capable directory access before use.
 * Failed flush/postverification seals admission, retains the original handle until actual retirement,
 * and preserves uncertainty even if physical close succeeds. No retry, reopening, or volume flush. */
pwp_result pwp_win_sync_directory(uint64_t directory);
/* One admitted record operation: create persistent pending, publish create-only/cooperative replacement,
 * sync the original NTFS parent, then retire the original candidate exactly once before success. Root
 * accepts profile.header/create-only; identity accepts canonical AES records. Pending names are supplied
 * by the caller, never derived from payloads. Exact profile/vault grants remain live throughout. Any
 * failure after publication seals admission and retains uncertainty despite actual close. No bootstrap,
 * recovery, durable deletion, full-provider capability or complete managed adapter is implied. */
pwp_result pwp_win_write_record(uint64_t directory, const uint16_t *pending, size_t pending_length,
                                const uint16_t *target, size_t target_length, size_t count,
                                pwp_buffer_action copy, void *context, int replace);
pwp_result pwp_win_discard_stage(uint64_t stage);
/* Independent lease close refuses dependent stages/vault; root close attempts all exact original owners. */
pwp_result pwp_win_close(uint64_t handle);
/* Same role scopes as staging, including revalidation around deletion intent/readback. */
pwp_result pwp_win_request_delete(uint64_t directory, const uint16_t *name, size_t length,
                                  const uint64_t *expected, size_t count);
#endif
