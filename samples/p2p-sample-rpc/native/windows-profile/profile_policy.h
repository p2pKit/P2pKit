#ifndef P2PKIT_WINDOWS_PROFILE_POLICY_H
#define P2PKIT_WINDOWS_PROFILE_POLICY_H
#include <stddef.h>
#include <stdint.h>

#define PWP_COMPONENT_LIMIT 96u
#define PWP_RECORD_LIMIT 262144u
#define PWP_HANDLE_LIMIT 128u
#define PWP_PUBLIC_HANDLE_LIMIT 32u
#define PWP_PATH_LIMIT 32768u
#define PWP_IDENTITY_WORDS 6u
#define PWP_DIRECTORY_LIMIT 1024u
#define PWP_DIRECTORY_BUFFER_LIMIT 65536u
#define PWP_CUSTODY_ABI 7

typedef enum {
    PWP_OK = 0, PWP_ARGUMENT = 1, PWP_POLICY = 2, PWP_OS = 3,
    PWP_BUSY = 4, PWP_CLOSED = 5, PWP_LIMIT = 6, PWP_NOT_FOUND = 7,
    PWP_CLEANUP_UNKNOWN = 8, PWP_UNIMPLEMENTED = 9
} pwp_result;

/* Byte-oriented decoding: never cast untrusted OS buffers to potentially unaligned structs. */
int pwp_token_valid(uint64_t token);
int pwp_append_path(uint16_t *path, size_t capacity, const uint16_t *name, size_t length);
int pwp_component(const uint16_t *name, size_t length);
int pwp_absolute_path(const uint16_t *path, size_t length);
int pwp_final_path(const uint16_t *expected, size_t expected_length,
                   const uint16_t *actual, size_t actual_length);
/* Exact successful FileCaseSensitiveInfo query, Flags == 0; unknown/unsupported is not insensitive. */
int pwp_directory_case_policy(int query_succeeded, uint32_t flags);
typedef struct {
    uint32_t count;
    uint16_t lengths[PWP_DIRECTORY_LIMIT];
    uint16_t names[PWP_DIRECTORY_LIMIT][PWP_COMPONENT_LIMIT + 1];
} pwp_directory_names;
/* FILE_ID_BOTH_DIR_INFO byte records. Failure invalidates the whole aggregate, never exposes a partial list. */
pwp_result pwp_directory_decode(const unsigned char *bytes, size_t length, pwp_directory_names *names);
int pwp_stream_record(const unsigned char *bytes, size_t length, uint64_t file_size, int directory);
int pwp_acl_shape(uint16_t control, uint32_t revision, uint32_t ace_count,
                  const uint8_t types[2], const uint8_t flags[2], const uint32_t masks[2],
                  int owner_is_user, const int sid_kind[2], int directory);
void pwp_clear(void *bytes, size_t length);
/* Caller already owns admission. The bounded zero-initialized buffer cannot escape the synchronous action;
 * every action outcome clears/frees it before returning. No callback may throw/longjmp across this boundary. */
typedef pwp_result (*pwp_buffer_action)(unsigned char *bytes, size_t count, void *context);
pwp_result pwp_buffer_apply(size_t count, pwp_buffer_action action, void *context);

/* Disposable, uncommitted staging only. This state machine never publishes or replaces a record.
 * Caller serializes access and owns the exact original delete-on-close handle for the entire lifetime. */
typedef enum {
    PWP_STAGE_EMPTY = 0, PWP_STAGE_OWNED, PWP_STAGE_FILLING, PWP_STAGE_FLUSHED,
    PWP_STAGE_FAILED, PWP_STAGE_RETIRING, PWP_STAGE_RETIRED, PWP_STAGE_QUARANTINED
} pwp_stage_phase;
typedef struct { pwp_stage_phase phase; } pwp_stage;
typedef int (*pwp_stage_write)(const unsigned char *bytes, size_t count, size_t *written, void *context);
typedef int (*pwp_stage_action)(void *context);
typedef int (*pwp_stage_verify)(size_t expected_size, void *context);
int pwp_stage_name(const uint16_t *name, size_t length);
int pwp_regular_metadata(pwp_stage_phase phase);
pwp_result pwp_stage_init(pwp_stage *stage);
pwp_result pwp_stage_fill(pwp_stage *stage, const unsigned char *bytes, size_t length,
                         pwp_stage_write write, pwp_stage_action flush, pwp_stage_verify verify, void *context);
pwp_result pwp_stage_discard(pwp_stage *stage, pwp_stage_action mark_delete,
                            pwp_stage_action close, void *context);

/* Positive, non-reused tokens, not pointers or OS handles. A failed close is permanently quarantined. */
typedef struct { uint64_t token; uintptr_t resource; unsigned state, published; } pwp_owned_handle;
typedef struct { pwp_owned_handle slots[PWP_HANDLE_LIMIT]; uint64_t next; int poisoned; } pwp_owner;
typedef int (*pwp_close_callback)(uintptr_t resource, void *context);
void pwp_owner_init(pwp_owner *owner);
pwp_result pwp_reserve(pwp_owner *owner, uint64_t *token);
size_t pwp_public_count(const pwp_owner *owner);
pwp_result pwp_publish(pwp_owner *owner, uint64_t token);
pwp_result pwp_attach(pwp_owner *owner, uint64_t token, uintptr_t resource);
pwp_owned_handle *pwp_lookup(pwp_owner *owner, uint64_t token);
pwp_result pwp_retire(pwp_owner *owner, uint64_t token, pwp_close_callback close, void *context);
pwp_result pwp_retire_all(pwp_owner *owner, pwp_close_callback close, void *context);
/* Caller serializes admission and supplies an already-created, unpublished exclusive handle.
 * Invalid arguments do not transfer ownership. Once admitted, every failure retires that exact handle;
 * success publishes its still-live lease. Flush is file-only, never namespace durability. */
typedef int (*pwp_lock_action)(void *context);
pwp_result pwp_lock_finish(pwp_owner *owner, uint64_t token, pwp_lock_action verify,
                           pwp_lock_action flush, pwp_close_callback close, void *context);
/* Fresh exact-handle directory tuples: private, one link, same volume, distinct nonzero file IDs. */
int pwp_expected_child_directory(const uint64_t *parent, const uint64_t *child, size_t count);
/* Fresh admitted directory tuples plus exact root/identity path scope. The native caller must also
 * prove direct parent-token ownership and an insensitive namespace on the same pinned handles. */
int pwp_vault_directory_scope(const uint64_t *root, const uint64_t *identity, size_t count,
                               const uint16_t *root_path, size_t root_length,
                               const uint16_t *identity_path, size_t identity_length);
/* Exact normal directory/file tuples for a new lock: same raw volume and distinct nonzero IDs. */
int pwp_expected_lock_file(const uint64_t *directory, const uint64_t *file, size_t count);
/* Caller serializes admission and has already created/attached one unpublished directory handle.
 * Verify must recheck the held parent and child, not open a name. Success publishes custody only;
 * failure closes that exact handle, without deleting a name or claiming namespace durability. */
pwp_result pwp_child_finish(pwp_owner *owner, uint64_t token, pwp_lock_action verify,
                            pwp_close_callback close, void *context);
/* Expected normal FILE tuple. Volume is unsigned/raw bits, not a positive signed Java Long. */
int pwp_expected_file(const uint64_t *words, size_t count, uint64_t parent_volume);
/* Caller serializes and owns one freshly opened, unpublished, exclusive file handle.
 * Success means deletion intent/readback + exact-handle retirement, NOT name absence or durability.
 * Preverification rejection only closes. Any uncertainty after mark starts quarantines, even if
 * the close callback succeeds. No retries and no pathname cleanup. Invalid args retain caller ownership. */
pwp_result pwp_delete_intent_finish(pwp_owner *owner, uint64_t token, pwp_lock_action verify,
                                    pwp_lock_action mark, pwp_lock_action pending_verify,
                                    pwp_close_callback close, void *context);
#endif
