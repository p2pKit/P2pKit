package dev.p2pkit.sample.rpc.profile

import java.io.IOException
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/**
 * Managed contract implementation only. No production selector or native loader exists.
 * One active operation, no queue; close seals admission and joins the actual native return before retiring handles.
 * Native OS hangs still require the separately reviewed terminal watchdog, not an invented coroutine deadline.
 */
internal class WindowsProfileFiles private constructor(
    private val native: WindowsProfileNativeApi,
    private val handleAcquisitionObservation: HandleAcquisitionObservation?,
    private val beforeHandleRetirement: (() -> Unit)?,
) :
    ProtectedProfileSession {
    /**
     * Failed admission with uncertain native retirement. Retain this sealed session for the terminal owner;
     * dropping the native owner or retrying close is not evidence that its resources retired. Native cleanup
     * can remain uncertain even when admission failed before publishing a root handle to this session.
     */
    class AcquisitionFailure internal constructor(
        val retainedSession: WindowsProfileFiles,
    ) : IOException("Windows profile admission failed with retained cleanup ownership") {
        lateinit var cleanupFailure: Throwable
            private set

        internal fun attach(cause: Throwable, cleanup: Throwable): AcquisitionFailure {
            initCause(cause)
            cleanupFailure = cleanup
            return this
        }
    }

    /** A failed cleanup controller retains this sealed session and its unretired ledger, without retry. */
    class RetirementFailure internal constructor(val retainedSession: WindowsProfileFiles) :
        IOException("Windows profile retirement orchestration failed with ownership retained") {
        var priorFailure: Throwable? = null
            private set

        internal fun attach(cause: Throwable, prior: Throwable?): RetirementFailure {
            initCause(cause)
            priorFailure = prior
            return this
        }
    }

    /** Inert fault observation only; neither callback creates native authority or changes admission. */
    interface HandleAcquisitionObservation {
        fun beforeCarrierAllocation()
        fun afterPrimitiveRetention() = Unit
        fun afterAcquisition()
    }

    private enum class State { Opening, Open, Closing, Closed, Failed }
    private class Handle {
        var value = 0L
        var registered = false
        var failure: Throwable? = null
        var released = false
    }
    private val monitor = ReentrantLock()
    private val changed = monitor.newCondition()
    private var state = State.Opening
    private var busy = false
    private var operationFailed = false
    private var closeFailure: Throwable? = null
    private var nativeCleanupFailure: Throwable? = null
    // Allocate the bounded ledger and failure carrier before storage admission. Retirement must not
    // allocate a snapshot/iterator after sealing admission, especially on a native reporting-Error path.
    private val handles = arrayOfNulls<Handle>(32)
    private var handleCount = 0
    private val retirementFailure = RetirementFailure(this)
    internal val retirementStarted: Boolean get() = monitor.withLock {
        state in setOf(State.Closing, State.Closed, State.Failed)
    }
    // Published handles only. Zero does not settle cleanup of unpublished native resources.
    internal val retainedHandleCount: Int get() = monitor.withLock { handles.count { it?.registered == true } }
    private lateinit var openedRoot: Directory
    override val root: ProtectedProfileDirectory get() = monitor.withLock {
        check(state == State.Open)
        openedRoot
    }

    /**
     * Called before key/proof admission with the profile lease held. Interrupted candidates have no
     * authenticated destination or ordering information: a valid old record cannot settle their outcome.
     * Refuse unknown inventory without reading payloads, promoting candidates, deleting or repairing files.
     * Sync the admitted current identity namespace under both original leases before consuming any header/key.
     * This acknowledgment cannot establish whether an earlier unacknowledged operation succeeded.
     * This is conservative startup admission, not proof of crash recovery or native Windows durability.
     */
    internal fun requireSettledProfileInventory() {
        val profile = root
        val members = profile.names()
        check("profile.lock" in members && members.all { it in profileMembers }) {
            "Incomplete Windows profile: preserve its files for recovery; no identity reset was attempted"
        }
        for (name in members - "identity") profile.fileIdentity(name)
        if ("identity" !in members) return
        val identity = profile.child("identity")
        // Every initialized identity has this lock. Do not create a missing lock while inspecting an
        // existing directory: interrupted first initialization requires explicit recovery, not adoption.
        check(identity.exists("vault.lock")) { "Incomplete Windows profile: identity lock is missing" }
        identity.fileIdentity("vault.lock")
        // The native exclusive lease uses shareAccess=0. Read before acquiring it, never reopen that
        // owned lock for data; lock admission independently rechecks emptiness through its original handle.
        check(identity.read("vault.lock", 0).isEmpty())
        identity.lock("vault.lock", nonBlocking = true).use {
            val records = identity.names()
            check("vault.lock" in records && records.all { it == "vault.lock" || recordName.matches(it) }) {
                "Incomplete Windows profile: preserve its records for recovery; no identity reset was attempted"
            }
            records.forEach(identity::fileIdentity)
            identity.verifyIdentity()
            profile.verifyIdentity()
            // A completed rename/delete can leave no pending name despite an unacknowledged prior sync.
            // Acknowledge only the visible canonical namespace, keeping the original directory and leases.
            identity.sync()
            identity.verifyIdentity()
            profile.verifyIdentity()
        }
    }

    private inline fun allocate(open: (Handle) -> Unit): Handle {
        val handle = monitor.withLock {
            check(handleCount < handles.size) { "Profile native-handle bound reached" }
            handleAcquisitionObservation?.beforeCarrierAllocation()
            // Reserve a fresh carrier and ledger slot BEFORE native effects. Never recycle an old
            // Handle object: previously returned directories/leases may still refer to that lifetime.
            Handle().also { handles[handleCount++] = it }
        }
        try {
            // Each inlined callback stores the native primitive directly in this pre-reserved carrier.
            // Returning Long through a lambda can box even after inlining, before ownership is retained.
            open(handle)
            handleAcquisitionObservation?.afterPrimitiveRetention()
        } catch (failure: Throwable) {
            monitor.withLock {
                if (handle.value == 0L && handleCount > 0 && handles[handleCount - 1] === handle) {
                    handles[--handleCount] = null
                } else {
                    // A post-store reporting failure leaves an unvalidated raw token, not a second
                    // close authority. Preserve both the provisional carrier and original failure.
                    handle.failure = failure
                }
            }
            throw failure // Unpublished native resources remain the original provider's responsibility.
        }
        monitor.withLock {
            val raw = handle.value
            var duplicate = false
            var index = 0
            while (index < handleCount - 1) {
                val existing = handles[index++]
                if (existing != null && existing.value == raw) duplicate = true
            }
            if (raw <= 0 || duplicate) {
                // An invalid return never creates a second close authority for an existing token.
                handles[--handleCount] = null
                error("Invalid or reused profile handle")
            }
            handle.registered = true
        }
        // Once this reporting boundary runs, the exact returned token is already ledger-owned.
        handleAcquisitionObservation?.afterAcquisition()
        return handle
    }

    private fun rememberNativeUncertainty(failure: Throwable) = monitor.withLock {
        if (nativeCleanupFailure == null && (failure is Error ||
                (failure is WindowsProfileCustodyException &&
                    (failure.failure == WindowsProfileCustodyFailure.CleanupUnknown ||
                        failure.failure == WindowsProfileCustodyFailure.Unknown)))) {
            // JNI reporting can preserve OOM/linkage Errors instead of its intended CleanupUnknown code.
            // Such a failure after storage entry cannot prove retirement of unpublished native resources.
            // Keep the exact provider and throwable; never translate it or invent a handle/drain retry.
            nativeCleanupFailure = failure
        }
    }

    private fun <T> operation(handle: Handle, cleanupRead: Boolean = false, block: () -> T): T {
        monitor.withLock {
            check(state == State.Open && (!operationFailed || cleanupRead) && !busy &&
                !handle.released && handle.failure == null) {
                "Profile operation is unavailable; no work queued"
            }
            busy = true
        }
        try {
            val result = block()
            monitor.withLock {
                if (state != State.Open) {
                    if (result is ByteArray) result.fill(0)
                    error("Profile retired before native return")
                }
            }
            return result
        } catch (failure: Throwable) {
            rememberNativeUncertainty(failure)
            monitor.withLock { operationFailed = true }
            throw failure
        } finally {
            monitor.withLock { busy = false; changed.signalAll() }
        }
    }

    private fun closeHandle(handle: Handle) {
        if (handle.released) return
        handle.failure?.let { throw it }
        try {
            // A returned token retained before failed admission is not yet independent close authority.
            check(handle.registered) { "Profile handle admission remained uncertain" }
            native.close(handle.value)
            monitor.withLock {
                val index = handles.indexOfFirst { it === handle }
                check(index in 0 until handleCount)
                for (next in index + 1 until handleCount) handles[next - 1] = handles[next]
                handles[--handleCount] = null
                handle.released = true
            }
        }
        catch (failure: Throwable) {
            monitor.withLock {
                handle.failure = failure
                // An uncertain lease release poisons the session, not merely this handle's next close.
                operationFailed = true
            }
            throw failure
        }
    }

    override fun close() {
        var interrupted: InterruptedException? = null
        var ownsRetirement = false
        var retirementPublished = false
        var failure: Throwable? = null
        fun rememberInterrupt(caught: InterruptedException) {
            // Native ownership can outlive repeated interruptions; retain only one interruption diagnostic.
            if (interrupted == null) interrupted = caught
        }
        fun observeInterrupt() {
            if (Thread.interrupted() && interrupted == null)
                rememberInterrupt(InterruptedException("Profile close interrupted"))
        }
        fun waitForOwner() {
            try { changed.await() } catch (caught: InterruptedException) { rememberInterrupt(caught) }
            finally {
                // Condition.await may return normally and re-interrupt when a signal wins the interruption race.
                observeInterrupt()
            }
        }
        try {
            monitor.withLock {
                // Clear only to finish actual ownership cleanup; restore the caller's interrupt in finally.
                observeInterrupt()
                while (state == State.Closing) waitForOwner()
                observeInterrupt()
                if (state == State.Closed || state == State.Failed) {
                    val failure = closeFailure ?: interrupted
                    failure?.let { throw it }
                    return
                }
                state = State.Closing
                ownsRetirement = true
                while (busy) waitForOwner()
                observeInterrupt()
            }
            failure = monitor.withLock { nativeCleanupFailure }
            fun retain(caught: Throwable?) {
                if (caught == null) return
                if (failure == null) failure = caught
                // Error paths must not allocate a suppressed array. A failed known handle still retains
                // its exact throwable in Handle.failure, independently of this aggregate close result.
                else if (failure !== caught && failure !is Error && caught !is Error &&
                    failure.suppressed.none { it === caught }) failure.addSuppressed(caught)
            }
            retain(interrupted)
            // Late native allocations registered before busy cleared; never free a handle while its owner runs.
            // Admission is sealed and busy has joined the actual native return. Descending indices
            // remain valid as successful retirement compacts only entries at/above the removed index.
            var index = monitor.withLock { handleCount } - 1
            while (index >= 0) {
                // Inert validation fault only; no production factory or native authority is introduced.
                beforeHandleRetirement?.invoke()
                val handle = monitor.withLock { checkNotNull(handles[index]) }
                try { closeHandle(handle) } catch (caught: Throwable) {
                    if (caught is InterruptedException) rememberInterrupt(caught)
                    retain(caught)
                }
                finally { observeInterrupt(); retain(interrupted) }
                index--
            }
            monitor.withLock {
                // Terminal outcome linearizes at this final observation, not at a future interrupt after return.
                observeInterrupt()
                retain(interrupted)
                closeFailure = failure
                state = if (failure == null) State.Closed else State.Failed
                changed.signalAll()
                retirementPublished = true
            }
            failure?.let { throw it }
        } catch (caught: Throwable) {
            if (!ownsRetirement || retirementPublished) throw caught
            // Controller/reporting failure is not native retirement. Keep the original owner/cause
            // and prior diagnostic without suppression allocation; never strand waiters in Closing.
            // This handles reported errors, not a promise of recovery from arbitrary JVM exhaustion.
            val retained = retirementFailure.attach(caught, failure)
            monitor.withLock {
                closeFailure = retained
                state = State.Failed
                changed.signalAll()
            }
            throw retained
        } finally {
            interrupted?.let { Thread.currentThread().interrupt() }
        }
    }

    private inner class Directory(private val handle: Handle, private val identity: WindowsProfileIdentity) :
        ProtectedProfileDirectory {
        private val children = linkedMapOf<String, Directory>()
        override val mutexIdentity: Any = identity
        private fun verify() {
            check(WindowsProfileIdentity.decode(native.directoryIdentity(handle.value), true) == identity)
        }
        private fun memberIdentity(raw: LongArray, directory: Boolean): WindowsProfileIdentity =
            WindowsProfileIdentity.decode(raw, directory).also {
                check(it.volume == identity.volume) { "Profile member volume differs from its pinned parent" }
            }
        override fun verifyIdentity(): Any = operation(handle, cleanupRead = true) { verify(); identity }
        override fun fileIdentity(name: String): Any = operation(handle) {
            verify(); memberIdentity(native.fileIdentity(handle.value, profileComponent(name)), false)
        }
        override fun exists(name: String): Boolean = operation(handle) {
            verify(); native.exists(handle.value, profileComponent(name))
        }
        override fun names(): Set<String> = operation(handle) {
            verify()
            val names = native.names(handle.value)
            check(names.size <= 1024 && names.all { it.length <= 96 } && names.toSet().size == names.size)
            names.forEach(::profileComponent)
            names.toSet()
        }
        override fun child(name: String, create: Boolean): ProtectedProfileDirectory = operation(handle) {
            verify()
            val component = profileComponent(name)
            children[component]?.also { check(!create); it.verify() } ?: run {
                val child = allocate { acquired -> acquired.value = native.child(handle.value, component, create) }
                // An invalid child remains owned for session cleanup, but must never enter the directory cache.
                Directory(child, memberIdentity(native.directoryIdentity(child.value), true))
                    .also { children[component] = it }
            }
        }
        override fun read(name: String, maximum: Int): ByteArray {
            require(maximum in 0..262_144)
            return operation(handle) {
                verify()
                native.read(handle.value, profileComponent(name), maximum).also {
                    if (it.size > maximum) { it.fill(0); error("Native profile read exceeded its bound") }
                }
            }
        }
        override fun write(name: String, bytes: ByteArray, replace: Boolean) {
            require(bytes.size <= 262_144)
            operation(handle) {
                verify()
                val component = profileComponent(name)
                // Rejected callers must not allocate payload copies outside the single admitted owner.
                val copy = bytes.copyOf()
                try { native.write(handle.value, component, copy, replace) }
                finally { copy.fill(0) }
            }
        }
        override fun lock(name: String, nonBlocking: Boolean): ProtectedProfileLease = operation(handle) {
            verify()
            val locked = allocate { acquired ->
                acquired.value = native.lock(handle.value, profileComponent(name), nonBlocking)
            }
            object : ProtectedProfileLease {
                override fun close() {
                    // Close is cleanup, still allowed after an ordinary operation has poisoned admission.
                    monitor.withLock {
                        if (locked.released) return
                        locked.failure?.let { throw it }
                        check(state == State.Open && !busy) { "Profile retirement owns this lock" }
                        busy = true
                    }
                    try { closeHandle(locked) }
                    finally { monitor.withLock { busy = false; changed.signalAll() } }
                }
            }
        }
        override fun delete(name: String, expectedIdentity: Any?): Boolean = operation(handle) {
            verify()
            val component = profileComponent(name)
            val expected = if (expectedIdentity != null) {
                check(expectedIdentity is WindowsProfileIdentity) { "Invalid expected profile file identity" }
                memberIdentity(expectedIdentity.encoded(), false)
            } else {
                if (!native.exists(handle.value, component)) return@operation false
                memberIdentity(native.fileIdentity(handle.value, component), false)
            }
            native.delete(handle.value, component, expected.encoded())
        }
        override fun sync() = operation(handle) { verify(); native.sync(handle.value) }
        override fun deleteIfEmpty() = operation(handle) { verify(); native.deleteIfEmpty(handle.value) }
    }

    companion object {
        private val profileMembers = setOf("profile.lock", "profile.header", "identity")
        private val recordName = Regex("[0-9a-f]{64}\\.aesgcm")

        /** Test/qualification seam only. No property, UI or platform path can instantiate a production backend. */
        fun openForValidation(
            native: WindowsProfileNativeApi,
            handleAcquisitionObservation: HandleAcquisitionObservation? = null,
            beforeHandleRetirement: (() -> Unit)? = null,
        ): WindowsProfileFiles {
            val session = WindowsProfileFiles(native, handleAcquisitionObservation, beforeHandleRetirement)
            // Allocate the owner carrier before native effects, not while reporting a possible native/JNI OOM.
            // This preserves ownership after a reported Error; it does not promise recovery from VM exhaustion.
            val retained = AcquisitionFailure(session)
            var storageAdmissionStarted = false
            try {
                check(native.abi() == 1 && native.capabilities() == 0x7fL) { "Incomplete native profile contract" }
                val root = session.allocate { acquired ->
                    storageAdmissionStarted = true
                    acquired.value = native.openRoot()
                }
                session.openedRoot = session.Directory(root,
                    WindowsProfileIdentity.decode(native.directoryIdentity(root.value), true))
                session.state = State.Open
                return session
            } catch (failure: Throwable) {
                // ABI/introspection is side-effect-free and cannot establish storage ownership.
                if (storageAdmissionStarted) session.rememberNativeUncertainty(failure)
                try { session.close() } catch (cleanup: Throwable) {
                    // No iterator/count allocation on a reporting-Error path before transferring its owner.
                    val ownsUncertainResources = session.monitor.withLock {
                        session.nativeCleanupFailure != null || session.handleCount != 0
                    }
                    if (ownsUncertainResources) {
                        retained.attach(failure, cleanup)
                        if (cleanup !== failure && failure !is Error && cleanup !is Error)
                            retained.addSuppressed(cleanup)
                        throw retained
                    }
                    if (cleanup !== failure && failure !is Error && cleanup !is Error) failure.addSuppressed(cleanup)
                }
                throw failure
            }
        }
    }
}
