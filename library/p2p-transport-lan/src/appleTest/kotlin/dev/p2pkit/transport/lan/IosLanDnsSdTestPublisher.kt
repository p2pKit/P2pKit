@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import kotlin.time.TimeSource
import kotlinx.cinterop.ByteVar
import kotlinx.cinterop.COpaquePointer
import kotlinx.cinterop.CPointer
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.StableRef
import kotlinx.cinterop.alloc
import kotlinx.cinterop.asStableRef
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.ptr
import kotlinx.cinterop.staticCFunction
import kotlinx.cinterop.value
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import platform.Foundation.NSLock
import platform.Network.nw_txt_record_access_bytes
import platform.Network.nw_txt_record_t
import platform.darwin.DNSServiceRef
import platform.darwin.DNSServiceRefDeallocate
import platform.darwin.DNSServiceRefVar
import platform.darwin.DNSServiceRegister
import platform.darwin.DNSServiceSetDispatchQueue
import platform.darwin.DNSServiceUpdateRecord
import platform.darwin.NXSwapHostShortToBig
import platform.darwin.dispatch_async
import platform.darwin.dispatch_queue_t
import platform.darwin.kDNSServiceFlagsAdd
import platform.darwin.kDNSServiceFlagsIncludeP2P
import platform.darwin.kDNSServiceFlagsNoAutoRename
import platform.darwin.kDNSServiceInterfaceIndexBLE
import platform.darwin.kDNSServiceInterfaceIndexInfra
import platform.darwin.kDNSServiceInterfaceIndexLocalOnly
import platform.darwin.kDNSServiceInterfaceIndexP2P
import platform.darwin.kDNSServiceInterfaceIndexUnicast

/** One real test advertisement; it does not attach an NW descriptor or supply receiver results. */
internal class IosLanDnsSdTestPublisher(
    private val queue: dispatch_queue_t,
    private val name: String,
    private val type: String,
    private val domain: String,
    private val port: UShort,
    private val checkListener: () -> Unit
) {
    enum class PublishOp { NONE, REGISTER, UPDATE }
    enum class Registration { NOT_STARTED, PENDING, READY, LOST, ERROR, CLOSED, UNAVAILABLE }

    data class Status(
        val publishOp: PublishOp = PublishOp.NONE,
        val publishCode: Int? = null,
        val registration: Registration = Registration.NOT_STARTED,
        val registerCode: Int? = null,
        val references: Int = 0,
        val contexts: Int = 0,
        val failure: Throwable? = null
    )

    data class RetirementResult(val complete: Boolean, val references: Int, val contexts: Int)

    private class Retirement {
        val started = TimeSource.Monotonic.markNow()
        val done = CompletableDeferred<Unit>()
        val result = MutableStateFlow<Boolean?>(null)
        val reportedIncomplete = MutableStateFlow(false)
        fun remainingMillis(): Long = (OWNERSHIP_TIMEOUT_MS - started.elapsedNow().inWholeMilliseconds).coerceAtLeast(0)
    }

    private val state = MutableStateFlow(Status())
    private val closing = MutableStateFlow(false)
    // Only orders submission against retirement. Never held during native calls, callbacks or awaits.
    private val submissionLock = NSLock()
    private var retirement: Retirement? = null

    // Native ownership is confined to the supplied serial queue, including failed/late starts.
    private var reference: DNSServiceRef? = null
    private var context: StableRef<IosLanDnsSdTestPublisher>? = null

    val status: Status get() = state.value

    suspend fun publish(record: nw_txt_record_t) {
        val started = TimeSource.Monotonic.markNow()
        withTimeout(OWNERSHIP_TIMEOUT_MS) {
            suspendCancellableCoroutine<Unit> { pending ->
                pending.invokeOnCancellation { requestRetirement() }
                var submissionFailure: Throwable? = null
                submissionLock.lock()
                try {
                    check(!closing.value) { "DNS-SD test publisher is closing" }
                    dispatch_async(queue) {
                        fun canContinue(): Boolean = pending.isActive && !closing.value &&
                            started.elapsedNow().inWholeMilliseconds < OWNERSHIP_TIMEOUT_MS
                        try {
                            check(canContinue()) { "DNS-SD publication handoff expired" }
                            mutateOnQueue(record, ::canContinue)
                            check(canContinue()) { "DNS-SD publication completed after its deadline or close" }
                            pending.resumeWith(Result.success(Unit))
                        } catch (failure: Throwable) {
                            failOnQueue(failure)
                            if (pending.isActive) pending.resumeWith(Result.failure(failure))
                        }
                    }
                } catch (failure: Throwable) {
                    submissionFailure = failure
                } finally {
                    submissionLock.unlock()
                }
                // Resumption can run an unconfined caller (and its close) immediately.
                submissionFailure?.let {
                    requestRetirement()
                    pending.resumeWith(Result.failure(it))
                }
            }
        }
    }

    /** The caller places this actual Add acknowledgment inside its original discovery deadline. */
    suspend fun awaitRegistered() {
        try {
            state.first {
                it.failure?.let { failure -> throw failure }
                check(!closing.value) { "DNS-SD registration closed before acknowledgment" }
                it.registration == Registration.READY
            }
        } catch (failure: CancellationException) {
            requestRetirement()
            throw failure
        }
    }

    /** Publisher failure can abort an unchanged receiver predicate, never satisfy it. */
    suspend fun <T> whileAvailable(wait: suspend CoroutineScope.() -> T): T = coroutineScope {
        state.value.failure?.let { throw it }
        val watcher = launch(start = CoroutineStart.UNDISPATCHED) {
            val failed = state.first { it.failure != null }
            throw checkNotNull(failed.failure)
        }
        try {
            wait().also { state.value.failure?.let { failure -> throw failure } }
        } finally {
            watcher.cancelAndJoin()
        }
    }

    /** This same-process lifecycle fixture uses real loopback, not a production advertising policy. */
    private fun validatedLoopbackInterfaceIndex(): UInt {
        val snapshot = collectAppleInterfaceAddressSnapshot()
        check(snapshot.enumerationErrorCode == null) { "Could not enumerate the test loopback interface" }
        val indices = snapshot.candidates.filter {
            it.interfaceName == "lo0" && it.ipVersion == 4 && it.addressBytes.size == 4 &&
                (it.addressBytes[0].toInt() and 0xFF) == 127 &&
                it.interfaceIsUp && it.interfaceIsRunning && it.interfaceIsLoopback && it.interfaceSupportsMulticast
        }.map { it.interfaceIndex }.distinct()
        val reserved = setOf(
            0u, kDNSServiceInterfaceIndexLocalOnly, kDNSServiceInterfaceIndexP2P,
            kDNSServiceInterfaceIndexUnicast, kDNSServiceInterfaceIndexBLE, kDNSServiceInterfaceIndexInfra
        )
        check(indices.size == 1 && indices.none { it in reserved }) { "Invalid test loopback interface" }
        return indices.single()
    }

    private fun mutateOnQueue(record: nw_txt_record_t, canContinue: () -> Boolean) {
        state.value.failure?.let { throw it }
        checkListener()
        val registering = state.value.registration == Registration.NOT_STARTED
        val registrationInterface = if (registering) {
            check(port != 0.toUShort()) { "DNS-SD requires the ready listener port" }
            val index = validatedLoopbackInterfaceIndex()
            check(canContinue()) { "DNS-SD publication handoff expired" }
            context = StableRef.create(this)
            state.update { it.copy(registration = Registration.PENDING, contexts = 1) }
            index
        } else {
            check(state.value.registration == Registration.READY && reference != null) {
                "DNS-SD update requires the original ready registration"
            }
            null
        }
        var attempted = false
        var code: Int? = null
        var accessFailure: Throwable? = null
        val accessed = try {
            memScoped {
                val output = alloc<DNSServiceRefVar>()
                output.value = null
                val callbackContext = context?.asCPointer()
                val networkPort = NXSwapHostShortToBig(port)
                nw_txt_record_access_bytes(record) { bytes, length ->
                    if (bytes == null || length == 0uL || length > 65_535uL) {
                        false
                    } else {
                        try {
                            if (!canContinue()) {
                                false
                            } else {
                                attempted = true
                                val returned = if (registering) {
                                    DNSServiceRegister(
                                        output.ptr, kDNSServiceFlagsNoAutoRename or kDNSServiceFlagsIncludeP2P,
                                        checkNotNull(registrationInterface), name, type, domain, null,
                                        networkPort, length.toUShort(), bytes,
                                        staticCFunction(::iosLanTestRegisterReply), callbackContext
                                    )
                                } else {
                                    DNSServiceUpdateRecord(reference, null, 0u, length.toUShort(), bytes, 0u)
                                }
                                code = returned
                                // Error output is undefined. Transfer a successful ref before reporting/scheduling.
                                if (registering && returned == 0) reference = output.value
                                true
                            }
                        } catch (failure: Throwable) {
                            accessFailure = failure
                            false
                        }
                    }
                }
            }
        } finally {
            state.update {
                it.copy(
                    publishOp = when {
                        !attempted -> it.publishOp
                        registering -> PublishOp.REGISTER
                        else -> PublishOp.UPDATE
                    },
                    publishCode = if (attempted) code else it.publishCode,
                    references = if (reference == null) 0 else 1
                )
            }
        }
        accessFailure?.let { throw it }
        check(accessed) { "Could not borrow the complete publisher TXT record before the deadline" }
        check(code == 0) { "DNS-SD publication failed: $code" }
        check(canContinue()) { "DNS-SD publication returned after its deadline or close" }
        if (registering) {
            val ref = checkNotNull(reference) { "DNS-SD registration succeeded without a reference" }
            val scheduled = DNSServiceSetDispatchQueue(ref, queue)
            check(scheduled == 0) { "DNS-SD registration scheduling failed: $scheduled" }
        }
    }

    internal fun receive(
        error: Int,
        fields: () -> Boolean
    ) {
        state.update { it.copy(registerCode = error) }
        // All other native callback fields are undefined on error.
        if (error != 0) {
            failOnQueue(IllegalStateException("DNS-SD registration callback failed: $error"), Registration.ERROR)
        } else if (!closing.value && fields()) {
            state.update { it.copy(registration = Registration.READY) }
        }
    }

    internal fun acceptIdentity(
        ref: DNSServiceRef?, flags: UInt, actualName: CPointer<ByteVar>?,
        actualType: CPointer<ByteVar>?, actualDomain: CPointer<ByteVar>?
    ): Boolean {
        if ((flags and kDNSServiceFlagsAdd) == 0u) {
            failOnQueue(IllegalStateException("DNS-SD registration was withdrawn"), Registration.LOST)
            return false
        }
        check(ref != null && ref == reference) { "DNS-SD registration reference changed" }
        check(copyLanDnsString(actualName, 64) == name &&
            copyLanDnsString(actualType)?.removeSuffix(".") == type.removeSuffix(".") &&
            copyLanDnsString(actualDomain)?.removeSuffix(".") == domain.removeSuffix(".")
        ) { "DNS-SD registration identity changed" }
        return true
    }

    internal fun callbackUnavailable() {
        failOnQueue(IllegalStateException("DNS-SD registration callback unavailable"), Registration.UNAVAILABLE)
    }

    private fun failOnQueue(failure: Throwable, registration: Registration = Registration.ERROR) {
        state.update { it.copy(registration = registration, failure = it.failure ?: failure) }
        requestRetirement()
    }

    private fun requestRetirement(): Retirement {
        closing.value = true
        submissionLock.lock()
        try {
            retirement?.let { return it }
            val requested = Retirement()
            retirement = requested
            // The submission fence covers queued starts too, not just the current reference count.
            dispatch_async(queue) { retireOnQueue(requested) }
            return requested
        } finally {
            submissionLock.unlock()
        }
    }

    private fun retireOnQueue(requested: Retirement) {
        try {
            reference?.let { DNSServiceRefDeallocate(it) }
            reference = null
            state.update { it.copy(references = 0) }
            // Explicit deallocation has no RegisterReply cancellation callback. Drain a later queue
            // turn before disposing its StableRef, never from inside the native callback stack.
            dispatch_async(queue) {
                try {
                    context?.dispose()
                    context = null
                    state.update { it.copy(registration = Registration.CLOSED, contexts = 0) }
                    requested.result.value = requested.remainingMillis() > 0
                } catch (failure: Throwable) {
                    state.update { it.copy(failure = it.failure ?: failure) }
                    requested.result.value = false
                } finally {
                    requested.done.complete(Unit)
                }
            }
        } catch (failure: Throwable) {
            // Keep any ownership that could still be reachable by native code; never retry deallocation.
            state.update { it.copy(failure = it.failure ?: failure) }
            requested.result.value = false
            requested.done.complete(Unit)
        }
    }

    suspend fun close(): RetirementResult = withContext(NonCancellable) {
        val requested = requestRetirement()
        val complete = if (requested.reportedIncomplete.value) false else requested.result.value ?: (
            withTimeoutOrNull(requested.remainingMillis()) {
                requested.done.await()
                requested.result.value
            } ?: false
        )
        if (!complete) requested.reportedIncomplete.value = true
        val final = state.value
        RetirementResult(complete, final.references, final.contexts)
    }

    private companion object {
        const val OWNERSHIP_TIMEOUT_MS: Long = 5_000
    }
}

private fun iosLanTestRegisterReply(
    ref: DNSServiceRef?, flags: UInt, error: Int, name: CPointer<ByteVar>?,
    type: CPointer<ByteVar>?, domain: CPointer<ByteVar>?, context: COpaquePointer?
) {
    var target: IosLanDnsSdTestPublisher? = null
    try {
        val owner = context?.asStableRef<IosLanDnsSdTestPublisher>()?.get() ?: return
        target = owner
        owner.receive(error) { owner.acceptIdentity(ref, flags, name, type, domain) }
    } catch (_: Throwable) {
        try { target?.callbackUnavailable() } catch (_: Throwable) { }
    }
}
