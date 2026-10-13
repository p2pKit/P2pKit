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
#define PWP_CUSTODY_ABI 13
#define PWP_TOKEN_BUFFER_LIMIT 4096u

typedef enum {
    PWP_OK = 0, PWP_ARGUMENT = 1, PWP_POLICY = 2, PWP_OS = 3,
    PWP_BUSY = 4, PWP_CLOSED = 5, PWP_LIMIT = 6, PWP_NOT_FOUND = 7,
    PWP_CLEANUP_UNKNOWN = 8, PWP_UNIMPLEMENTED = 9
} pwp_result;

/* Pure post-admission result precedence. Read both flags under the native gate; no cleanup/admission is performed. */
pwp_result pwp_cleanup_result(pwp_result result, int failed, int poisoned);

/* Byte-oriented decoding: never cast untrusted OS buffers to potentially unaligned structs. */
int pwp_token_valid(uint64_t token);
/* Validate an embedded SID view inside a successful bounded OS token query before any SID API reads it.
 * Caller first validates/copies the fixed SDK header. Address is observed from that header, never authority.
 * Outputs are cleared on refusal. This proves byte bounds/revision only, not account or token policy. */
int pwp_token_sid_view(const unsigned char *bytes, size_t capacity, size_t returned, size_t header,
                       uintptr_t address, size_t *offset, size_t *length);
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

/* Persistent pending record only, not publication or namespace durability. Native ownership closes the
 * original handle separately; preparation never closes, deletes, renames or promotes a disposable stage.
 * Once an OWNED candidate is filled, every error (including invalid input) makes it FAILED, never retryable. */
typedef enum {
    PWP_CANDIDATE_EMPTY = 0, PWP_CANDIDATE_OWNED, PWP_CANDIDATE_FILLING,
    PWP_CANDIDATE_VERIFIED, PWP_CANDIDATE_FAILED, PWP_CANDIDATE_RENAMING,
    PWP_CANDIDATE_RENAMED, PWP_CANDIDATE_UNCERTAIN
} pwp_candidate_phase;
typedef struct { pwp_candidate_phase phase; size_t prepared_size; } pwp_candidate;
typedef int (*pwp_candidate_read)(unsigned char *bytes, size_t capacity, size_t *read_count, void *context);
int pwp_candidate_name(const uint16_t *name, size_t length);
pwp_result pwp_candidate_init(pwp_candidate *candidate);
pwp_result pwp_candidate_fill(pwp_candidate *candidate, const unsigned char *bytes, size_t count,
                             pwp_stage_write write, pwp_stage_action flush, pwp_stage_action rewind,
                             pwp_candidate_read read, pwp_stage_verify verify, void *context);
/* Exact create-only destinations: root/profile.header, or identity/<64 lowercase hex>.aesgcm.
 * Scope must be exactly 0 (root) or 1 (identity). Syntax grants no directory/lease authority. */
int pwp_candidate_target(const uint16_t *name, size_t length, int identity_scope);
/* Replacement is narrower: canonical identity/<64 lowercase hex>.aesgcm only, never profile.header. */
int pwp_candidate_replace_target(const uint16_t *name, size_t length, int identity_scope);
/* Caller serializes access and keeps the original candidate handle and exact granting leases.
 * No close/delete/replace/durability. Callbacks must return normally, never throw/longjmp across this boundary.
 * Invalid callbacks retain VERIFIED; corrupted prepared_size is terminal FAILED. All admitted callbacks
 * observe RENAMING. Preverification failure is FAILED/no attempt; every failure after rename entry is
 * UNCERTAIN, including a false rename result. RENAMED is still not an ordinary or durable record. */
pwp_result pwp_candidate_rename_new(pwp_candidate *candidate, pwp_stage_verify before,
                                   pwp_stage_action rename, pwp_stage_verify after,
                                   pwp_stage_action flush, void *context);
/* Call only AFTER the original physical close attempt; never suppress that attempt on uncertainty.
 * False preserves native quarantine even if CloseHandle succeeded. Does not mutate candidate state. */
int pwp_candidate_close_ok(const pwp_candidate *candidate, int os_closed);

/* Exact native FILE_ACCESS_INFORMATION mask for an original sync-capable private directory:
 * READ_CONTROL | SYNCHRONIZE | FILE_LIST_DIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | FILE_ADD_FILE.
 * No generic, append, delete, write-sharing, owner-changing, or DACL-changing access is inferred. */
#define PWP_DIRECTORY_SYNC_ACCESS UINT32_C(0x001200a3)
int pwp_directory_sync_access(int query_succeeded, uint32_t granted_access);
typedef enum { PWP_SYNC_READY = 0, PWP_SYNC_RUNNING, PWP_SYNC_UNCERTAIN } pwp_directory_sync_phase;
typedef struct { pwp_directory_sync_phase phase; } pwp_directory_sync;
/* Caller serializes the original directory and exact profile/vault grants. Both verification callbacks
 * must check current NTFS custody, granted access and role generations. No handle is closed or reopened.
 * Preverification refusal does not flush. Any failure after flush entry is terminal uncertainty;
 * successful metadata flush is NOT a complete record transaction, bootstrap commit, or recovery policy. */
pwp_result pwp_directory_sync_apply(pwp_directory_sync *sync, pwp_stage_action verify,
                                    pwp_stage_action flush, void *context);
/* Call only after the original physical close attempt. Uncertainty survives a successful OS close. */
int pwp_directory_sync_close_ok(const pwp_directory_sync *sync, int os_closed);

/* Bounded complete-record request syntax only. Exact native root/identity custody and lease grants
 * must be checked separately, before allocation. Root header is always create-only. */
int pwp_record_write_request(const uint16_t *pending, size_t pending_length,
                             const uint16_t *target, size_t target_length, size_t count,
                             int identity_scope, int replace);
typedef enum {
    PWP_WRITE_NEW = 0, PWP_WRITE_PREPARING, PWP_WRITE_PUBLISHING, PWP_WRITE_SYNCING,
    PWP_WRITE_CLOSING, PWP_WRITE_COMPLETE, PWP_WRITE_FAILED, PWP_WRITE_UNCERTAIN
} pwp_record_write_phase;
typedef struct { pwp_record_write_phase phase; uint64_t candidate; } pwp_record_write;
typedef pwp_result (*pwp_record_prepare)(uint64_t *candidate, void *context);
typedef pwp_result (*pwp_record_action)(uint64_t candidate, void *context);
typedef void (*pwp_record_uncertain)(uint64_t candidate, void *context);
/* One already-admitted, serialized operation, with zero-initialized per-call state. Prepare returns
 * only its original owned candidate (even on late failure); zero on failure means none to adopt.
 * Every valid nonzero returned owner is closed exactly once, never by a pathname. A successful prepare
 * with no valid owner is a contract uncertainty, not guessed cleanup. Publish must report UNKNOWN for
 * any possibly attempted failed publication. Sync includes original-candidate checks on both sides.
 * Once publication succeeded, every later failure is UNKNOWN, including pre-flush refusal. The memory-
 * only uncertain callback seals admission/marks candidate before cleanup; it must never close or do I/O.
 * After close failure it may seal the session but must not inspect a retired original. All callbacks
 * return normally. No reentry/retry/reset, capability grant, bootstrap, deletion or recovery is implied. */
pwp_result pwp_record_write_apply(pwp_record_write *write, pwp_record_prepare prepare,
                                  pwp_record_action publish, pwp_record_action sync,
                                  pwp_record_action close, pwp_record_uncertain uncertain, void *context);

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
/* Candidate publication with cooperative replacement, NOT expected-ID compare-and-swap or durability.
 * The caller keeps the original candidate and granting profile/vault leases throughout. It supplies
 * either one freshly opened, exclusive, unpublished target owner, or zero after exact NOT_FOUND.
 * Invalid arguments/non-VERIFIED state retain caller ownership. After admission every path retires
 * that target exactly once, including failed source/target verification. Close ambiguity poisons the
 * owner and forbids rename. Successful target retirement is followed by fresh source/grant verification.
 * The rename callback receives replace=1 only for the admitted existing target; absent targets use
 * create-only, with no fallback on failure. All callbacks observe RENAMING and return normally.
 * The original candidate is never closed here. Failure before rename is FAILED; any failure after
 * rename entry is UNCERTAIN. A successful result remains RENAMED, not ordinary/durable metadata. */
typedef int (*pwp_replace_action)(int replace, void *context);
pwp_result pwp_candidate_replace(pwp_candidate *candidate, pwp_owner *owner, uint64_t target,
                                 pwp_stage_verify before, pwp_stage_action target_verify,
                                 pwp_close_callback target_close, pwp_replace_action rename,
                                 pwp_stage_verify after, pwp_stage_action flush, void *context);
/* Serialized native role ledger, not a filename/public-handle inference. Native callers must independently
 * verify the fixed root/identity/file scope on the original handles before binding a published role.
 * Metadata custody alone grants no mutation. Do not reset either owner or roles to recover from uncertainty. */
typedef enum { PWP_LEASE_NONE = 0, PWP_LEASE_PROFILE, PWP_LEASE_VAULT } pwp_lease_role;
typedef struct { uint64_t root, directory, profile, vault; } pwp_role_grant;
/* Unpublished-record dependants: disposable stages AND persistent candidates bind their native owner token
 * and exact granting leases here. This ledger controls dependency retirement, never a deletion policy. */
typedef struct { uint64_t token; pwp_role_grant grant; } pwp_role_stage;
typedef struct {
    uint64_t root, identity, profile, vault, vault_profile, vault_directory, root_floor;
    int opening, retiring_all;
    pwp_role_stage stages[PWP_PUBLIC_HANDLE_LIMIT];
} pwp_roles;
void pwp_roles_init(pwp_roles *roles);
/* Exact fixed spellings only. The returned selector grants no role until native verification/publication. */
pwp_lease_role pwp_lease_name(const uint16_t *name, size_t length);
/* Begin before acquiring any new root/ancestor handle; every previous original owner must be retired. */
pwp_result pwp_roles_begin_root(pwp_roles *roles, const pwp_owner *owner);
pwp_result pwp_roles_bind_root(pwp_roles *roles, const pwp_owner *owner, uint64_t token);
/* Canonical direct root/identity custody may be opened before the profile lease, but cannot mutate. */
pwp_result pwp_roles_identity_admit(const pwp_roles *roles, const pwp_owner *owner, uint64_t parent);
pwp_result pwp_roles_bind_identity(pwp_roles *roles, const pwp_owner *owner, uint64_t parent, uint64_t token);
pwp_result pwp_roles_lease_admit(const pwp_roles *roles, const pwp_owner *owner,
                                uint64_t directory, pwp_lease_role role);
pwp_result pwp_roles_bind_lease(pwp_roles *roles, const pwp_owner *owner,
                               uint64_t directory, pwp_lease_role role, uint64_t token);
/* Capture before payload allocation/OS mutation; recheck the exact root/profile/vault generation on use. */
pwp_result pwp_roles_capture(const pwp_roles *roles, const pwp_owner *owner,
                            uint64_t directory, pwp_role_grant *grant);
pwp_result pwp_roles_check_grant(const pwp_roles *roles, const pwp_owner *owner, const pwp_role_grant *grant);
pwp_result pwp_roles_bind_stage(pwp_roles *roles, const pwp_owner *owner,
                               uint64_t token, const pwp_role_grant *grant);
pwp_result pwp_roles_check_stage(const pwp_roles *roles, const pwp_owner *owner, uint64_t token);
/* Ordinary retirement rejects dependent stages/vaults. Poison also retains parents of unpublished failures.
 * Whole-root retirement instead attempts every independent original owner in reverse order, retaining
 * uncertainty. Only complete clean retirement resets the role ledger; native tokens are never reset. */
pwp_result pwp_roles_retire(pwp_roles *roles, pwp_owner *owner, uint64_t token,
                           pwp_close_callback close, void *context);
pwp_result pwp_roles_retire_all(pwp_roles *roles, pwp_owner *owner, pwp_close_callback close, void *context);
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
/* Post-deletion absence is a raw, final NtCreateFile STATUS_OBJECT_NAME_NOT_FOUND result and a NULL
 * returned handle, never a DOS-error/NOT_FOUND aggregation. IO_STATUS_BLOCK contents cannot replace a
 * final nonpending return status. No other status or handle indication proves exact name absence. */
int pwp_exact_name_absence(uint32_t status, int null_handle);
/* Failed read-only FILE_OPEN after the original probe's retirement. Only final NAME_NOT_FOUND+NULL
 * and fully successful retirement authorize an absent-target branch. A PATH_NOT_FOUND/DOS mapping,
 * pending/late handle or malformed success is an OS failure, not creation authority. Failed/unknown
 * retirement remains UNKNOWN. This classifier never closes or inspects a retired owner. */
pwp_result pwp_strict_open_failure(uint32_t status, int null_handle, pwp_result retirement);
/* Caller owns a freshly reserved unpublished probe, attaching any valid returned handle before entry.
 * A missing/invalid raw handle leaves its reservation empty; null_handle must distinguish NULL from an
 * invalid non-NULL sentinel. All admitted paths retire that original probe once, even OS/policy failures.
 * No deletion/metadata repair. Only exact missing + empty reservation + clean retirement + fresh original
 * parent/grant verification returns NOT_FOUND. Everything else is UNKNOWN; invalid args retain ownership.
 * Verification may reuse the retired probe slot. Never inspect the retired pointer/token afterward. */
pwp_result pwp_name_absence_finish(pwp_owner *owner, uint64_t probe, uint32_t status, int null_handle,
                                   pwp_lock_action verify, pwp_close_callback close, void *context);
typedef enum {
    PWP_DELETE_NEW = 0, PWP_DELETE_INTENT, PWP_DELETE_OBSERVING, PWP_DELETE_SYNCING,
    PWP_DELETE_COMPLETE, PWP_DELETE_FAILED, PWP_DELETE_UNCERTAIN
} pwp_record_delete_phase;
typedef struct { pwp_record_delete_phase phase; } pwp_record_delete;
typedef pwp_result (*pwp_record_step)(void *context);
typedef void (*pwp_delete_uncertain)(void *context);
/* One already-admitted operation; original grants/parent stay owned throughout. remove owns original-ID
 * validation, deletion intent/readback and its exact close, reporting UNKNOWN for any possibly attempted
 * failed deletion. A safe pre-intent NOT_FOUND is still an error, not successful absence. After remove OK,
 * only strict absence NOT_FOUND then successful original-directory sync may complete. Any later failure
 * seals uncertainty; the memory-only seal never reads/recloses the already-retired original file.
 * Zero-initialize per call. No retry/reset/reentry, borrowed handles, path deletion, recovery or capability. */
pwp_result pwp_record_delete_apply(pwp_record_delete *deletion, pwp_record_step remove,
                                   pwp_record_step absent, pwp_record_step sync,
                                   pwp_delete_uncertain uncertain, void *context);
/* A failed FILE_CREATE is known not to have created an entry only for final NAME_COLLISION+NULL.
 * No DOS aggregation or failure IO_STATUS_BLOCK inference; any other attempted-create failure is uncertain. */
int pwp_create_collision_without_effect(uint32_t status, int null_handle);
/* Three-way observation of an attempted synchronous FILE_CREATE, before phase initialization or data I/O.
 * OK requires raw+I/O success, FILE_CREATED and one valid non-NULL handle. OS is only exact final collision
 * with NULL (no new entry); failure I/O status/information never supply no-effect authority. Every other
 * observation is UNKNOWN, including malformed booleans/handles. Caller retains/attaches valid originals,
 * seals UNKNOWN before actual retirement, and lets cleanup uncertainty override an otherwise clean collision. */
pwp_result pwp_create_observation(uint32_t status, uint32_t io_status, uint64_t information,
                                  int null_handle, int valid_handle);
typedef enum {
    PWP_NAMESPACE_NEW = 0, PWP_NAMESPACE_VERIFYING, PWP_NAMESPACE_SYNCING, PWP_NAMESPACE_PUBLISHING,
    PWP_NAMESPACE_COMPLETE, PWP_NAMESPACE_FAILED, PWP_NAMESPACE_UNCERTAIN
} pwp_namespace_phase;
typedef struct { pwp_namespace_phase phase; } pwp_namespace_commit;
typedef pwp_result (*pwp_namespace_sync)(size_t index, void *context);
/* Fixed, already-admitted creation/admission finalization, never public pre-lease sync authority.
 * The caller retains exact original owners and scopes. verify checks all original identities/grants;
 * 1..3 ordered sync callbacks are followed by that same verification before publication. created is
 * exactly0/1 and records any known/possible namespace creation before entry. Any failure after creation
 * or sync entry is UNKNOWN; the memory-only seal runs once before caller-owned actual retirement.
 * This controller never closes/reopens, infers a role from a name, or makes a pending file recoverable.
 * Invalid callbacks/count retain caller ownership. Zero initialize; no reset/reentry/retry. */
pwp_result pwp_namespace_commit_apply(pwp_namespace_commit *commit, int created, size_t count,
                                      pwp_record_step verify, pwp_namespace_sync sync,
                                      pwp_record_step publish, pwp_delete_uncertain uncertain, void *context);
#endif
