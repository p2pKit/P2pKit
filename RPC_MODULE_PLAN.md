# Optional LAN RPC module for P2pKit

> Planning snapshot saved at the owner's request. Workspace-status statements below describe the investigation before this Markdown file was created. Saving this plan does not approve or start implementation.

## 1. Verified project understanding

### Workspace and baseline

- Clone: `/root/projects/p2pkit-feature-prep-20260927-yiDjCB`
- Detached HEAD and `origin/main`: `3bc76f956f8f47447b51a62474fc878b9c43173c`
- Remote main was checked again and has not advanced.
- Worktree is clean. `AGENTS.md` and `CLAUDE.md` were read completely and remain unchanged.
- No implementation, feature branch, builds, SDK/dependency downloads, or hosted execution started.
- Release Foundation remains **NOT_READY**, with all HOLDs and gates preserved.

Current lockfiles still contain `org.jmdns:jmdns:3.6.3` entries despite the embedded JmDNS implementation. This remains separate baseline evidence—not an RPC regression. No repair was copied, regenerated, or independently runtime-verified.

### What exists and what can be reused

| Area | Verified capability and limitation |
|---|---|
| Modules and targets | Core, LAN transport, and optional platform provisioning modules. Targets are JVM 17, Android API 24+, and iOS device/simulator targets—not JS or Wasm. See [module mapping](settings.gradle.kts) and [core target configuration](library/p2p-core/build.gradle.kts). |
| Topology | Sessions are explicitly established, one-to-one connections. Nothing requires an automatic mesh. Advertising and discovery are separately controlled. See [P2pKit](library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pKit.kt). |
| Transport and framing | LAN uses TCP with JmDNS/Bonjour discovery. Core already supplies framing, chunking, reassembly, integrity checks, and encrypted records. RPC should reuse these rather than introduce another socket or framing stack. See [DefaultP2pProtocol](library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/DefaultP2pProtocol.kt) and [Reassembler](library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/Reassembler.kt). |
| Delivery and ordering | Session writes are serialized. A successful `send()` proves local write completion, not handler execution. Core ACK packets are ignored; they are not application acknowledgements. TCP ordering does not imply ordering of concurrent business operations. See [P2pSession](library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pSession.kt) and [session implementation](library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pSessionImpl.kt). |
| Reconnection and lifecycle | Outgoing sessions can reconnect with bounded attempts; incoming sessions do not redial. Reconnection preserves the public session while replacing the connection/security epoch. There is no RPC replay or durable call queue. Incoming flows have no replay and do not complete on session termination; their owners must cancel collectors. |
| Security | Authenticated v2 uses Noise XX, X25519 identities, and ChaCha20-Poly1305. Identity is AppId-bound. Unknown peers are rejected by default; full fingerprints support explicit pinning. Discovery information is not authorization. See [security configuration](library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Config.kt), [identity/QR API](library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Identity.kt), and [authentication implementation](library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/AuthenticatedV2SecurityEngine.kt). |
| Testing and compatibility | Existing tests use deterministic fake connections, explicit security fixtures, virtual time, and strict teardown assertions. API/ABI and dependency gates include explicitly listed modules. Existing published APIs/wire history must remain intact. See [testing conventions](docs/testing/local.md) and [root build gates](build.gradle.kts). |

Existing durable **file-transfer** facilities do not establish durable RPC delivery.

### Important missing capabilities

1. Procedure registration, typed RPC payload contracts, correlation, application-error responses, and call lifecycle management.
2. Application-level deduplication and result recovery across reconnects.
3. Live trust enrollment/revocation: `PinnedOnly` currently holds an immutable snapshot.
4. Uniform, restrictive organization-network endpoint policy.
5. Public structured session failure and connection-generation observations.
6. Aggregate resource controls suitable for the requested host capacity.

Two capacity prerequisites are particularly important:

- The current **64-active-session threshold applies to net-new inbound admission**, not all possible sessions. It still prevents the requested 128-client host configuration. See [admission policy](library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/SessionManager.kt#L1880).
- JVM and Android use blocking socket reads and writes on shared `Dispatchers.IO`. At 128 long-lived connections, blocking reads could starve writes/setup work. This is a source-identified risk, not a measured result. See [JVM read loop](library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmRawConnection.kt#L168) and its Android counterpart.

**Consequently, this feature requires additive core/LAN prerequisites—not merely a thin RPC wrapper.**

## 2. Recommended architecture

### Module and dependency direction

Add one optional `p2p-rpc` module:

```text
Application / shared procedure definitions
                   ↓
                p2p-rpc
                   ↓
       p2p-core + p2p-transport-lan
                   ↓
 Existing platform networking/security facilities
```

- Common Kotlin contains procedure definitions, protocol handling, dispatch, correlation, limits, and retry/deduplication logic.
- Platform factories configure existing LAN transports and secure identity storage.
- Existing provisioning factories supply manual-address fallback; RPC does not initiate hotspot creation or Wi-Fi joining.
- Core and LAN never depend on RPC.
- No cloud dependency, new transport stack, alternate encryption protocol, or new database dependency.

The RPC façade owns a dedicated kit and its scopes. MVP will **not** accept an arbitrary borrowed `P2pKit`, because that could bypass transport, admission, or LAN-policy guarantees.

### Roles and topology

- **Host:** accepts approved clients, dispatches registered procedures, returns responses, and optionally sends registered notifications.
- **Client:** connects only to one explicitly selected, pinned host.
- Clients do not advertise themselves as RPC hosts, accept RPC clients, discover-and-connect automatically, or forward requests to other clients.
- Notifications use the existing client–host connection; they do not require reverse connections.
- Role changes require closing the current runtime and explicitly creating the other role.

Both roles target JVM, Android, and iOS. Mobile hosting is foreground-oriented. Android background operation requires an application-owned, OS-permitted foreground service. **An always-running iOS background server is not promised.**

### Additive prerequisites

Implement these as opt-in capabilities, preserving ordinary P2P defaults:

1. **Admission and capabilities:** live authenticated admission with trusted, enrollment-only, and rejected states; restricted message types; configurable session/resource limits.
2. **Session observations:** retained structured failure information and connection generations, without parsing exception strings.
3. **Reconnect scheduling:** bounded backoff/jitter and explicit permanent-failure filtering, using the existing connection owner.
4. **LAN policy:** validated endpoints, interface/network selection, optional fixed listening port, and dial-only client mode.
5. **I/O scheduling:** separate bounded JVM/Android read, write/setup, and cleanup capacity. Do not change global dispatcher settings or add a second transport implementation.

A failure to meet mobile capacity with these bounded changes is a **stop-and-review gate**, not permission to silently rewrite the networking stack.

## 3. Proposed public API

These sketches are **proposals, not implemented or compiled APIs**.

Applications share explicit procedure descriptors and serializers:

```kotlin
val ReadStock = RpcProcedure(
    name = "inventory.read-stock",
    version = 1,
    request = StockRequest.serializer(),
    response = StockReply.serializer(),
    applicationError = StockError.serializer(),
    retrySafety = RpcRetrySafety.Idempotent,
)
```

Platform wiring provides the appropriate context and identity store:

```kotlin
// Platform-specific construction:
// RpcPlatform.jvm(protectedJvmIdentityStore)
// RpcPlatform.android(applicationContext)
// RpcPlatform.ios()
```

### Host setup and handler registration

```kotlin
val host = RpcHost.create(platform, applicationScope) {
    appId = AppId("org.example.inventory.rpc")

    lan = OrganizationLan(
        allowedSubnets = organizationCidrs,
        interfaceSelection = approvedInterface,
        listenPort = configuredPort,
    )

    trustStore = applicationTrustStore
    limits = RpcLimits.host128()

    register(
        ReadStock,
        authorize = { identity -> acl.mayReadStock(identity) },
    ) { context, request ->
        inventoryService.readStock(request, context.peer)
        // Application-owned logic returning RpcReply<StockReply, StockError>.
    }
}

host.start()
```

Registration is explicit and frozen when the host starts. Duplicate procedure identities fail locally. There is no reflection-based invocation, remote class loading, arbitrary function naming, or remotely supplied executable code.

### Pairing and live revocation

```kotlin
val invitation = host.pairing.createInvitation(expiresIn = 2.minutes)
showQrLocally(invitation.qr)

// UI observes host.pairing.pending.
// Only an explicit administrator action approves a specific request:
host.pairing.approve(selectedPendingRequest.id)

// A later administrator action takes effect without restarting:
host.trust.revoke(selectedClientFingerprint)
```

The trust store is application-supplied, local, durable security configuration—not an RPC business database.

### Client connection, typed call, and errors

```kotlin
val client = RpcClient.create(platform, applicationScope) {
    appId = AppId("org.example.inventory.rpc")
    lan = OrganizationLan(organizationCidrs, approvedInterface)
    trustStore = applicationTrustStore
}

val selectedHost = client.pair(RpcInvitation.parse(scannedQr))
client.connect(selectedHost)
// Manual fallback supplies a validated numeric address and port,
// while retaining exactly the same trusted host fingerprint.

try {
    when (
        val reply = client.call(
            ReadStock,
            StockRequest("SKU-123"),
            timeout = 10.seconds,
            retry = RpcRetry.Idempotent(maxAttempts = 3),
        )
    ) {
        is RpcReply.Success -> display(reply.value)
        is RpcReply.ApplicationError -> displayBusinessError(reply.error)
    }
} catch (cancelled: CancellationException) {
    throw cancelled
} catch (failure: RpcFailure) {
    displayInfrastructureFailure(
        failure.kind,
        failure.requestId,
        failure.executionEvidence,
    )
    // An uncertain outcome must not trigger an automatic fresh submission.
}
```

Infrastructure failures expose typed kind, phase, request ID, execution evidence, and retry advice. Application errors remain explicitly serialized application types.

Connection state is available through `StateFlow`; diagnostics provide bounded counters/events. Kotlin/Native suspend boundaries preserve catchable errors and cancellation. Swift applications can use a small shared-Kotlin façade rather than manipulate serializers directly.

### Notifications

```kotlin
client.notifications(StockChanged)
    .onEach(::refreshDisplayedStock)
    .launchIn(applicationScope)

val result = host.tryNotify(clientIdentity, StockChanged, update)
```

`tryNotify` reports local enqueue/refusal—not remote receipt. Notifications are separate from responses and cannot complete an RPC call.

## 4. Protocol and reliability contract

### Encoding and compatibility

Use a versioned RPC envelope inside `P2pMessage.Binary`:

- Small bounded header containing message kind, protocol version, procedure/version, logical request ID, host incarnation, and attempt/deadline information.
- Application bodies encoded using explicit `kotlinx.serialization` JSON serializers.
- Length-delimited body bytes—not a JSON-encoded byte array wrapped inside another JSON document.
- Core retains ownership of fragmentation, reassembly, encryption, and socket delivery.

MVP message families cover negotiation, invocation, response/application error, infrastructure refusal, status recovery, cancellation, response receipt, pairing, and notification.

A bounded HELLO/READY exchange runs after every new authenticated connection generation. Collectors are attached before readiness/advertising. This addresses the existing hot-flow subscription race without pretending the underlying flow has replay.

Unsupported protocol majors or required features fail explicitly. No plaintext downgrade or silent codec/schema fallback is allowed.

### Request lifecycle

1. Client allocates a random logical request ID, freezes encoded request bytes, and starts one monotonic overall deadline.
2. Local admission and payload limits are checked before transmission.
3. Host validates protocol, identity, authorization, procedure, size, and resource availability.
4. Host atomically installs a deduplication record **before** starting the handler.
5. The registered handler returns success or an application error; the host encodes one terminal outcome.
6. Client validates and correlates the response, then completes the call once.

Success means the client received a valid success response from the registered handler. It means a database transaction committed **only if the application handler defines success that way**.

Concurrent handlers and responses may finish out of order. Business ordering remains application-owned.

### Duplicate handling and retained outcomes

Deduplication is scoped to authenticated client identity plus logical request ID, within a host incarnation.

- Same ID and same procedure/frozen payload: join the existing execution or return its retained outcome.
- Concurrent duplicates never start another handler while the record exists.
- Same ID with different contents is a protocol violation.
- Late or duplicate responses cannot complete a call twice.
- Running records are not evicted to make room for new calls.

Recommended retention:

- Completed records/tombstones: **60 seconds**, without early eviction.
- Maximum records: **1,024 per client; 131,072 per host**.
- Encoded responses: up to **30 seconds**, subject to a **32 MiB aggregate** cache.
- Response payloads may be reclaimed earlier after receipt or under pressure, but their tombstones remain.

A small best-effort **response-receipt message** allows prompt payload reclamation at the requested call rate. It is not a delivery, execution, or durability guarantee.

A tombstone with no retained response produces `ResultUnavailable`; it never authorizes re-execution. Once records expire, the module cannot guarantee deduplication. Official clients must not silently replay expired calls.

### Retries and uncertain outcomes

| Situation | Contract |
|---|---|
| Definitely not transmitted, or explicit host refusal before execution | Eligible for bounded retry under the call policy. |
| Send began, then connection failed | Execution may have occurred. Default recovery is status/result lookup, not a fresh invocation. |
| Existing running/completed record found | Attach to it or return its retained response. |
| No record found during recovery | Outcome remains unknown; default policy does not execute the request. |
| Procedure and caller explicitly opt into idempotent retry | Re-invocation may be attempted with the same logical ID and frozen payload, within the same deadline/incarnation. Incorrect idempotency declarations remain an application risk. |
| Authentication/pin/authorization failure, malformed protocol, incompatible version | No automatic retry or downgrade. |
| Host incarnation changed | No automatic replay of pending calls, including nominally idempotent ones. Report restart/uncertainty; subsequent new calls require normal application action. |

Recommended call policy:

- Default deadline: **10 seconds**; configurable up to **30 seconds**.
- At most **three call-level invocation/recovery attempts**, including the initial attempt.
- Exponential full-jitter backoff, starting at 100 ms and capped at 2 seconds.
- Respect bounded server retry-after information.
- All encoding, queue waits, reconnect waits, and attempts consume the same deadline.
- Overall deadline expiry ends recovery; it does not start a new timeout window.

Connection reconnection remains a separate shared operation: at most five attempts within a 30-second recovery window, with jitter. It restores connectivity, not business execution guarantees. New calls while disconnected fail locally rather than entering an offline queue.

### Cancellation, deadlines, and restart

- Coroutine cancellation remains `CancellationException`.
- Before local transmission, cancellation can establish “not sent.”
- After transmission begins, cancellation is best effort. The host removes queued work or requests cooperative handler cancellation.
- Cancellation does **not** undo side effects or prove the handler stopped.
- Handler jobs belong to the host runtime, not an individual incoming session, allowing retained outcomes to survive a connection loss.
- A non-cooperative handler retains its execution slot until it actually terminates.
- Server-side remaining-time budgets are clamped at first admission and never extended by duplicates. Unsynchronized clocks and network delay prevent promising an exact remote stop time.
- Restart loses in-memory execution/results and changes the host incarnation.

**No end-to-end exactly-once, crash-safe delivery, durable offline queue, or transactional deduplication is promised.** Stronger guarantees require application-owned durable idempotency records committed atomically with the business operation.

## 5. Security and LAN-only operation

### Enforced network boundary

Current LAN behavior alone is insufficient:

- [JVM dialing](library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDataTransport.kt) does not impose the proposed organization-CIDR policy.
- Android selects suitable networks but does not enforce approved remote subnets.
- [Apple transport](library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDataTransport.kt) prohibits cellular but currently permits peer-to-peer/AWDL and may use opaque Bonjour endpoints.

The RPC profile will require:

1. Explicit approved private IPv4/IPv6 subnets; routed organizational VLANs are allowed.
2. Validated numeric endpoints for application TCP connections.
3. Interface/network binding and available OS path checks; no silent default-route fallback.
4. Revalidation on discovery changes, reconnect, and network-path changes.
5. Rejection of public destinations, forbidden interfaces, cellular/VPN paths identified by the platform, and unverifiable strict-policy routes.
6. No general hostname lookup in the manual fallback. Bonjour resolution must remain local and produce policy-checkable endpoints.
7. Apple peer-to-peer/AWDL disabled for this profile. If an opaque endpoint cannot be checked safely, require the numeric-address fallback.
8. Discovery multicast restricted to approved interfaces; application data never placed in discovery metadata.

No cloud fallback, public relay, external RPC processing endpoint, or automatic telemetry export is introduced.

**Boundary limitation:** endpoint checks and source binding cannot prove what upstream routers or administrator-installed tunnels do. The organization must enforce routing/firewall policy against offsite forwarding. Documentation must distinguish SDK enforcement from deployment assurance rather than describe private addresses alone as proof of local-only transit.

### Pairing and trust

Use the owner-selected workflow:

1. Host creates a short-lived, single-use invitation containing the existing AppId-bound full host fingerprint, an invitation identifier, and a 256-bit CSPRNG secret.
2. Client scans it through a trusted local channel and pins the host before sending enrollment material.
3. Unknown clients may enter a tightly bounded **encrypted enrollment-only quarantine** while invitations are active.
4. They cannot invoke procedures, transfer files, receive notifications, or access retained results.
5. A valid invitation is atomically bound to the authenticated client identity.
6. Administrator approval persists that identity before normal admission.
7. Client establishes a fresh fully authorized connection.

Do not globally enable `AcceptAnyAuthenticatedSameApp` as the pairing implementation.

Default invitation lifetime is two minutes; at most four quarantine connections are admitted. Invitation secrets are redacted from diagnostics and not persisted as ordinary application data.

Live revocation denies new work and cached-result access immediately, closes affected sessions, and requests cancellation of active handlers. It cannot reverse completed side effects. Approval/revocation storage failures fail closed and must not be reported as successfully persisted changes.

### Authorization and defensive processing

- Procedure authorization is application-controlled and deny-by-default.
- The authenticated identity—not a request field—identifies the caller.
- Authorization is rechecked before returning retained results.
- Business/resource-level authorization and validation stay in application code.
- Enforce lengths before large allocations, with aggregate core-level budgets before RPC decoding.
- Bound JSON nesting/structural complexity and reject malformed/duplicate protocol fields.
- Disable file-transfer and unrelated application-message paths in the RPC-owned kit.
- Never return host stack traces, SQL errors, payload fragments, or raw exception messages as infrastructure errors.
- Diagnostics expose bounded status/counter data, not payloads, invitation secrets, or credentials.

Permissions remain application-controlled. Document Apple local-network/Bonjour declarations, Android’s platform-dependent LAN permission requirements, and foreground/background restrictions.

## 6. Bounded MVP and implementation phases

### Recommended initial limits

These are proposed defaults for approval, not measured capacity claims.

| Resource | Default |
|---|---|
| Connected trusted clients | 128 |
| Enrollment-only connections | 4 additional |
| Concurrent inbound handshakes | 16; preserve source-level admission protection |
| Outstanding calls per client | 8 |
| Host execution | 128 running, 256 queued; no more than 8 accepted calls per client |
| Encoded request/response body | Hard ceiling 1 MiB; procedures default to 64 KiB unless explicitly raised |
| Aggregate retained payload accounting | 64 MiB across core/RPC buffers, with per-peer limits |
| Response cache | At most 32 MiB within that budget |
| Notifications | 16 KiB each; 16 entries/128 KiB per peer; 1 MiB aggregate |

Admission reserves necessary capacity before execution. New work is rejected with typed overload errors when safe to do so; transport-level exhaustion may instead close the connection, leaving an already transmitted call uncertain.

Notifications are best-effort, non-durable, non-replayed, and dropped under their own pressure policy. Responses/control take priority between messages; they cannot preempt a message already being written.

Byte accounting is **not an exact process-memory ceiling**. Object graphs, defensive copies, thread stacks, OS socket buffers, and application-held objects require measurement.

### Non-goals

- Databases, transactions, storage engines, synchronization, or application business frameworks.
- Durable queues or crash-safe RPC results.
- Streaming RPC, replayable event logs, remote subscriptions, or client-side procedures.
- Leader election, automatic host selection, failover, clustering, or replication.
- Public-Internet connectivity, relays, VPN setup, hotspot orchestration, or arbitrary transport injection.
- Universal 128-client performance on every device meeting the minimum OS version.

### Phases after approval and execution authorization

1. **Freeze the implementation baseline.** Recheck main, summarize any advancement, create a uniquely named feature branch, and report directory, branch, exact base SHA, and clean status.
2. **Implement generic prerequisites.** Admission/quarantine, resource accounting, session observations, LAN enforcement, and bounded I/O scheduling. Preserve existing P2P defaults and compatibility.
3. **Implement RPC mechanics.** Registration, bounded codec/envelopes, negotiation, dispatch, deadlines, correlation, deduplication, recovery, cancellation, and errors.
4. **Implement pairing and notifications.** Local trust-store integration, administrator workflow, revocation, bounded notification delivery, state visibility, and sanitized diagnostics.
5. **Add examples, documentation, and verification integration.** Include the new module deliberately in applicable API/ABI, dependency, documentation, and repository gates.
6. **Run separately authorized qualification.** Stop for review if security/path enforcement or mobile capacity cannot meet the approved contract.

Future integration comes from main normally. No unfinished Foundation or campaign source is copied into the feature.

## 7. Verification plan

### Permitted and completed now

- Read-only architecture, lifecycle, security, transport, and test-convention inspection.
- Git/GitHub inspection of the main baseline.
- Instruction-file comparison and clean-worktree verification.
- `git diff --check`.
- Static inspection of current dependency-lock entries.

No runtime or platform qualification is inferred from those checks.

### Tests to implement, then run only with authorization

| Scenario | Required assertion |
|---|---|
| Normal concurrent calls | Correct typed correlation, application errors remain distinct, out-of-order completions are safe. |
| Star topology | Only the selected host is contacted; clients do not accept or establish a mesh. |
| Subscription/connection races | Early traffic, reconnect generations, and missing READY responses cannot silently lose an admitted call or leak collectors. |
| Duplicate requests | Concurrent duplicates execute once within the retained record; completed duplicates return retained results; altered-payload ID reuse is rejected. |
| Lost responses/disconnects | Recovery returns a retained outcome when available; otherwise reports uncertainty without unsafe execution. |
| Unsafe retries | Non-idempotent handlers are not silently re-invoked after ambiguous sends, restart, or expiry. |
| Timeouts/cancellation | Cover before-send, queued, running, side-effect-completed, and late-response races; preserve cancellation and resource ownership. |
| Retention limits | Exercise receipt loss, early response eviction, tombstone expiry, full record tables, and active records that must not be evicted. |
| Host restart/sleep | Incarnation changes prevent stale replay; reconnect restores only connectivity; mobile lifecycle behavior matches documented restrictions. |
| Pairing/revocation | Invalid/expired/reused invitations, competing clients, approval races, storage failures, live revocation, and cached-result authorization. |
| Malformed/unauthorized traffic | Unknown procedures, incompatible versions, oversized/nested payloads, plaintext downgrade attempts, prohibited message types, and unapproved identities fail safely. |
| Resource pressure | Queue/byte/concurrency limits, slow readers, 128 idle socket readers, I/O starvation, handler non-cooperation, and teardown accounting remain bounded. |
| Compatibility | Existing P2P behavior, public API compatibility, secure-v2 behavior, and immutable release history remain intact. |

Use deterministic common tests with fake clocks/connections, then real adapter and cross-platform tests. Do not expose test-only unsafe transports or identity fixtures through production RPC APIs.

### Agreed capacity qualification

For **each real JVM, Android, and iOS host**:

- 128 independently authenticated synthetic client instances.
- 10 calls/second/client: **1,280 calls/second aggregate**.
- 1 KiB encoded requests and 1 KiB encoded replies, using a trivial handler.
- 30-minute steady-state run with sustained completions, no RPC failures, and no growing backlog/resource leak.
- Report latency distributions, CPU, memory, threads, and connection health. **No latency pass/fail threshold**, as selected.
- Supplement load tests with physical cross-platform interoperability.

This does not certify 128 physical Wi-Fi associations. Device models, OS versions, network topology, and exact tested artifacts must be recorded.

Test 1 MiB requests/responses separately at bounded concurrency, including deliberate overload. Do not combine maximum payload with the full-rate target as an implied guarantee: that combination exceeds 20 Gbit/s before overhead.

Local builds, physical-device tests, packet captures, hostile-network tests, and shared CI execution all require later authorization/coordination. Existing external validation and audit gates remain unchanged.

## 8. Documentation and examples

Provide:

- Host/client quick start, explicit role selection, and shared typed procedure definitions.
- QR enrollment, administrator approval, durable trust storage, revocation, and identity rotation.
- Enterprise deployment guide: approved subnets/interfaces, fixed ports, VLAN/firewall rules, mDNS limitations, numeric fallback, and disconnected-Internet operation.
- Reliability guide with diagrams for response loss, unknown outcomes, cancellation, expiry, and restart.
- Clear application-idempotency guidance without claiming the module supplies transactional storage.
- Procedure/schema versioning and protocol compatibility documentation.
- Limits, backpressure, diagnostics, and resource-ownership reference.
- Android/iOS permission and background-execution guidance.
- KMP examples with role selection, typed business errors, notifications, and an unsafe operation whose automatic replay is visibly prevented.
- A JVM load harness and thin iOS shared-Kotlin façade for later authorized qualification.

Examples must not normalize plaintext, permissive trust, secret logging, or development-only identity storage as production configuration.

## 9. Decisions and risks for approval

### Decisions already selected

- Explicit organization-private subnets, including routed VLANs.
- One selected host.
- Live client-initiated QR pairing with host approval and live revocation.
- Lightweight, bounded host notifications in MVP.
- JVM, Android, and iOS host/client roles.
- 128-client qualification on each host platform.
- Thirty-minute throughput qualification using synthetic clients plus physical interoperability.
- 1 MiB maximum encoded request/response body, tested separately from peak call rate.

### Recommended defaults submitted with this plan

| Decision | Recommendation and trade-off |
|---|---|
| Ambiguous calls | Recover retained outcomes by default; do not automatically re-execute. Safer, but sometimes requires application reconciliation. |
| Restart/expiry | Return uncertainty instead of transparent replay. Stronger continuity requires application storage/idempotency outside MVP. |
| Retention/resources | Use the bounded defaults above. Result availability may be sacrificed under pressure without sacrificing retained non-reexecution records. |
| Mobile hosting | Foreground-first; explicit Android service integration only. Predictable lifecycle behavior instead of unsupported always-on promises. |
| LAN assurance | Enforce endpoint/path restrictions in the SDK and require managed routing/firewall controls for deployment assurance. |
| Capacity shortfall | Stop and review rather than weaken gates, raise limits blindly, or silently introduce a replacement transport. |

The main risks are security-sensitive admission changes, cross-platform LAN-policy enforcement, shared-I/O scalability, memory overhead at the selected workload, and integration conflicts with future main changes.

**Operating context and decisions are retained without adding repository files. Implementation remains unstarted. Approval is awaited before branch creation, editing, committing, or pushing; execution/build permissions remain separate.**
