package dev.p2pkit.sample.rpc.profile

import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/**
 * Managed contract implementation only. No production selector or native loader exists.
 * One active operation, no queue; close seals admission and joins the actual native return before retiring handles.
 * Native OS hangs still require the separately reviewed terminal watchdog, not an invented coroutine deadline.
 */
internal class WindowsProfileFiles private constructor(private val native: WindowsProfileNativeApi) :
    ProtectedProfileSession {
    private enum class State { Opening, Open, Closing, Closed, Failed }
    private class Handle(val value: Long) { var failure: Throwable? = null; var released = false }
    private val monitor = ReentrantLock()
    private val changed = monitor.newCondition()
    private var state = State.Opening
    private var busy = false
    private var operationFailed = false
    private var closeFailure: Throwable? = null
    private val handles = linkedMapOf<Long, Handle>()
    internal val retirementStarted: Boolean get() = monitor.withLock {
        state in setOf(State.Closing, State.Closed, State.Failed)
    }
    internal val retainedHandleCount: Int get() = monitor.withLock { handles.values.count { !it.released } }
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

    private fun own(raw: Long): Handle = monitor.withLock {
        check(raw > 0 && raw !in handles) { "Invalid or reused profile handle" }
        Handle(raw).also { handles[raw] = it }
    }

    private fun allocate(open: () -> Long): Handle {
        monitor.withLock { check(handles.size < 32) { "Profile native-handle bound reached" } }
        return own(open()) // Allocation errors must not return an unowned native resource through the ABI.
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
            native.close(handle.value)
            monitor.withLock {
                check(handles.remove(handle.value) === handle)
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
                while (busy) waitForOwner()
                observeInterrupt()
            }
            var failure: Throwable? = interrupted
            fun retain(caught: Throwable?) {
                if (caught == null) return
                if (failure == null) failure = caught
                else if (failure !== caught && failure.suppressed.none { it === caught }) failure.addSuppressed(caught)
            }
            // Late native allocations registered before busy cleared; never free a handle while its owner runs.
            for (handle in monitor.withLock { handles.values.toList().asReversed() }) {
                try { closeHandle(handle) } catch (caught: Throwable) {
                    if (caught is InterruptedException) rememberInterrupt(caught)
                    retain(caught)
                }
                finally { observeInterrupt(); retain(interrupted) }
            }
            monitor.withLock {
                // Terminal outcome linearizes at this final observation, not at a future interrupt after return.
                observeInterrupt()
                retain(interrupted)
                closeFailure = failure
                state = if (failure == null) State.Closed else State.Failed
                changed.signalAll()
            }
            failure?.let { throw it }
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
                val child = allocate { native.child(handle.value, component, create) }
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
            val locked = allocate { native.lock(handle.value, profileComponent(name), nonBlocking) }
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
        fun openForValidation(native: WindowsProfileNativeApi): WindowsProfileFiles {
            val session = WindowsProfileFiles(native)
            try {
                check(native.abi() == 1 && native.capabilities() == 0x7fL) { "Incomplete native profile contract" }
                val root = session.own(native.openRoot())
                session.openedRoot = session.Directory(root,
                    WindowsProfileIdentity.decode(native.directoryIdentity(root.value), true))
                session.state = State.Open
                return session
            } catch (failure: Throwable) {
                try { session.close() } catch (cleanup: Throwable) {
                    if (cleanup !== failure) failure.addSuppressed(cleanup)
                }
                throw failure
            }
        }
    }
}
