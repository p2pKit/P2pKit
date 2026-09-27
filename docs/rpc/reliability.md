# RPC reliability and resource contract

This is the implemented source contract, **not a runtime qualification result**.
See [qualification](qualification.md) for required tests and current blockers.

## What success and failure mean

- A local TCP/session send does not prove remote receipt or handler completion.
- A received, valid success response means the registered handler returned
  success. It proves a business transaction committed only if the application
  defines its success reply that way.
- Application errors are typed `RpcReply.ApplicationError` values, not
  infrastructure exceptions. Infrastructure exceptions never serialize host
  exception messages or stack traces.
- Concurrent handlers/replies can complete out of order. The application owns
  business ordering and transactions.
- Coroutine cancellation remains `CancellationException`. A cancelled caller
  may have caused a remote side effect. Cancelling a request is not rollback.
- Timeout, transport failure, restart, result eviction and retention expiry can
  leave an outcome unknown. **There is no end-to-end exactly-once execution.**

`RpcFailure` reports kind, phase, logical request ID when allocated, execution
evidence and retry advice. `NotSent` and `RejectedBeforeExecution` are stronger
than `MayHaveExecuted`. `HandlerFinished` accompanies received terminal business
outcomes, including when local decoding subsequently fails. Never convert
uncertainty into an automatic fresh business request.

## One call, one deadline, one frozen identity

1. Client checks readiness and its outstanding-call bound, allocates a random
   128-bit logical ID, and freezes encoded request bytes.
2. Encoding, queue time, connection recovery, sending and responses consume one
   monotonic deadline: 10 seconds by default, at most 30 seconds.
3. An unsent queue ticket can be cancelled/expired without later transmission.
   Once writing starts, evidence conservatively becomes `MayHaveExecuted`.
4. Host validates the procedure, authenticated admission, current authorization,
   body and resource limits. It installs the deduplication record **before** any
   handler can start and reserves decoding/result-encoding allowance.
5. Host owns the handler independently of a particular incoming connection.
   It records a terminal outcome and may send it on a fresh authorized connection.
6. Client correlates the response and completes once. A small best-effort receipt
   permits prompt response-body reclamation; it is not a durability guarantee.

The host clamps the client's remaining-time allowance on first admission.
Duplicates cannot extend it. Network delay and unsynchronized clocks mean this
is not an exact wall-clock remote-stop guarantee. Queued cancellation/deadline
removes work before the handler; running cancellation is cooperative. A
non-cooperative handler retains its slot and leases until it actually exits.
Authorization waits also consume the initial admission budget and are capped
at five seconds per check. Result/status authorization has the same cap and
fails closed; it does not extend the client's overall call deadline. A
cooperative result-authorization timeout releases the execution slot while
retaining the outcome for a later authorized lookup, not another execution.

## Response loss and bounded recovery

```text
client                        host
  INVOKE(id, frozen bytes) ---> install record; execute handler
                          X--- response lost
  STATUS(id, digest) --------> look up the SAME record; recheck authorization
                         <--- running / retained reply / result unavailable
```

`RpcRetry.RecoverOnly(maxAttempts = 3)` is the default. Initial invocation plus
subsequent status/reinvocation attempts are capped at three. Backoff uses full
jitter, starting at 100 ms and capped at 2 seconds; bounded overload retry-after
information is honored inside the same deadline. Waiting for a reply uses the
remaining call budget, not a newly reset per-attempt timeout.

| Observation | Action |
| --- | --- |
| Ticket definitely not started | May attempt invocation within the same deadline/attempt count. |
| Explicit overload refusal before any ambiguous invocation | May attempt invocation; host installed no execution record. |
| Write started, reply missing | Recover with STATUS, not an unsafe invocation. |
| Existing record still executing | Observe it; never run a second concurrent handler for that record. |
| Retained terminal outcome | Return it after current authorization. |
| Tombstone without response bytes | `ResultUnavailable`; never re-execute from that tombstone. |
| No record during recovery | `UnknownOutcome` by default, even if the request might never have arrived. |
| Caller **and** descriptor opted into idempotency | A bounded reinvocation may use the same ID and frozen bytes if no record exists, within the same host incarnation/deadline. |
| Authentication, authorization, malformed protocol, incompatible version | Terminal; no automatic downgrade or retry. |
| New host incarnation | `HostRestarted`/uncertainty; no automatic replay, including idempotent calls. |

A later refusal cannot erase evidence of an earlier ambiguous attempt. Same ID
with a different procedure/version or request digest is a protocol violation.
Late/duplicate responses cannot complete a call twice; abusive response floods
are bounded and may terminate the connection.

Core's existing outgoing connection owner provides at most five reconnect
attempts in a 30-second recovery window, with bounded jitter and permanent
failure filtering. This restores a connection, not business delivery. New calls
while disconnected fail locally; there is no offline queue. Explicitly selecting
a different host never sends the previous host's calls, cancellation or receipts
to the replacement.

## Deduplication is bounded and volatile

Key: authenticated client fingerprint plus logical request ID, within one host
incarnation. Running records are never evicted to admit more calls.

- Completed records/tombstones live 60 seconds with no pressure eviction.
- At most 1,024 records per client and 131,072 per host; a full table refuses
  new work before execution.
- Response bodies live at most 30 seconds and share a 32 MiB cache. Receipt,
  cache pressure, or payload-budget pressure may reclaim bodies sooner, retaining
  the tombstone. Even a just-completed result might not remain recoverable.
- Host restart loses all records and changes the incarnation. The process does
  not persist handler jobs, results, request IDs or queues.
- Expired records no longer prevent a malicious/custom client from reusing an
  ID. Official calls end within 30 seconds and do not replay expired requests.

For durable idempotency, put an application operation key in the application
schema, then atomically commit that key, its result and the side effect inside
the application's own transaction. RPC does not supply that storage, choose the
business key, coordinate transactions, or make a non-idempotent handler safe.

## Default resource bounds

| Resource | Bound |
| --- | --- |
| Trusted connections | 128, plus 4 enrollment-only connections |
| Inbound handshakes | 16 globally; existing **2 per source** protection retained |
| Outstanding/accepted calls per client | 8 |
| Host handlers and pending queue | 128 running, 256 queued |
| Request, success or application-error body | 64 KiB per descriptor by default; explicit ceiling 1 MiB |
| Shared retained-payload policy | 64 MiB across participating core/RPC buffers |
| Cached response bodies | 32 MiB inside that shared budget |
| JSON structural preflight | depth 32, 131,072 value tokens, 128 keys/object; bounded keys/numbers |
| Notifications | 16 KiB body; 16 entries/128 KiB per peer, 1 MiB aggregate |
| Link priority queue | 32 entries/4 MiB per peer; aggregate payload budget still applies |

Limits may be lowered but not raised beyond the approved profile. Not every
combination of these maxima can be admitted simultaneously. Encoding/decoding
reserve scratch allowances before execution, so body limits alone do not
guarantee admission. Pressure can cause typed overload before execution, or
connection closure while an already-sent call remains uncertain.

Notifications include the active writer in their entry/byte limits. Priority
responses/control bypass queued notifications between complete messages, but
cannot preempt a message already being written. Client event consumers cannot
block the RPC response reader indefinitely; notification pressure drops events.

The byte budget is **not a heap/RSS ceiling**: object graphs, transient defensive
copies, application-held objects, native resources, thread stacks and socket
buffers require actual platform measurement. Host close requests cancellation
and observes connection cleanup in bounded batches, preserving each core
connection's retained deadline/result. It does not pretend a stuck application
handler has finished.
