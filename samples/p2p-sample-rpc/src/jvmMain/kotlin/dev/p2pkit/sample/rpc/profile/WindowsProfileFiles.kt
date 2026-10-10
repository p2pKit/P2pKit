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
        catch (failure: Throwable) { handle.failure = failure; throw failure }
    }

    override fun close() {
        var interrupted: InterruptedException? = null
        fun waitForOwner() {
            try { changed.await() } catch (caught: InterruptedException) {
                if (interrupted == null) interrupted = caught else interrupted.addSuppressed(caught)
            }
        }
        monitor.withLock {
            // Do not abandon ownership after interruption. Join the actual owner, then restore the interrupt.
            while (state == State.Closing) waitForOwner()
            if (state == State.Closed || state == State.Failed) {
                interrupted?.let { Thread.currentThread().interrupt() }
                val failure = closeFailure ?: interrupted
                failure?.let { throw it }
                return
            }
            state = State.Closing
            while (busy) waitForOwner()
        }
        var failure: Throwable? = interrupted
        // The registry is now sealed, and even late native allocations were registered before busy was cleared.
        for (handle in monitor.withLock { handles.values.toList().asReversed() }) {
            try { closeHandle(handle) } catch (caught: Throwable) {
                if (failure == null) failure = caught else if (failure !== caught) failure.addSuppressed(caught)
            }
        }
        monitor.withLock {
            closeFailure = failure
            state = if (failure == null) State.Closed else State.Failed
            changed.signalAll()
        }
        interrupted?.let { Thread.currentThread().interrupt() }
        failure?.let { throw it }
    }

    private inner class Directory(private val handle: Handle, private val identity: WindowsProfileIdentity) :
        ProtectedProfileDirectory {
        private val children = linkedMapOf<String, Directory>()
        override val mutexIdentity: Any = identity
        private fun verify() {
            check(WindowsProfileIdentity.decode(native.directoryIdentity(handle.value), true) == identity)
        }
        override fun verifyIdentity(): Any = operation(handle, cleanupRead = true) { verify(); identity }
        override fun fileIdentity(name: String): Any = operation(handle) {
            verify(); WindowsProfileIdentity.decode(native.fileIdentity(handle.value, profileComponent(name)), false)
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
                Directory(child, WindowsProfileIdentity.decode(native.directoryIdentity(child.value), true))
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
            val copy = bytes.copyOf()
            try {
                operation(handle) { verify(); native.write(handle.value, profileComponent(name), copy, replace) }
            } finally { copy.fill(0) }
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
                check(expectedIdentity is WindowsProfileIdentity && !expectedIdentity.directory &&
                    expectedIdentity.volume == identity.volume) { "Invalid expected profile file identity" }
                expectedIdentity
            } else {
                if (!native.exists(handle.value, component)) return@operation false
                WindowsProfileIdentity.decode(native.fileIdentity(handle.value, component), false)
            }
            native.delete(handle.value, component, expected.encoded())
        }
        override fun sync() = operation(handle) { verify(); native.sync(handle.value) }
        override fun deleteIfEmpty() = operation(handle) { verify(); native.deleteIfEmpty(handle.value) }
    }

    companion object {
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
