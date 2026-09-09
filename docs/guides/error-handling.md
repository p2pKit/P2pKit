# Error handling and recovery

Use public error types and structured fields, not `reason`/message parsing.
[`P2pError`](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Errors.kt)
covers operational failures;
[`NetworkProvisioningError`](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/NetworkProvisioningError.kt)
is its provisioning branch. Only `FileTransferFailed` has `retryability`;
`LocalIdentityUnavailable` instead has `kind` and `recovery`. Other types require
operation/lifecycle context, not a universal retry rule inferred from their name.

## Handle the operation and its state

In Kotlin, propagate `CancellationException` unchanged before handling typed
failures (especially in a broader `Throwable` catch). Do not turn cancellation
into a retry, success, or a new identity. A source/destination callback that
throws `CancellationException` while the caller remains active can instead be
reported as a typed file I/O failure; inspect the *top-level* error, not just its
cause. A local callback's `AuthenticationFailed` cause is likewise not proof
that the secure channel failed.

Handle synchronous `create` exceptions, suspend-operation exceptions, and the
relevant retained state: `P2pKit.state`, `advertisingState`, `discoveryState`,
`P2pSession.state`, and a file handle's `state`. Subscribing to one does not
handle the others. StateFlow may conflate intermediate transitions. Sidecar
methods can return a `Failed` result; also observe their state/events as the
method contract requires. Background notification schedules work without waiting
for its outcome; use the suspending feature-stop methods when completion matters.

Keep a failed error instance if diagnostics need its cause: `copy()` on the
compatibility-preserved error data classes does not retain that diagnostic slot.
Preserve suppressed cleanup failures too, but redact reasons/causes before
logging: they can contain provider/platform data. Never log keys, credentials,
private payloads, or personal device identifiers.

## Core error reference

The following covers the 16 concrete cases in `Errors.kt`. It is recovery
guidance, not a claim that every public operation can throw every case.

| `P2pError` case | Typical boundary / observable consequence | Recommended action |
| --- | --- | --- |
| `LocalIdentityUnavailable` | Secure `create` cannot load/create identity; no transient identity or constructed transport is returned. | Follow `recovery` below. Never fall back to ephemeral or plaintext identity. |
| `NoTransportAvailable` | `connect` finds no registered data transport for the current peer hints. | Check provider registration and current reachability; retry only after useful new information, with a bounded policy. |
| `ConnectionFailed` | Connection/send, provider selection, startup rollback, or cleanup failed; this is not always a network outage. | Inspect the operation and lifecycle. A non-Connected session cannot send. Resolve retained cleanup before replacement; do not assume the same operation is safe to repeat. |
| `FileTransferFailed` | One attempt failed, either before a handle is returned or in `FileTransferState.Failed`. | Use `kind`, `phase`, `retryability`, and `transferId`; see below. |
| `ProtocolError` | Peer framing/protocol validation failed; session-level protocol failure is terminal. | Stop using that session, retain safe diagnostics, and investigate compatibility or malformed input. A protocol error wrapped as a file failure follows the outer transfer contract. |
| `PermissionMissing` | Advertising/discovery permission gate throws and publishes `FeatureState.PermissionRequired`. | The app requests the listed runtime permissions; retry after grant. Core `connect` itself does not perform that permission query. |
| `PayloadTooLarge` | Send/file preflight rejects the supplied size. | Reduce/split application data or choose an allowed file-transfer configuration. Do not loop on unchanged input or bypass receive limits. |
| `UnsupportedFeature` | Operation needs a feature the peer did not negotiate. | Choose a supported operation or a compatible peer; do not silently replace secure durable transfer with plaintext/flush-only transfer. |
| `HandshakeRejected` | HELLO was rejected and no usable new session is returned. | Check AppId/configuration/peer compatibility. Do not blindly redial the unchanged rejection. |
| `AuthenticationFailed` | Secure preface, key proof, or record authentication failed; secure setup/session cannot continue. | Treat as terminal; investigate before a new explicitly authorized attempt. Never downgrade or auto-repin. |
| `AuthorizationRejected` | The proved key is not admitted by the configured policy. | Keep it rejected. A user/application may separately approve a full fingerprint through a trusted out-of-band process; discovery text is not approval. |
| `SecurityConfigurationInvalid` | Required secure configuration/pin/identity is unavailable or inconsistent. | Correct configuration using trusted identity information before retrying; never switch to a weaker policy as recovery. |
| `AuthenticatedIdentityMismatch` | Proved identity differs from the selected peer/pin or encrypted HELLO. | Stop that attempt/session and investigate. Do not overwrite a trusted pin with the received identity. |
| `VersionMismatch` | Protocol major versions are incompatible. | Use compatible implementations/configuration. The secure mode is not negotiated down to v1. |
| `TransportInitializationFailed` | Factory throws or contradicts its descriptor during creation. | Fix the provider/configuration; startup has not begun. Providers must be resource-inert here. |
| `TransportStartFailed` | Explicit or lazy startup could not bring up a data transport. | Check the cause and OS/network prerequisites. Retry on the same kit only if rollback completed; uncertain rollback requires terminal stop and replacement. |

A failed startup with incomplete/timed-out rollback is fail-closed. Call `stop`
and retain its outcome before deciding whether a replacement can safely use the
same resources. `Stopped` is terminal even when stop reports `ConnectionFailed`;
it is not proof that an uncooperative native resource was released. Repeating
kit `stop()` normally returns the same teardown result, not a general cleanup
retry. Read the [lifecycle contract](../architecture/specification.md#lifecycle)
and the exact public method KDoc before choosing recovery.

`IllegalArgumentException`, `IllegalStateException`, and unsupported-stub
`UnsupportedOperationException` can indicate configuration or API misuse, such
as duplicate registration, use after stop, or responding to a terminal offer.
Correct the call sequence rather than treating these as transient network errors.
Arbitrary application/provider callbacks can also throw; this table does not
promise an exhaustive classification of user-code exceptions.

## File-transfer dispositions

`FileTransferState.Failed.error` is a `P2pError`, not necessarily a
`FileTransferFailed`: a real channel authentication failure retains its session-
level type. `Rejected` and `Cancelled` are separate terminal states. A pending
offer can expire as `Rejected("timeout")` at the receiver while a sender that
misses its notification later reports a typed `TIMEOUT` failure.

Every retry is a **new transfer attempt with a new transfer ID**. Failed handles
never resume. `transferId` can be null for pre-registration failures; otherwise
key records by `(session.id, transferId)`, not transfer ID alone.

| `Retryability` | Action, after checking current session/ownership |
| --- | --- |
| `RETRY_SAME_SESSION` | Wait for the blocking condition, such as outgoing capacity, to clear; then create a new transfer if that session is still Connected. Apply backoff and a finite attempt budget. |
| `RETRY_NEW_SESSION` | Re-establish an authorized usable session before a new transfer. Never resume the failed handle or downgrade security. |
| `RETRY_AFTER_USER_ACTION` | Stop automatic retries. Resolve storage permission/space, source availability, or the reported local condition first. |
| `NOT_RETRYABLE` | Do not retry this failed input/attempt automatically. Investigate and explicitly correct the cause before considering a different operation. |

Do not infer a Cartesian failure matrix from the enums: direction, operation,
and source of failure matter. These categories describe the failure, while the
actual `retryability` field controls its recovery:

| `FileTransferFailureKind` | Meaning / relevant context |
| --- | --- |
| `TRANSPORT` | A transport operation failed, including offer/data/control writes. |
| `REMOTE_DISCONNECTED` | Session/remote connection became unavailable to the attempt. |
| `TIMEOUT` | An offer, source/destination callback, streaming, or completion wait exceeded its budget; callback timeouts can require user action rather than merely a new session. |
| `INVALID_METADATA` | Local offer metadata/size/chunk representation is invalid. |
| `AUTHENTICATION` | Authentication-related transfer classification; genuine channel errors may instead be top-level `AuthenticationFailed`. |
| `INTEGRITY` | Received content/digest validation failed. Investigate; a digest alone does not authenticate its sender. |
| `SOURCE_CHANGED` | Source no longer matches the prepared snapshot. Keep the source immutable and explicitly prepare new input. |
| `SOURCE_IO` | Preparing/opening/reading the application source failed. |
| `STORAGE` | Destination setup/write/flush/commit or remote storage failed. |
| `UNSUPPORTED_FEATURE` | Required authenticated durable-transfer feature or source form is absent. |
| `TRANSFER_PROTOCOL` | Transfer framing/state/order/commit contract was violated. |

`FileTransferPhase` identifies where: `OFFER` (registration/decision), `ACCEPT`
(acceptance/setup), `SOURCE_READ` (source access), `SEND`, `RECEIVE`, `VERIFY`
(length/digest/order validation), `FLUSH`, or `DURABLE_COMMIT` (publication or
commit acknowledgement). It is not a progress/success guarantee. A remote
`FILE_RESULT` supplies a validated phase and maps digest/protocol/source-change
results to `NOT_RETRYABLE`, storage to `RETRY_AFTER_USER_ACTION`, and timeout to
`RETRY_NEW_SESSION`; not every local timeout uses that same disposition.

Sender failure/cancellation does **not** prove that no receiver output exists:
the receiver may have committed before its acknowledgement was lost, and an
already-running commit can finish late. Reconcile application-level file/operation
identity before resending; do not delete published output as “rollback.”
Destination `abort` is idempotent; on a thrown acceptance error the caller should
defensively invoke it as documented, because pre-acceptance refusal may never
have transferred ownership to the SDK. Cleanup failure must be retained, not
hidden by a retry.

## Local identity recovery

Use the supplied `LocalIdentityRecovery`, not a guessed mapping from error text
or a generic retry loop. `LocalIdentityFailureKind` provides finer diagnostics
for storage/provider/lost-key/live-identity/reset conditions, not permission to
replace keys automatically.

| `LocalIdentityRecovery` | Action |
| --- | --- |
| `RETRY` | Preserve the identity record and retry creation after the transient condition ends, with a bounded policy. |
| `RETRY_AFTER_DEVICE_UNLOCK` | Ask the user to unlock; retry only then. Do not weaken storage accessibility. |
| `CONFIGURE_STORE` | Supply the required protected `JvmSecureIdentityStore` before constructing a kit. Development in-memory stores are not a production substitute. |
| `FIX_PLATFORM_CONFIGURATION` | Fix the reported platform initialization, permission, entitlement, or provider setup. Do not wipe a healthy identity to bypass configuration. |
| `EXPLICIT_RESET_REQUIRED` | Stop for an explicit user/application decision. Platform identity reset is destructive, changes PeerId/fingerprint, and requires trusted peer re-pinning; first release live identity users and inspect the platform reset contract. Never automate this in a catch block. |

## Provisioning branch

These six cases are `NetworkProvisioningError` subtypes of `P2pError`. Provisioning
results/state are separate from session authentication and connectivity.

| Case | Recommended action |
| --- | --- |
| `PlatformError` | Inspect operation/state and a redacted `platformException`/cause. Correct the platform condition; no unconditional safe retry is implied. |
| `PermissionMissingForProvisioning` | Request the listed runtime permissions in the app, then retry the intended operation. |
| `HotspotStopped` | Hosting failed or the OS stopped the hosted resource. Update UI from retained resource/state, then decide whether to request new hosting. It does not prove cleanup succeeded or a joined network was released. |
| `JoinFailed` | Joining failed or a joined resource was lost. Check credentials/network/user action; do not loop or interfere with independently hosted resources. |
| `ManagerClosed` | Terminal disposal began. No new work is accepted; finish owned cleanup and construct a new manager/kit when safe. |
| `CleanupFailed` | A resource release was incomplete. Retain the owner/error; use the manager's documented cleanup retry, not a new acquisition over uncertain ownership. This can also arise during feature/resource cleanup, not just final close. |

`Unsupported` and `RequiresUserAction` provisioning results are not success and
must be handled explicitly. `stopLocalNetwork()` stops hosting, not a joined
Android Wi-Fi binding; terminal `close()` owns final disposal.

## Never blanket-retry security failures

`AuthenticationFailed`, `AuthorizationRejected`, and
`AuthenticatedIdentityMismatch` terminate that security attempt/session. A new
attempt is a deliberate decision after investigating/correcting the cause, not
a recovery loop. Never replace an approved pin using discovery text, silently
accept a different key, or retry authenticated-v2 failure as plaintext. See
[secure migration](migrating-to-0.7.md) and [the security model](../security/model.md).

Java consumers can use ordinary error getters and `instanceof`; this is not a
complete Java SDK promise (see [consumer-language limits](../compatibility.md#consumer-languages-and-java-interop)).
Kotlin/Native bridges annotated failures to catchable `NSError`/Swift `Error`;
a Swift catch is not automatically a typed Kotlin match. Exact generated-header
bridging examples and Apple validation remain separately tracked in
[#191](https://github.com/p2pKit/P2pKit/issues/191). Do not parse localized error
strings or invent an unverified `NSError.userInfo` key to recover the type.
