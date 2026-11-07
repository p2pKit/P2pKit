# Accept an RPC result before Receipt

Available in the **0.8.0-rc12 source candidate** for
[#543](https://github.com/p2pKit/P2pKit/issues/543). This candidate is not published.
The existing `call`, `callWithDetails` and `callWithObservation` APIs still attempt
automatic Receipt after decoding. Use `callWithAcceptance` when Receipt must
mean that your application has validated and durably stored the terminal result.

## Usage

```kotlin
val result = client.callWithAcceptance(
    procedure = getSale,
    request = query,
    timeout = 10.seconds,
    retry = RpcRetry.RecoverOnly(),
) { acceptance ->
    val details = acceptance.details
    // Reject an unexpected sale/account, invalid signature, stale business revision, etc.
    validateSaleReply(query, details.reply)

    // Application-owned suspend function. Return ONLY after the durable transaction commits.
    // Store the business idempotency key too, so recovery survives a new RPC request ID.
    journal.commitAndSync(
        host = acceptance.hostFingerprint.value,
        incarnation = acceptance.hostIncarnation,
        requestId = details.requestId.value,
        procedure = acceptance.procedureName,
        version = acceptance.procedureVersion,
        reply = details.reply,
    )
}
// Validation and local durable acceptance succeeded. Receipt delivery is best effort.
showAcceptedSale(result.reply)
```

`getSale`, `query`, `validateSaleReply`, `journal.commitAndSync` and
`showAcceptedSale` belong to your application. P2pKit does not supply a journal,
database transaction or `fsync`. Configure the store's crash/power-loss durability
policy; returning after an in-memory enqueue or launching an unawaited coroutine
does not satisfy the acceptance contract. Avoid logging the context or its data.

## Ordering and failures

1. RPC authenticates and receives a terminal response, checks request/procedure/
   Host association and decodes it with the existing payload bounds.
2. The callback receives immutable association metadata plus the decoded reply.
   It runs once in the caller's coroutine, inside the original total call timeout
   (1 ms–30 seconds, default 10 seconds). It retains the call's existing slot.
3. Return normally after validation and durable persistence to permit only that
   request's matching Receipt. Throw to reject it. A `Success` and a typed
   `ApplicationError` both require acceptance; an application may durably accept
   a business rejection. Infrastructure/wire failures never enter the callback.
4. Failed validation, persistence, decoding or cancellation before callback
   completion sends no Receipt. RPC does not retry the callback or reinvoke the
   handler because acceptance failed, even with `RpcRetry.Idempotent`. Ordinary
   application exceptions propagate; RPC failures retain their execution evidence.
5. Receipt queueing is best effort, bounded to one second within the original
   timeout. Cancellation removes an unstarted Receipt. The writer checks the
   original connection generation, readiness and cancellation again before start.
   A disconnected/replaced connection cannot inherit that Receipt. The Host still
   applies current trust, original application scope, physical association and
   Receipt authorization. An accepted local result does not grant remote authority.

`RpcCallDetails.elapsedMillis` returned by the call includes acceptance and
Receipt queueing. The callback's snapshot measures elapsed time up to decoding.
An optional `RpcCallObservation` uses the existing stages; while acceptance runs,
it remains nonterminal. Completion counters advance only after the call returns.

## Recovery limits

- Retries *before* a terminal reply reuse the original request ID and existing
  conservative recovery/idempotency policy. They never extend the call deadline.
- A lost/refused Receipt leaves the Host's retained result subject to its normal
  limits. There is no Receipt confirmation in this protocol; a successful local
  return proves acceptance, not remote cache deletion. There is no retry owner
  or additional networking loop for acceptance.
- The Host retains bodies for at most 30 seconds and may evict them earlier for
  capacity. An accepted matching Receipt drops only that cached body. The
  non-reinvocable record/tombstone remains until its existing 60-second expiry.
  Receipt loss and duplicate delivery do not permit re-execution during that
  record lifetime. Existing explicitly idempotent recovery remains opt-in.
- Acceptance failure does not extend retention, keep an infinite cache, expose
  an acknowledge token or add a public resume-by-ID API. Calling again creates
  a new logical request ID. Use application idempotency keys and an authorized
  business-result lookup for durable cross-process recovery; do not blindly retry
  a non-idempotent operation after an unknown or locally rejected result.
- Cancellation after a durable commit cannot roll it back and may race a Receipt
  already started. A process crash between commit and Receipt is likewise
  unavoidable. Make journal writes idempotent. A callback must not swallow
  cancellation, exceed the deadline with non-cooperative work, or bypass current
  application authorization when persisting or presenting data.

This opt-in changes no wire format, encryption, admission limit, default capacity
profile, Host disclosure policy or Apple deployment target. Legacy automatic
Receipt APIs retain their existing signatures and behavior.
