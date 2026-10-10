package dev.p2pkit.sample.rpc.profile

import java.util.concurrent.atomic.AtomicLong

/** Inert memory model of the proposed native ABI. It is not a filesystem, production fallback, or Windows evidence. */
internal class WindowsProfileModel(val store: Store = Store()) : WindowsProfileNativeApi {
    class Node(val id: Long, val directory: Boolean, var bytes: ByteArray = byteArrayOf()) {
        val entries = linkedMapOf<String, Node>()
    }
    class Store {
        private val ids = AtomicLong(1)
        val root = Node(ids.getAndIncrement(), true)
        val locks = mutableSetOf<Pair<Long, String>>()
        fun node(directory: Boolean, bytes: ByteArray = byteArrayOf()) = Node(ids.getAndIncrement(), directory, bytes)
    }
    private data class Handle(val node: Node, val lock: Pair<Long, String>? = null)
    private val handles = linkedMapOf<Long, Handle>()
    private val ids = AtomicLong(1)
    var declaredAbi = 1
    var declaredCapabilities = 0x7fL
    var invalidMetadata = false
    var readOversize = false
    var writeFailure: Exception? = null
    var closeFailure: Exception? = null
    var beforeRead: () -> Unit = {}
    var beforeChild: () -> Unit = {}
    var beforeClose: () -> Unit = {}
    var writtenInput: ByteArray? = null
    var oversizedOutput: ByteArray? = null
    val closeCalls = mutableListOf<Long>()
    var opens = 0
    val remaining get() = handles.size
    override fun abi() = declaredAbi
    override fun capabilities() = declaredCapabilities
    private fun own(node: Node, lock: Pair<Long, String>? = null): Long = ids.getAndIncrement().also {
        handles[it] = Handle(node, lock)
    }
    private fun node(handle: Long): Node = checkNotNull(handles[handle]).node
    private fun identity(node: Node): LongArray = WindowsProfileIdentity(7, 0, node.id, node.directory).encoded()
        .also { if (invalidMetadata) it[4] = 0 }
    override fun openRoot(): Long { opens++; return own(store.root) }
    override fun directoryIdentity(handle: Long): LongArray = identity(node(handle))
    override fun fileIdentity(directory: Long, name: String): LongArray =
        identity(node(directory).entries.getValue(name))
    override fun exists(directory: Long, name: String) = name in node(directory).entries
    override fun names(directory: Long): Array<String> = node(directory).entries.keys.toTypedArray()
    override fun child(directory: Long, name: String, create: Boolean): Long {
        beforeChild()
        val parent = node(directory)
        if (create) { check(name !in parent.entries); parent.entries[name] = store.node(true) }
        val child = parent.entries.getValue(name)
        check(child.directory)
        return own(child)
    }
    override fun read(directory: Long, name: String, maximum: Int): ByteArray {
        beforeRead()
        if (readOversize) return ByteArray(maximum + 1) { 12 }.also { oversizedOutput = it }
        return node(directory).entries.getValue(name).bytes.copyOf().also { check(it.size <= maximum) }
    }
    override fun write(directory: Long, name: String, bytes: ByteArray, replace: Boolean) {
        writtenInput = bytes
        writeFailure?.let { throw it }
        val parent = node(directory)
        check(replace || name !in parent.entries)
        parent.entries[name] = store.node(false, bytes.copyOf())
    }
    override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long {
        val parent = node(directory)
        val key = parent.id to name
        synchronized(store) { check(store.locks.add(key)) { "Synthetic profile lock held" } }
        val file = parent.entries.getOrPut(name) { store.node(false) }
        return own(file, key)
    }
    override fun delete(directory: Long, name: String, expected: LongArray): Boolean {
        val parent = node(directory)
        val found = parent.entries[name] ?: return false
        check(identity(found).contentEquals(expected)) { "Synthetic identity replacement" }
        parent.entries.remove(name)
        return true
    }
    override fun sync(directory: Long) { check(node(directory).directory) }
    override fun deleteIfEmpty(directory: Long) { check(node(directory).entries.isEmpty()) }
    override fun close(handle: Long) {
        beforeClose()
        closeCalls += handle
        closeFailure?.let { throw it }
        val owned = checkNotNull(handles.remove(handle))
        owned.lock?.let { synchronized(store) { check(store.locks.remove(it)) } }
    }
}
